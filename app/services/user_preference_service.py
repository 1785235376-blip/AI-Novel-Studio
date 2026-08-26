from __future__ import annotations
import json, os, tempfile
from pathlib import Path

class UserPreferenceService:
    def __init__(self, root: Path):
        self.path = root / "user_preferences.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)
    def _load(self):
        try: return json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, json.JSONDecodeError): return {"enabled": True, "share_enabled": False, "harness_enabled": False, "items": {}}
    def _save(self, value):
        fd, name = tempfile.mkstemp(prefix="user-preferences-", suffix=".json", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle: json.dump(value, handle, ensure_ascii=False, indent=2)
            os.replace(name, self.path)
        finally:
            if os.path.exists(name): os.unlink(name)
    def list(self):
        value=self._load(); return {"enabled": bool(value.get("enabled", True)), "share_enabled": bool(value.get("share_enabled", False)), "harness_enabled": bool(value.get("harness_enabled", False)), "items": list(value.get("items", {}).values())}
    def upsert(self, key, content, source="explicit", confidence=1.0):
        value=self._load(); value.setdefault("items", {})[key]={"key":key,"content":content,"source":source,"confidence":max(0,min(1,float(confidence)))}; self._save(value); return value["items"][key]
    def delete(self, key):
        value=self._load(); value.setdefault("items", {}).pop(key, None); self._save(value)
    def set_enabled(self, enabled):
        value=self._load(); value["enabled"]=bool(enabled); self._save(value); return bool(value["enabled"])
    def set_share_enabled(self, enabled):
        value=self._load(); value["share_enabled"]=bool(enabled); self._save(value); return bool(value["share_enabled"])
    def set_harness_enabled(self, enabled):
        value=self._load(); value["harness_enabled"]=bool(enabled); self._save(value); return bool(value["harness_enabled"])
