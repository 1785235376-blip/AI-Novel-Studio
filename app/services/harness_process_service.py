from __future__ import annotations
import os, subprocess, shlex
from datetime import datetime, timezone

class HarnessProcessService:
    def __init__(self): self.process=None; self.last_action=None; self.last_action_at=None
    def status(self):
        running=bool(self.process and self.process.poll() is None)
        return {"running":running,"pid":self.process.pid if running else None,"last_action":self.last_action,"last_action_at":self.last_action_at}
    def start(self):
        if self.status()["running"]: return self.status()
        command=os.getenv("DEEPSEEK_HARNESS_COMMAND", "npx @deepseek-ai/dsh web --no-open")
        argv=shlex.split(command, posix=False)
        if not argv: raise RuntimeError("Harness command is empty")
        self.process=subprocess.Popen(argv, shell=False, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        self.last_action="started"; self.last_action_at=datetime.now(timezone.utc).isoformat()
        return self.status()
    def stop(self):
        if self.process and self.process.poll() is None: self.process.terminate()
        self.last_action="stopped"; self.last_action_at=datetime.now(timezone.utc).isoformat()
        result=self.status(); self.process=None; return result
