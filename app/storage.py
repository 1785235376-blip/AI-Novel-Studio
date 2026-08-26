from __future__ import annotations
import json, os, tempfile, time
from pathlib import Path

def atomic_write(path:Path, content:str)->None:
    path.parent.mkdir(parents=True,exist_ok=True)
    fd,tmp=tempfile.mkstemp(dir=path.parent,prefix=path.name+".",suffix=".tmp",text=True)
    try:
        with os.fdopen(fd,"w",encoding="utf-8",newline="\n") as f: f.write(content); f.flush(); os.fsync(f.fileno())
        for attempt in range(5):
            try:
                os.replace(tmp,path)
                break
            except PermissionError:
                if attempt == 4:
                    raise
                time.sleep(.02 * (attempt + 1))
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def append_pending(root:Path,item:dict)->Path:
    target=root/"pending_canon"/(item["id"]+".json"); atomic_write(target,json.dumps(item,ensure_ascii=False,indent=2)); return target
