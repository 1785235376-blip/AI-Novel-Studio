import json, os
from pathlib import Path
from .storage import atomic_write

DEFAULTS = {"limit": 10, "interval_seconds": 5.0, "timeout_seconds": 3600, "execute": False}

def config_path():
    return Path(os.getenv("ASSET_WORKER_CONFIG_PATH", str(Path.home()/".ai-novel-studio"/"asset-worker.json")))

def load():
    try:
        data = json.loads(config_path().read_text(encoding="utf-8"))
        return {**DEFAULTS, **{k: data[k] for k in DEFAULTS if k in data}}
    except (OSError, ValueError, TypeError):
        return dict(DEFAULTS)

def save(**values):
    current = load()
    if "limit" in values: current["limit"] = max(1, min(100, int(values["limit"])))
    if "interval_seconds" in values: current["interval_seconds"] = max(0.1, float(values["interval_seconds"]))
    if "timeout_seconds" in values: current["timeout_seconds"] = max(1, int(values["timeout_seconds"]))
    if "execute" in values: current["execute"] = bool(values["execute"])
    atomic_write(config_path(), json.dumps(current, ensure_ascii=False, indent=2))
    return current
