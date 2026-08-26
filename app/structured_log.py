from __future__ import annotations
import json,logging,threading
from datetime import datetime,timezone
from pathlib import Path
from .config import settings

class RuntimeLogger:
    allowed={"request_id","generation_id","novel_id","chapter_id","agent","provider","model","latency_ms","input_tokens","output_tokens","cost","fallback","status","error"}
    def __init__(self): self.path=settings.root/"logs/runtime.jsonl"; self.lock=threading.Lock(); self.write_failures=0
    def write(self,**values):
        record={"timestamp":datetime.now(timezone.utc).isoformat(),**{k:v for k,v in values.items() if k in self.allowed and v is not None}}
        try:
            self.path.parent.mkdir(parents=True,exist_ok=True)
            with self.lock:
                with self.path.open("a",encoding="utf-8") as f:f.write(json.dumps(record,ensure_ascii=False)+"\n")
        except OSError:
            self.write_failures+=1
runtime_log=RuntimeLogger()
