from __future__ import annotations
import json, os, threading
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .storage import atomic_write

class IdempotencyStore:
    def __init__(self, path: Path, ttl_hours: int = 24):
        # Resolve once so aliases and later working-directory changes cannot
        # separate the cache being accessed from its cooperating-writer lock.
        self.path=Path(path).resolve(); self.ttl=timedelta(hours=ttl_hours); self.lock=threading.Lock()
    @contextmanager
    def _access(self):
        # Lazy import: repositories also import consumers of this store.
        from .repositories.file.mutation_coordinator import workspace_mutation
        # The entire JSON document is the mutation unit, not a request key.
        # Even reads may create coordination metadata, never a receipt file.
        key="idempotency-store:"+os.path.normcase(str(self.path))
        with self.lock, workspace_mutation(self.path.parent,key):
            yield
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):return {}
    def retained(self,key):
        """Read an existing receipt without TTL eviction or legacy adoption.

        Keyed generation uses this stricter observation path. Other callers
        retain get()'s original TTL behavior. Corruption is not a cache miss.
        """
        with self._access():
            try:data=json.loads(self.path.read_text(encoding='utf-8'))
            except FileNotFoundError:return None
            except (UnicodeError, json.JSONDecodeError) as exc:
                raise ValueError("IDEMPOTENCY_RETAINED_STORE_INVALID") from exc
            if not isinstance(data,dict):raise ValueError("IDEMPOTENCY_RETAINED_STORE_INVALID")
            if key not in data:return None
            item=data[key]
            if not isinstance(item,dict) or set(item)!={'created_at','value'}:
                raise ValueError("IDEMPOTENCY_RETAINED_RECORD_INVALID")
            return item
    def get(self,key):
        with self._access():
            data=self._load(); item=data.get(key)
            if not item:return None
            try:
                if datetime.now(timezone.utc)-datetime.fromisoformat(item['created_at']) > self.ttl:
                    data.pop(key,None); atomic_write(self.path,json.dumps(data)); return None
            except (KeyError, ValueError): data.pop(key,None); atomic_write(self.path,json.dumps(data)); return None
            return item.get('value')
    def put(self,key,value):
        if not key:return value
        with self._access():
            data=self._load(); data[key]={'created_at':datetime.now(timezone.utc).isoformat(),'value':value}; atomic_write(self.path,json.dumps(data,ensure_ascii=False)); return value
