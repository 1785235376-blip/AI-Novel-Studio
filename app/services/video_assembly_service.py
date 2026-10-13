"""Local-only, bounded video cut assembly from verified project assets."""
from __future__ import annotations
import base64
import copy
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import tempfile
from uuid import uuid4
from ..media_files import inspect_media, MediaValidationError
from ..repository import now
from ..storage import atomic_write
from ..repositories.file.mutation_coordinator import workspace_mutation
from .v1_capability_service import CapabilityVersionConflict


class VideoAssemblyService:
    _studio_active = set()
    _studio_process = str(uuid4())
    def __init__(self, root, assets):
        self.root=Path(root)/'video-assemblies';self.assets=assets;self._active=set()

    def _scope_dir(self, novel_id, branch_id, actor_id):
        return self.root/hashlib.sha256(json.dumps([novel_id,branch_id,actor_id]).encode()).hexdigest()

    def list(self,novel_id,branch_id,actor_id):
        rows=sorted([json.loads(path.read_text()) for path in self._scope_dir(novel_id,branch_id,actor_id).glob('*.json')],key=lambda row:row['created_at'],reverse=True)
        return [{**row,'recoverable':row.get('status')=='RUNNING' and row['id'] not in self._active} for row in rows]

    def create(self,novel_id,branch_id,actor_id,screenplay_id,clips):
        if not 1<=len(clips)<=30:raise ValueError('select between 1 and 30 video clips')
        decoder=shutil.which('ffmpeg')
        if not decoder:raise MediaValidationError('MEDIA_VALIDATOR_NOT_CONFIGURED')
        verified=[];total=0
        for clip in clips:
            asset=self.assets.get(clip['asset_id'],branch_id=branch_id)
            if asset['novel_id']!=novel_id or not asset['media_type'].startswith('video/'):raise ValueError('video asset does not belong to this project and branch')
            data=self.assets.content(asset['id'],branch_id=branch_id);measured=inspect_media(data,'video')
            start=int(clip.get('start_ms') or 0);end=int(clip.get('end_ms') or measured['duration_ms'])
            if start<0 or end<=start or end>measured['duration_ms']:raise ValueError('clip trim is outside measured media duration')
            total+=end-start
            if total>600000:raise ValueError('assembly exceeds the ten-minute limit')
            verified.append((data,{**clip,'start_ms':start,'end_ms':end,'source_sha256':asset['sha256'],'source_version':asset.get('version',1)}))
        job={'id':str(uuid4()),'novel_id':novel_id,'branch_id':branch_id,'owner_actor_id':actor_id,'screenplay_id':screenplay_id,'status':'RUNNING','created_at':now(),'updated_at':now(),'audio_policy':'VIDEO_ONLY','clips':[row for _,row in verified],'requested_duration_ms':total}
        path=self._scope_dir(novel_id,branch_id,actor_id)/(job['id']+'.json');atomic_write(path,json.dumps(job,ensure_ascii=False));self._active.add(job['id'])
        try:
            with tempfile.TemporaryDirectory(prefix='novel-video-cut-') as directory:
                directory=Path(directory);command=[decoder,'-nostdin','-v','error','-xerror','-threads','1'];filters=[]
                for index,(data,clip) in enumerate(verified):
                    source=directory/f'clip-{index}.bin';source.write_bytes(data)
                    command+=['-protocol_whitelist','file,pipe','-i',str(source)]
                    # Fixed review rendition; originals are retained byte-for-byte.
                    filters.append(f"[{index}:v:0]trim=start={clip['start_ms']/1000}:end={clip['end_ms']/1000},setpts=PTS-STARTPTS,scale=640:360:force_original_aspect_ratio=decrease,pad=640:360:(ow-iw)/2:(oh-ih)/2,setsar=1,fps=24[v{index}]")
                filters.append(''.join(f'[v{index}]' for index in range(len(verified)))+f'concat=n={len(verified)}:v=1:a=0[out]')
                output=directory/'assembly.mp4';command+=['-filter_complex_threads','1','-filter_complex',';'.join(filters),'-map','[out]','-an','-c:v','mpeg4','-q:v','4','-fs',str(self.assets.MAX_BYTES+1),'-y',str(output)]
                subprocess.run(command,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE,timeout=120,check=True)
                data=output.read_bytes()
                if len(data)>self.assets.MAX_BYTES:raise MediaValidationError('assembled video exceeds asset limit')
                measured=inspect_media(data,'video')
                # Rounding to 24 fps may alter the end by one frame per segment.
                if abs(measured['duration_ms']-total)>50*len(verified):raise MediaValidationError('assembled duration differs from requested trims')
                asset=self.assets.create(novel_id,f"assembly-{job['id']}.mp4",base64.b64encode(data).decode(),'video/mp4','video','video-assembly:'+job['id'],branch_id=branch_id)
                asset=self.assets.update_metadata(asset['id'],{'source_job_id':job['id'],'source_asset_ids':list(dict.fromkeys(clip['asset_id'] for _,clip in verified))},branch_id=branch_id)
                job.update(status='SUCCEEDED',asset_id=asset['id'],duration_ms=measured['duration_ms'],sha256=asset['sha256'],updated_at=now(),render_profile='REVIEW_640x360_24FPS_VIDEO_ONLY')
        except Exception:
            job.update(status='FAILED',error='VIDEO_ASSEMBLY_FAILED',updated_at=now())
        try:atomic_write(path,json.dumps(job,ensure_ascii=False,indent=2))
        finally:self._active.discard(job['id'])
        return job

    def _studio_context(self, novel_id, branch_id, actor_id, context):
        """Validate a server context, never infer an actor/incarnation from input."""
        from ..experimental.flags import enabled_flags
        if "narrative_production_v2" not in enabled_flags():
            raise ValueError("STUDIO_TIMELINE_FEATURE_DISABLED")
        for identity in (novel_id, actor_id):
            if not isinstance(identity, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", identity):
                raise ValueError("STUDIO_TIMELINE_OWNER_INVALID")
        if branch_id is not None and (not isinstance(branch_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", branch_id)):
            raise ValueError("STUDIO_TIMELINE_BRANCH_INVALID")
        if (not isinstance(context, dict) or context.get("actor") != actor_id
                or not isinstance(context.get("scope_key"), str) or not re.fullmatch(r"[a-f0-9]{64}", context["scope_key"])
                or not isinstance(context.get("incarnation"), str)
                or not re.fullmatch(r"(?:file|postgres):[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}", context["incarnation"])):
            raise ValueError("STUDIO_TIMELINE_CONTEXT_INVALID")
        return context

    def _studio_dir(self, novel_id, branch_id, actor_id, context):
        self._studio_context(novel_id, branch_id, actor_id, context)
        binding = hashlib.sha256(json.dumps([context["scope_key"], context["incarnation"]]).encode()).hexdigest()
        # Same original owner/root, a private row namespace that legacy list()
        # cannot expose when the narrative feature or new scoped entry is off.
        path = self._scope_dir(novel_id, branch_id, actor_id) / "studio" / binding
        for candidate in (self.root, path.parent.parent, path.parent, path):
            if candidate.is_symlink():
                raise ValueError("STUDIO_TIMELINE_OWNER_PATH_INVALID")
        return path

    @staticmethod
    def _studio_digest(row):
        return hashlib.sha256(json.dumps({key: value for key, value in row.items() if key != "receipt_digest"},
                                        ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()

    def _studio_path(self, novel_id, branch_id, actor_id, job_id, context):
        if not isinstance(job_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,239}", job_id):
            raise ValueError("STUDIO_TIMELINE_JOB_ID_INVALID")
        path = self._studio_dir(novel_id, branch_id, actor_id, context) / (job_id + ".json")
        if path.is_symlink():
            raise ValueError("STUDIO_TIMELINE_OWNER_PATH_INVALID")
        return path

    @staticmethod
    def _studio_receipt_bytes(path):
        """Read one bounded snapshot without trusting a pre-open size check."""
        limit = 384_000
        def snapshot(value):
            return (value.st_dev, value.st_ino, value.st_size,
                    value.st_mtime_ns, value.st_ctime_ns)

        before = path.stat()
        if before.st_size > limit:
            raise ValueError("STUDIO_TIMELINE_RECEIPT_LIMIT")
        # Binary, unbuffered I/O bounds actual bytes, including the single
        # overflow sentinel. Reject replacement and observable in-place writes,
        # even when the resulting bytes would form a valid receipt. This uses
        # filesystem metadata, not an OS-level snapshot or a new writer lock.
        with path.open("rb", buffering=0) as source:
            opened = os.fstat(source.fileno())
            if opened.st_size > limit:
                raise ValueError("STUDIO_TIMELINE_RECEIPT_LIMIT")
            if snapshot(opened) != snapshot(before):
                raise ValueError("STUDIO_TIMELINE_RECEIPT_INVALID")
            data = source.read(limit + 1)
            after = os.fstat(source.fileno())
            if len(data) > limit or after.st_size > limit:
                raise ValueError("STUDIO_TIMELINE_RECEIPT_LIMIT")
            if (len(data) != before.st_size or snapshot(after) != snapshot(before)
                    or snapshot(path.stat()) != snapshot(before)):
                raise ValueError("STUDIO_TIMELINE_RECEIPT_INVALID")
        return data

    def _studio_load(self, novel_id, branch_id, actor_id, job_id, context):
        path = self._studio_path(novel_id, branch_id, actor_id, job_id, context)
        row = json.loads(self._studio_receipt_bytes(path).decode("utf-8"))
        if (not isinstance(row, dict) or row.get("id") != job_id or row.get("novel_id") != novel_id
                or row.get("branch_id") != branch_id or row.get("owner_actor_id") != actor_id
                or row.get("scope_key") != context["scope_key"] or row.get("incarnation") != context["incarnation"]
                or row.get("required_features") != ["narrative_production_v2"]
                or type(row.get("version")) is not int or row["version"] < 1
                or row.get("receipt_digest") != self._studio_digest(row)):
            raise ValueError("STUDIO_TIMELINE_RECEIPT_INVALID")
        if "graph_binding" in row.get("context", {}):
            from ..creative.graph_media_binding import validate_graph_binding
            if row["context"]["graph_binding"] is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
            validate_graph_binding(row["context"]["graph_binding"], row["context"])
        return row

    def _studio_read(self, novel_id, branch_id, actor_id, job_id, *, context):
        # No scope/source callbacks inside this owner lock.
        with workspace_mutation(self.root, "studio-media-jobs"):
            return copy.deepcopy(self._studio_load(novel_id, branch_id, actor_id, job_id, context))

    def _studio_write(self, novel_id, branch_id, actor_id, row, *, context, expected_version=None):
        self._studio_context(novel_id, branch_id, actor_id, context)
        value = copy.deepcopy(row)
        for key, expected in {"novel_id": novel_id, "branch_id": branch_id, "owner_actor_id": actor_id,
                              "scope_key": context["scope_key"], "incarnation": context["incarnation"],
                              "required_features": ["narrative_production_v2"]}.items():
            if key in value and value[key] != expected:
                raise ValueError("STUDIO_TIMELINE_RECEIPT_CONTEXT_MISMATCH")
            value[key] = expected
        path = self._studio_path(novel_id, branch_id, actor_id, value.get("id"), context)
        with workspace_mutation(self.root, "studio-media-jobs"):
            if path.exists():
                original = self._studio_load(novel_id, branch_id, actor_id, value["id"], context)
                if expected_version != original["version"]:
                    raise CapabilityVersionConflict(copy.deepcopy(original))
                immutable = ("id", "kind", "type", "contract", "body", "novel_id", "branch_id", "owner_actor_id", "scope_key", "incarnation", "request_id",
                             "request_digest", "input_digest", "operation_id", "timeline_snapshot", "timeline", "sources", "rights", "context", "created_at")
                if any(value.get(key) != original.get(key) for key in immutable):
                    raise ValueError("STUDIO_TIMELINE_IMMUTABLE_RECEIPT_CHANGED")
                value["version"] = original["version"] + 1
            else:
                if expected_version not in (None, 0):
                    raise FileNotFoundError(value["id"])
                if len(list(path.parent.glob("*.json"))) >= 100:
                    raise ValueError("STUDIO_MEDIA_JOB_LIMIT")
                value["version"] = 1
            value["updated_at"] = now()
            value["receipt_digest"] = self._studio_digest(value)
            encoded = json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False)
            if len(encoded.encode("utf-8")) > 384_000:
                raise ValueError("STUDIO_TIMELINE_RECEIPT_LIMIT")
            atomic_write(path, encoded)
            return copy.deepcopy(value)

    def _studio_mutate(self, novel_id, branch_id, actor_id, job_id, expected_version, callback, *, context):
        with workspace_mutation(self.root, "studio-media-jobs"):
            row = self._studio_load(novel_id, branch_id, actor_id, job_id, context)
            if row["version"] != expected_version:
                raise CapabilityVersionConflict(copy.deepcopy(row))
            callback(row)
            return self._studio_write(novel_id, branch_id, actor_id, row, context=context, expected_version=expected_version)

    def get_studio(self, novel_id, branch_id, actor_id, job_id, *, context, guard):
        guard()
        row = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
        guard()
        return self._studio_projection(row)

    def _studio_projection(self, row):
        # Observational fields are outside the persisted receipt. Absence from
        # this process's set is not evidence a different executor stopped.
        unknown = (row.get("kind") == "STUDIO_TIMELINE" and row.get("status") == "RUNNING"
                   and (str(self.root.resolve()), row["id"]) not in self._studio_active)
        return {**copy.deepcopy(row), "needs_reconciliation": unknown,
                "execution_state": "RUNNING_UNVERIFIED" if unknown else row.get("status")}

    def list_studio(self, novel_id, branch_id, actor_id, *, context, guard):
        guard()
        directory = self._studio_dir(novel_id, branch_id, actor_id, context)
        with workspace_mutation(self.root, "studio-media-jobs"):
            paths = list(directory.glob("*.json"))
            if len(paths) > 100:
                raise ValueError("STUDIO_TIMELINE_JOB_LIMIT")
            rows = [self._studio_load(novel_id, branch_id, actor_id, path.stem, context) for path in paths]
        guard()
        return [self._studio_projection(row) for row in sorted(rows, key=lambda row: (row["created_at"], row["id"]), reverse=True)]

    def create_studio(self, novel_id, branch_id, actor_id, timeline, *, context, guard, source_guard, publish, export_profile=None):
        """Lease one original execution; callbacks never hold the queue lock."""
        self._studio_context(novel_id, branch_id, actor_id, context)
        request_id = context.get("request_id")
        if not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", request_id):
            raise ValueError("STUDIO_TIMELINE_REQUEST_INVALID")
        if not all(callable(callback) for callback in (guard, source_guard, publish)):
            raise ValueError("STUDIO_TIMELINE_OWNER_CALLBACKS_REQUIRED")
        job_id = hashlib.sha256(json.dumps([context["scope_key"], context["incarnation"], actor_id, request_id], separators=(",", ":")).encode()).hexdigest()
        guard()
        with workspace_mutation(self.root, "studio-timeline-execution:" + job_id):
            return self._create_studio_locked(novel_id, branch_id, actor_id, timeline, context=context,
                guard=guard, source_guard=source_guard, publish=publish, export_profile=export_profile)

    def queue_studio(self, novel_id, branch_id, actor_id, timeline, *, context, guard, export_profile=None):
        """Persist one original QUEUED receipt without inspecting or rendering.

        This accepts only server context. The supplied guard is the original
        Host guard; a Graph caller rechecks its own run/source phase after this
        admission. No external callback runs inside the original queue lock.
        """
        if not callable(guard):
            raise ValueError("STUDIO_TIMELINE_OWNER_CALLBACKS_REQUIRED")
        context = copy.deepcopy(context)
        prepared = self._prepare_studio_inputs(novel_id, branch_id, actor_id, timeline, context=context,
                                               export_profile=export_profile)
        if context.get("operation_id") != "m9.timeline.multitrack":
            raise ValueError("STUDIO_TIMELINE_OPERATION_INVALID")
        job_id = prepared["job_id"]
        guard()
        with workspace_mutation(self.root, "studio-media-jobs"):
            path = self._studio_path(novel_id, branch_id, actor_id, job_id, context)
            if path.exists():
                row = self._studio_load(novel_id, branch_id, actor_id, job_id, context)
                if (row.get("kind") != "STUDIO_TIMELINE" or row.get("input_digest") != prepared["input_digest"]
                        or row.get("request_digest") != prepared["request_digest"]
                        or row.get("context", {}).get("graph_binding") != context.get("graph_binding")):
                    raise ValueError("STUDIO_TIMELINE_IDEMPOTENCY_CONFLICT")
            else:
                row = self._studio_write(novel_id, branch_id, actor_id,
                    {"id": job_id, "kind": "STUDIO_TIMELINE", "contract": "studio-timeline-render/1", "status": "QUEUED", "phase": "QUEUED",
                     "request_id": prepared["request_id"], "request_digest": prepared["request_digest"], "input_digest": prepared["input_digest"],
                     "operation_id": context.get("operation_id"), "timeline_snapshot": copy.deepcopy(prepared["snapshot"]), "timeline": prepared["definition"],
                     "sources": prepared["sources"], "rights": copy.deepcopy(context.get("rights", {})), "context": context, "created_at": now(),
                     "review_state": "HUMAN_REVIEW_REQUIRED", "output_candidate": None, "model_called": False, "automatic_retry": False},
                    context=context)
        guard()
        return self._studio_projection(row)

    def execute_studio(self, novel_id, branch_id, actor_id, job_id, expected_version, expected_request_digest, *,
                       context, guard, source_guard, publish):
        """Execute an exact QUEUED receipt once under its original lease.

        RUNNING/UNKNOWN/final receipts are never retried by this method. All
        actual input/profile values come from the original immutable receipt,
        and the Graph/source guard remains outside the queue mutation lock.
        """
        self._studio_context(novel_id, branch_id, actor_id, context)
        self._studio_path(novel_id, branch_id, actor_id, job_id, context)
        if (type(expected_version) is not int or expected_version < 1
                or not isinstance(expected_request_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_request_digest)):
            raise ValueError("STUDIO_TIMELINE_EXECUTE_VERSION_INVALID")
        if not all(callable(callback) for callback in (guard, source_guard, publish)):
            raise ValueError("STUDIO_TIMELINE_OWNER_CALLBACKS_REQUIRED")
        guard()
        with workspace_mutation(self.root, "studio-timeline-execution:" + job_id):
            row = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
            if row.get("kind") != "STUDIO_TIMELINE":
                raise FileNotFoundError(job_id)
            if row["version"] != expected_version or row["request_digest"] != expected_request_digest:
                raise CapabilityVersionConflict(copy.deepcopy(row))
            if row.get("status") != "QUEUED":
                raise ValueError("STUDIO_TIMELINE_EXECUTE_NOT_QUEUED")
            captured = row.get("context")
            if (not isinstance(captured, dict) or any(captured.get(key) != context.get(key) for key in ("actor", "scope_key", "incarnation", "graph_binding"))
                    or captured.get("request_digest") != expected_request_digest
                    or ("request_digest" in context and context["request_digest"] != expected_request_digest)):
                raise ValueError("STUDIO_TIMELINE_EXECUTION_CONTEXT_CHANGED")
            prepared = self._prepare_studio_inputs(novel_id, branch_id, actor_id, row["timeline"], context=captured,
                                                   export_profile=captured.get("export_profile"))
            if (prepared["job_id"] != job_id or prepared["input_digest"] != row["input_digest"]
                    or prepared["definition"] != row["timeline"] or prepared["sources"] != row["sources"]
                    or prepared["snapshot"] != row["timeline_snapshot"] or prepared["request_id"] != row["request_id"]
                    or row.get("rights") != captured.get("rights", {}) or row.get("operation_id") != captured.get("operation_id")
                    or captured.get("operation_id") != "m9.timeline.multitrack"):
                raise ValueError("STUDIO_TIMELINE_EXECUTION_INPUT_CHANGED")
            # This is the last external guard before the original queue CAS.
            # A cancellation between the guard and CAS changes the version and
            # wins without any native process or publication being invoked.
            guard()
            key = (str(self.root.resolve()), job_id)
            queued_digest = row["receipt_digest"]
            def reserve(value):
                if (value.get("status") != "QUEUED" or value.get("request_digest") != expected_request_digest
                        or value.get("receipt_digest") != queued_digest):
                    raise ValueError("STUDIO_TIMELINE_EXECUTION_ATTEMPT_CHANGED")
                value.update(status="RUNNING", phase="RENDERING", execution_started_at=now(),
                             executor={"pid": os.getpid(), "process": self._studio_process}, automatic_retry=False)
            row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, expected_version, reserve, context=captured)
            self._studio_active.add(key)
            return self._render_studio_receipt(novel_id, branch_id, actor_id, row, context=captured,
                guard=guard, source_guard=source_guard, publish=publish, export_profile=prepared["export_profile"])

    def cancel_studio(self, novel_id, branch_id, actor_id, job_id, expected_version, expected_request_digest, *, context, guard):
        """Fence the original queue; the active local process observes this CAS.

        This intentionally does not wait for the execution lease. A private
        publication already in flight may still exist; cancellation never
        implies deletion of that candidate or remote-provider termination.
        """
        self._studio_context(novel_id, branch_id, actor_id, context)
        self._studio_path(novel_id, branch_id, actor_id, job_id, context)
        if (type(expected_version) is not int or expected_version < 1
                or not isinstance(expected_request_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_request_digest)):
            raise ValueError("STUDIO_TIMELINE_CANCEL_VERSION_INVALID")
        guard()
        def cancel(value):
            if value.get("kind") != "STUDIO_TIMELINE":
                raise FileNotFoundError(job_id)
            if value.get("request_digest") != expected_request_digest:
                raise CapabilityVersionConflict(copy.deepcopy(value))
            previous_status = value.get("status")
            if previous_status not in {"QUEUED", "RUNNING", "UNKNOWN", "SUCCEEDED", "AWAITING_REVIEW"}:
                raise ValueError("STUDIO_TIMELINE_CANCEL_NOT_ACTIVE")
            value.update(status="CANCELLED", phase="EXECUTION_FENCED", cancelled_at=now(),
                         automatic_retry=False, error_code="STUDIO_TIMELINE_EXECUTION_CANCELLED",
                         cancellation_mode="LOCAL_RENDER_PROCESS_STOP_REQUESTED" if previous_status == "RUNNING" else "LOCAL_RESULT_DISCARD")
        row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, expected_version, cancel, context=context)
        guard()
        return self._studio_projection(row)

    def reconcile_studio(self, novel_id, branch_id, actor_id, job_id, expected_version, expected_request_digest, *, context, guard,
                         recover_candidate=None, recover_review=None):
        """Fence a stopped executor and recover only a proven original Asset.

        Acquiring the same cross-process execution lease proves the original
        rendering call is no longer holding it. GET cannot make this claim.
        """
        self._studio_context(novel_id, branch_id, actor_id, context)
        self._studio_path(novel_id, branch_id, actor_id, job_id, context)
        if (type(expected_version) is not int or expected_version < 1
                or not isinstance(expected_request_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", expected_request_digest)):
            raise ValueError("STUDIO_TIMELINE_RECONCILE_VERSION_INVALID")
        if (recover_candidate is not None and not callable(recover_candidate)
                or recover_review is not None and not callable(recover_review)):
            raise ValueError("STUDIO_TIMELINE_RECOVERY_CALLBACK_INVALID")
        guard()
        with workspace_mutation(self.root, "studio-timeline-execution:" + job_id):
            row = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
            if row.get("kind") != "STUDIO_TIMELINE":
                raise FileNotFoundError(job_id)
            if row["version"] != expected_version or row["request_digest"] != expected_request_digest:
                raise CapabilityVersionConflict(copy.deepcopy(row))
            if row.get("status") not in {"RUNNING", "UNKNOWN", "REVIEWING"}:
                raise ValueError("STUDIO_TIMELINE_RECONCILE_NOT_ACTIVE")
            guard()
            if row["status"] == "REVIEWING":
                candidate = copy.deepcopy(row.get("output_candidate"))
                recovered = None
                def compensate():
                    nonlocal recovered
                    def change(current):
                        if (current["status"] != "REVIEWING" or current["request_digest"] != row["request_digest"]
                                or current.get("output_candidate") != candidate or current["context"] != row["context"]
                                or current.get("receipt_digest") != row.get("receipt_digest")):
                            raise ValueError("STUDIO_TIMELINE_REVIEW_RECOVERY_CHANGED")
                        current.update(status="AWAITING_REVIEW", phase="HUMAN_REVIEW_REQUIRED", review_state="HUMAN_REVIEW_REQUIRED",
                            error_code="STUDIO_TIMELINE_REVIEW_NOT_PROMOTED", recovery_state="EXACT_PRIVATE_REVIEW_RECOVERED_NO_REPLAY",
                            automatic_retry=False)
                    recovered = self._studio_mutate(novel_id, branch_id, actor_id, job_id, row["version"], change, context=context)
                if candidate is not None and recover_review is not None:
                    recover_review(candidate, compensate)
                guard()
                return self._studio_projection(recovered if recovered is not None else row)
            asset = None
            if (recover_candidate is not None and row.get("phase") in {"PUBLICATION_READY", "CANDIDATE_RECORDED", "INTERRUPTED_EXECUTION_RECONCILED"}
                    and isinstance(row.get("output_digest"), str) and re.fullmatch(r"[a-f0-9]{64}", row["output_digest"])):
                # The callback leases the original scope/assets and proves
                # bytes and the original idempotency key. It never publishes.
                asset = recover_candidate(copy.deepcopy(row))
            if asset is None:
                row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, expected_version,
                    lambda value: value.update(status="UNKNOWN", phase="INTERRUPTED_EXECUTION_RECONCILED",
                        error_code="STUDIO_TIMELINE_OUTCOME_UNKNOWN", automatic_retry=False), context=context)
            else:
                candidate = self._studio_candidate(novel_id, branch_id, actor_id, job_id, context,
                                                   asset, row["output_digest"])
                if row.get("output_candidate") is not None and row["output_candidate"] != candidate:
                    raise ValueError("STUDIO_TIMELINE_RECOVERY_CANDIDATE_CHANGED")
                guard()
                row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, expected_version,
                    lambda value: value.update(status="SUCCEEDED", phase="HUMAN_REVIEW_REQUIRED", error_code=None,
                        output_candidate=candidate, recovery_state="ORIGINAL_PRIVATE_CANDIDATE_RECOVERED", automatic_retry=False),
                    context=context)
            guard()
            return self._studio_projection(row)

    @contextmanager
    def studio_review_phase(self, job_id):
        # Share the original timeline execution/recovery lease. A live review
        # cannot be mistaken for an interrupted reservation by reconcile.
        with workspace_mutation(self.root, "studio-timeline-execution:" + job_id):
            yield

    @staticmethod
    def _studio_candidate(novel_id, branch_id, actor_id, job_id, context, asset, output_digest):
        expected_origin = {"contract": "studio-production-result/1", "job_id": job_id,
            **{key: context[key] for key in ("scope_key", "incarnation", "actor", "request_digest", "operation_id", "sources")},
            "provider_id": None, "model_id": None, "license_note": context.get("license_note", "")}
        if "graph_binding" in context:
            from ..creative.graph_media_binding import validate_graph_binding
            graph_binding = validate_graph_binding(context["graph_binding"], context)
            if graph_binding is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
            expected_origin["graph_binding"] = copy.deepcopy(graph_binding)
        if (not isinstance(asset, dict) or not isinstance(asset.get("id"), str)
                or type(asset.get("version")) is not int or asset["version"] < 1
                or asset.get("sha256") != output_digest or asset.get("kind") != "video"
                or asset.get("novel_id") != novel_id or asset.get("branch_id") != branch_id
                or asset.get("_owner_actor_id") != actor_id or asset.get("deleted_at")
                or asset.get("source_job_id") != job_id or asset.get("_required_features") != ["narrative_production_v2"]
                or asset.get("_studio_result_origin") != expected_origin
                or asset.get("_project_binding") != {"novel_id": novel_id, "branch_id": branch_id,
                    "scope_key": context["scope_key"], "incarnation": context["incarnation"]}):
            raise ValueError("STUDIO_TIMELINE_PUBLICATION_RECEIPT_INVALID")
        return {"id": asset["id"], "version": asset["version"], "digest": asset["sha256"], "kind": "video"}

    def _prepare_studio_inputs(self, novel_id, branch_id, actor_id, timeline, *, context, export_profile=None):
        """Pure original input normalization and digest, with no source/tool I/O."""
        from .studio_timeline_render import normalize_studio_timeline, studio_sources, timeline_digest
        self._studio_context(novel_id, branch_id, actor_id, context)
        if "graph_binding" in context:
            from ..creative.graph_media_binding import validate_graph_binding
            if validate_graph_binding(context["graph_binding"], context) is None:
                raise ValueError("CREATIVE_GRAPH_MEDIA_BINDING_INVALID")
        definition = normalize_studio_timeline(timeline)
        if export_profile is not None:
            from .studio_timeline_export import normalize_export_profile, validate_export_admission, export_profile_digest
            export_profile = normalize_export_profile(export_profile)
            validate_export_admission(definition, export_profile, self.assets.MAX_BYTES)
            if (context.get("export_profile") != export_profile
                    or context.get("export_profile_digest") != export_profile_digest(export_profile)):
                raise ValueError("STUDIO_TIMELINE_EXPORT_CONTEXT_CHANGED")
        elif "export_profile" in context or "export_profile_digest" in context:
            raise ValueError("STUDIO_TIMELINE_EXPORT_CONTEXT_CHANGED")
        request_id, request_digest = context.get("request_id"), context.get("request_digest")
        if (not isinstance(request_id, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]{0,99}", request_id)
                or not isinstance(request_digest, str) or not re.fullmatch(r"[a-f0-9]{64}", request_digest)):
            raise ValueError("STUDIO_TIMELINE_REQUEST_INVALID")
        snapshot = context.get("timeline_snapshot")
        if (not isinstance(snapshot, dict) or not isinstance(snapshot.get("id"), str)
                or type(snapshot.get("version")) is not int or snapshot["version"] < 1
                or not isinstance(snapshot.get("digest"), str) or not re.fullmatch(r"[a-f0-9]{64}", snapshot["digest"])):
            raise ValueError("STUDIO_TIMELINE_SNAPSHOT_REQUIRED")
        sources = studio_sources(definition)
        if context.get("sources") != sources or snapshot["digest"] != timeline_digest(definition):
            raise ValueError("STUDIO_TIMELINE_CONTEXT_SOURCE_OR_DEFINITION_CHANGED")
        payload = {"definition": definition, "timeline_snapshot": snapshot, "sources": sources,
                   "rights": context.get("rights", {}), "operation_id": context.get("operation_id")}
        if export_profile is not None:
            payload["export_profile"] = copy.deepcopy(export_profile)
        input_digest = timeline_digest(payload)
        job_id = hashlib.sha256(json.dumps([context["scope_key"], context["incarnation"], actor_id, request_id], separators=(",", ":")).encode()).hexdigest()
        return {"definition": definition, "snapshot": snapshot, "sources": sources, "export_profile": export_profile,
                "request_id": request_id, "request_digest": request_digest, "input_digest": input_digest, "job_id": job_id}

    def _create_studio_locked(self, novel_id, branch_id, actor_id, timeline, *, context, guard, source_guard, publish, export_profile=None):
        """Keep synchronous original create behavior; existing receipts never execute."""
        if not all(callable(callback) for callback in (guard, source_guard, publish)):
            raise ValueError("STUDIO_TIMELINE_OWNER_CALLBACKS_REQUIRED")
        prepared = self._prepare_studio_inputs(novel_id, branch_id, actor_id, timeline, context=context,
                                               export_profile=export_profile)
        definition, snapshot, sources = prepared["definition"], prepared["snapshot"], prepared["sources"]
        request_id, request_digest = prepared["request_id"], prepared["request_digest"]
        input_digest, job_id = prepared["input_digest"], prepared["job_id"]
        export_profile = prepared["export_profile"]
        directory = self._studio_dir(novel_id, branch_id, actor_id, context)
        key = (str(self.root.resolve()), job_id)
        guard()
        with workspace_mutation(self.root, "studio-media-jobs"):
            path = self._studio_path(novel_id, branch_id, actor_id, job_id, context)
            if path.exists():
                existing = self._studio_load(novel_id, branch_id, actor_id, job_id, context)
                if (existing.get("kind") != "STUDIO_TIMELINE" or existing.get("input_digest") != input_digest
                        or existing.get("request_digest") != request_digest):
                    raise ValueError("STUDIO_TIMELINE_IDEMPOTENCY_CONFLICT")
                row = existing
            else:
                if len(list(directory.glob("*.json"))) >= 100:
                    raise ValueError("STUDIO_TIMELINE_JOB_LIMIT")
                row = self._studio_write(novel_id, branch_id, actor_id,
                    {"id": job_id, "kind": "STUDIO_TIMELINE", "contract": "studio-timeline-render/1", "status": "RUNNING",
                     "request_id": request_id, "request_digest": request_digest, "input_digest": input_digest,
                     "operation_id": context.get("operation_id"), "timeline_snapshot": copy.deepcopy(snapshot), "timeline": definition,
                     "sources": sources, "rights": copy.deepcopy(context.get("rights", {})), "context": copy.deepcopy(context), "created_at": now(),
                     "review_state": "HUMAN_REVIEW_REQUIRED", "output_candidate": None, "model_called": False,
                     "automatic_retry": False, "executor": {"pid": os.getpid(), "process": self._studio_process}},
                    context=context)
                self._studio_active.add(key)
                existing = None
        if existing is not None:
            guard()
            return self.get_studio(novel_id, branch_id, actor_id, job_id, context=context, guard=guard)
        return self._render_studio_receipt(novel_id, branch_id, actor_id, row, context=context,
            guard=guard, source_guard=source_guard, publish=publish, export_profile=export_profile)

    def _render_studio_receipt(self, novel_id, branch_id, actor_id, row, *, context, guard, source_guard, publish, export_profile=None):
        """One real renderer/publication path, always under the original execution lease.

        publish(data, kind, filename, measured, job_id, job_guard) remains the
        original authorized private-Asset callback. No duplicate queue or
        worker owns this execution, and UNKNOWN never enters this method again.
        """
        from .studio_timeline_render import render_studio_timeline
        definition, job_id, request_digest = row["timeline"], row["id"], row["request_digest"]
        key = (str(self.root.resolve()), job_id)
        def execution_current():
            # External Host/source/graph guard is never called under queue lock.
            guard()
            current = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
            if (current.get("status") != "RUNNING" or current.get("request_digest") != request_digest
                    or current.get("version") != row["version"] or current.get("receipt_digest") != row["receipt_digest"]):
                raise ValueError("STUDIO_TIMELINE_EXECUTION_FENCED")
        candidate = None
        try:
            data, measured = render_studio_timeline(definition, source_guard=source_guard, guard=execution_current,
                                                  max_bytes=self.assets.MAX_BYTES, export_profile=export_profile)
            execution_current()
            row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, row["version"],
                lambda value: value.update(phase="PUBLICATION_READY", output_digest=hashlib.sha256(data).hexdigest(),
                                          measured=copy.deepcopy(measured)), context=context)
            publication_version = row["version"]
            publication_digest = row["receipt_digest"]
            def job_current():
                current = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
                if (current["version"] != publication_version or current["status"] != "RUNNING"
                        or current.get("phase") != "PUBLICATION_READY" or current["request_digest"] != request_digest
                        or current.get("receipt_digest") != publication_digest):
                    raise ValueError("STUDIO_TIMELINE_PUBLICATION_ATTEMPT_CHANGED")
            suffix = measured.get("extension")
            if suffix not in {"mp4", "webm"}:
                raise ValueError("STUDIO_TIMELINE_OUTPUT_CONTAINER_INVALID")
            asset = publish(data, "video", f"studio-timeline-{job_id}.{suffix}", measured, job_id, job_current)
            candidate = self._studio_candidate(novel_id, branch_id, actor_id, job_id, context, asset, hashlib.sha256(data).hexdigest())
            row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, row["version"],
                lambda value: value.update(output_candidate=candidate, phase="CANDIDATE_RECORDED"), context=context)
            guard()
            row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, row["version"],
                lambda value: value.update(status="SUCCEEDED", phase="HUMAN_REVIEW_REQUIRED"), context=context)
        except BaseException as error:
            # Publication may have completed even when its return/commit was
            # interrupted. Timeouts and process interruption are not failure
            # proof; keep the durable request and do not invoke publish again.
            ambiguous = (not isinstance(error, Exception) or isinstance(error, (subprocess.TimeoutExpired, OSError))
                         or row.get("phase") in {"PUBLICATION_READY", "CANDIDATE_RECORDED"})
            try:
                latest = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
                if latest.get("status") == "CANCELLED":
                    # The cancel CAS wins; never replace its fence with UNKNOWN.
                    row = latest
                    if candidate is not None and latest.get("output_candidate") is None:
                        # Publication has already happened and its private
                        # owner/origin/hash were validated above. Retain that
                        # fact without reopening, rerendering or promoting it.
                        def retain_cancelled(value):
                            if value.get("status") != "CANCELLED" or value.get("request_digest") != request_digest:
                                raise ValueError("STUDIO_TIMELINE_CANCELLED_RECEIPT_CHANGED")
                            value.update(output_candidate=copy.deepcopy(candidate),
                                         late_output_state="CANCELLED_RESULT_RETAINED")
                        try:
                            row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, latest["version"],
                                                      retain_cancelled, context=context)
                        except Exception:
                            # A competing receipt CAS or write failure cannot
                            # justify changing the durable cancellation fence.
                            row = self._studio_read(novel_id, branch_id, actor_id, job_id, context=context)
                            if row.get("status") != "CANCELLED":
                                raise error
                else:
                    row = self._studio_mutate(novel_id, branch_id, actor_id, job_id, row["version"],
                        lambda value: value.update(status="UNKNOWN" if ambiguous else "FAILED",
                                                  error_code="STUDIO_TIMELINE_OUTCOME_UNKNOWN" if ambiguous else "STUDIO_TIMELINE_RENDER_FAILED",
                                                  automatic_retry=False), context=context)
            except Exception:
                # Preserve the original in-flight/candidate receipt if the
                # status commit itself failed. Never replace it with success.
                raise error
            if not isinstance(error, Exception):
                raise
        finally:
            self._studio_active.discard(key)
        guard()
        return row
