from __future__ import annotations

import base64
import hashlib
import json
from pathlib import Path
import re
import threading
from uuid import uuid4

from ..asset_providers import AssetGenerationRequest
from ..media_files import fetch_media_bytes, inspect_image
from ..repository import now
from ..storage import atomic_write


_LOCKS: dict[str, threading.RLock] = {}
_LOCKS_GUARD = threading.Lock()
_ACTIVE: dict[str, set[str]] = {}


class ImageJobService:
    """Persistent image review queue. Provider results remain unapproved until accept."""
    def __init__(self, root: Path):
        self.root = root / 'image-jobs'
        with _LOCKS_GUARD: self._lock = _LOCKS.setdefault(str(self.root.resolve()), threading.RLock())
        self.owner_actor_id = None
        with _LOCKS_GUARD: self._active = _ACTIVE.setdefault(str(self.root.resolve()), set())

    def for_actor(self, actor_id):
        if not actor_id: raise ValueError('actor id is required')
        scoped=ImageJobService(self.root/'actors'/hashlib.sha256(actor_id.encode()).hexdigest())
        scoped.owner_actor_id=actor_id
        return scoped

    def _path(self, novel_id, branch_id=None):
        identity = json.dumps([novel_id, branch_id], ensure_ascii=False)
        return self.root / (hashlib.sha256(identity.encode()).hexdigest() + '.json')

    def _load(self, novel_id, branch_id=None):
        path = self._path(novel_id, branch_id)
        return json.loads(path.read_text()) if path.exists() else []

    def _mutate(self, novel_id, branch_id, operation):
        with self._lock:
            rows = self._load(novel_id, branch_id)
            result = operation(rows)
            atomic_write(self._path(novel_id, branch_id), json.dumps(rows, ensure_ascii=False))
            return dict(result)

    @staticmethod
    def _find(rows, job_id):
        row = next((row for row in rows if row['id'] == job_id), None)
        if row is None: raise FileNotFoundError(job_id)
        return row

    def list(self, novel_id, branch_id=None):
        with self._lock:
            return [{**row,'recoverable':row.get('status')=='RUNNING' and row.get('execution_token') not in self._active} for row in reversed(self._load(novel_id, branch_id))]

    def create(self, novel_id, branch_id, body, idempotency_key=None):
        parameters = dict(body.get('parameters') or {})
        from ..asset_providers import validate_image_parameters
        validate_image_parameters(parameters)
        def add(rows):
            payload = {key: body.get(key) for key in ('prompt','provider_id','model_id','parameters','character_id','scene_id','images','size','quality','output_format','allow_cloud_prompt') if key in body}
            digest = hashlib.sha256(json.dumps(payload,sort_keys=True).encode()).hexdigest()
            existing = next((row for row in rows if idempotency_key and row.get('idempotency_key') == idempotency_key), None)
            if existing:
                if existing['request_sha256'] != digest: raise ValueError('IMAGE_IDEMPOTENCY_CONFLICT')
                return existing
            row = {'id':str(uuid4()),'novel_id':novel_id,'branch_id':branch_id,'owner_actor_id':self.owner_actor_id,**payload,'status':'QUEUED','approval_status':'PENDING','attempt':0,'created_at':now(),'updated_at':now(),'idempotency_key':idempotency_key,'request_sha256':digest}
            rows.append(row); return row
        return self._mutate(novel_id,branch_id,add)

    def transition(self, novel_id, branch_id, job_id, target):
        def change(rows):
            row=self._find(rows,job_id)
            allowed={'CANCELLED':{'QUEUED','RUNNING'},'QUEUED':{'FAILED','CANCELLED'}}
            if row['status'] not in allowed[target] and not (target=='QUEUED' and row['status']=='RUNNING' and row.get('execution_token') not in self._active): raise ValueError('IMAGE_JOB_INVALID_TRANSITION')
            row.update(status=target,execution_token=None,error=None,updated_at=now())
            if target=='CANCELLED':row['cancellation_mode']='LOCAL_RESULT_DISCARD'
            return row
        return self._mutate(novel_id,branch_id,change)

    def execute(self, novel_id, branch_id, job_id, registry, check_authority=None, check_egress=None):
        def same_attempt(current, claimed):
            return (current.get('status') == 'RUNNING'
                    and current.get('execution_token') == claimed.get('execution_token')
                    and all(current.get(key) == claimed.get(key) for key in (
                        'novel_id', 'branch_id', 'owner_actor_id', 'request_sha256',
                        'provider_id', 'model_id', 'prompt', 'parameters', 'images',
                        'size', 'quality', 'output_format', 'allow_cloud_prompt')))

        def claim(rows):
            row=self._find(rows,job_id)
            if row['status']!='QUEUED': raise ValueError('IMAGE_JOB_NOT_QUEUED')
            if row.get('owner_actor_id') != self.owner_actor_id or row.get('novel_id') != novel_id or row.get('branch_id') != branch_id:
                raise ValueError('IMAGE_JOB_SCOPE_CHANGED')
            row.update(status='RUNNING',execution_token=str(uuid4()),attempt=row['attempt']+1,updated_at=now());self._active.add(row['execution_token']);return row
        job=self._mutate(novel_id,branch_id,claim)
        try:
            provider=registry.get(job['provider_id'])
            request=AssetGenerationRequest(job['provider_id'],job['model_id'],job['prompt'],job['id'],dict(job.get('parameters') or {}))
            if self.owner_actor_id and check_authority is None: raise ValueError('IMAGE_JOB_AUTHORITY_MISSING')
            if check_authority is not None: check_authority()
            if check_egress is not None:
                check_egress(job, provider)
            elif not getattr(provider, 'local', False):
                raise ValueError('IMAGE_EGRESS_AUTHORITY_MISSING')
            if check_authority is not None: check_authority()
            # Do not let cancellation/retry or owner/scope changes during
            # provider resolution dispatch a request from a stale attempt.
            with self._lock:
                current = self._find(self._load(novel_id, branch_id), job_id)
                if not same_attempt(current, job): return dict(current)
            if job.get('images'):
                if not hasattr(provider,'edit'): raise ValueError('IMAGE_EDIT_PROVIDER_UNSUPPORTED')
                result=provider.edit(request,job['images'],**{key:job[key] for key in ('size','quality','output_format') if key in job})
            else: result=provider.generate(request)
            if not result.asset_uri or len(result.asset_uri)>36*1024*1024: raise ValueError('IMAGE_RESULT_INVALID')
            def complete(rows):
                current=self._find(rows,job_id)
                if not same_attempt(current, job):return current
                current.update(status='SUCCEEDED',asset_uri=result.asset_uri,updated_at=now(),error=None);return current
            return self._mutate(novel_id,branch_id,complete)
        except Exception as exc:
            if isinstance(exc, ValueError) and str(exc) in {'IMAGE_JOB_AUTHORITY_MISSING', 'IMAGE_EGRESS_AUTHORITY_MISSING'}:
                error_code = str(exc)
            else:
                error_code="IMAGE_PARAMETER_UNSUPPORTED" if isinstance(exc,ValueError) and "IMAGE_PARAMETER_UNSUPPORTED" in str(exc) else "IMAGE_PROVIDER_REQUEST_FAILED"
            def fail(rows):
                current=self._find(rows,job_id)
                if same_attempt(current, job):current.update(status='FAILED',error=error_code,error_code=error_code,updated_at=now())
                return current
            return self._mutate(novel_id,branch_id,fail)
        finally:
            self._active.discard(job['execution_token'])

    def accept(self,novel_id,branch_id,job_id,assets,registry):
        job=self._find(self.list(novel_id,branch_id),job_id)
        if job['status']!='SUCCEEDED':raise ValueError('IMAGE_JOB_NOT_READY')
        if job.get('asset_id'): return assets.get(job['asset_id'],branch_id=branch_id)
        uri=job['asset_uri']
        if uri.startswith('data:image/'):
            match=re.fullmatch(r'data:image/[A-Za-z0-9.+-]+;base64,([A-Za-z0-9+/=]+)',uri)
            if not match or len(match[1])>assets.MAX_BYTES*4//3+8:raise ValueError('IMAGE_RESULT_INVALID')
            data=base64.b64decode(match[1],validate=True)
        else:
            provider=registry.get(job['provider_id'])
            data=fetch_media_bytes(uri,assets.MAX_BYTES,configured_provider_endpoint=getattr(provider,'endpoint',None))
        measured=inspect_image(data)
        def approve(rows):
            current=self._find(rows,job_id)
            if current['status']!='SUCCEEDED' or current.get('execution_token')!=job.get('execution_token'):raise ValueError('IMAGE_RESULT_CHANGED')
            if current.get('asset_id'):return assets.get(current['asset_id'],branch_id=branch_id)
            asset=assets.create(novel_id,f'image-{job_id}.{measured["extension"]}',base64.b64encode(data).decode(),measured['media_type'],'image','image-job:'+job_id,branch_id=branch_id)
            asset=assets.update_metadata(asset['id'],{'source_job_id':job_id,'provider_id':job['provider_id'],'model_id':job['model_id'],'parameters':job.get('parameters',{}),'approved_at':now(),'character_id':job.get('character_id'),'scene_id':job.get('scene_id')},branch_id=branch_id)
            current.update(approval_status='APPROVED',asset_id=asset['id'],approved_at=now(),updated_at=now())
            return asset
        return self._mutate(novel_id,branch_id,approve)
