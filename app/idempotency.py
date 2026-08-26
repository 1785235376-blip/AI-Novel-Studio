from __future__ import annotations
import json, threading
from datetime import datetime, timezone, timedelta
from pathlib import Path
from .storage import atomic_write

class IdempotencyStore:
    def __init__(self, path: Path, ttl_hours: int = 24):
        self.path=path; self.ttl=timedelta(hours=ttl_hours); self.lock=threading.Lock()
    def _load(self):
        try:return json.loads(self.path.read_text(encoding='utf-8'))
        except (FileNotFoundError, json.JSONDecodeError):return {}
    def get(self,key):
        with self.lock:
            data=self._load(); item=data.get(key)
            if not item:return None
            try:
                if datetime.now(timezone.utc)-datetime.fromisoformat(item['created_at']) > self.ttl:
                    data.pop(key,None); atomic_write(self.path,json.dumps(data)); return None
            except (KeyError, ValueError): data.pop(key,None); atomic_write(self.path,json.dumps(data)); return None
            return item.get('value')
    def put(self,key,value):
        if not key:return value
        with self.lock:
            data=self._load(); data[key]={'created_at':datetime.now(timezone.utc).isoformat(),'value':value}; atomic_write(self.path,json.dumps(data,ensure_ascii=False)); return value
