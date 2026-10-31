"""Install declarative JSON bundles without loading or executing plugin code.

Atomic directory swaps retain one previous version. Every transition requires
fresh manifest review; a rollback never restores execution or permission grants.
"""
from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
import threading
from pathlib import Path
from typing import Callable

from .plugin_contracts import (MAX_MANIFEST_BYTES, MAX_RESOURCE_BYTES, MAX_TOTAL_RESOURCE_BYTES,
                               PLUGIN_RESOURCE_HASH_MISMATCH, PluginContractError, parse_plugin_manifest)
from .plugin_discovery import load_plugin_package, packages_for_plugin_id, resolve_plugin_file, unique_package_for_plugin_id


class PluginPackageManager:
    def __init__(self, root: Path):
        self.root=Path(root)
        self.lock=threading.RLock()

    def _area(self, name: str) -> Path:
        path=self.root.parent / name
        if path.is_symlink():raise ValueError("plugin storage symlink is forbidden")
        path.mkdir(parents=True,exist_ok=True)
        return path

    def _checked_root(self):
        if self.root.is_symlink():raise ValueError("plugin storage symlink is forbidden")
        self.root.mkdir(parents=True,exist_ok=True)

    def install(self, bundle: dict, *, update: bool = False, register: Callable | None = None) -> dict:
        if set(bundle) != {"manifest", "resources"}:raise ValueError("bundle must contain only manifest and resources")
        manifest=parse_plugin_manifest(bundle["manifest"])
        encoded=json.dumps(bundle["manifest"],ensure_ascii=False).encode()
        if len(encoded)>MAX_MANIFEST_BYTES:raise ValueError("manifest exceeds size limit")
        resources=bundle["resources"]
        if not isinstance(resources,dict) or set(resources)!={item.relative_path for item in manifest.resources}:
            raise ValueError("bundle resources do not match manifest")
        if "manifest.json" in resources:raise ValueError("resource cannot replace manifest")
        payloads={}
        for resource in manifest.resources:
            value=resources[resource.relative_path]
            if not isinstance(value,str):raise ValueError("resource must be a UTF-8 JSON string")
            raw=value.encode("utf-8")
            if len(raw)>MAX_RESOURCE_BYTES:raise ValueError("resource exceeds size limit")
            if hashlib.sha256(raw).hexdigest()!=resource.sha256:raise PluginContractError(PLUGIN_RESOURCE_HASH_MISMATCH)
            payloads[resource.relative_path]=raw
        if sum(map(len,payloads.values()))>MAX_TOTAL_RESOURCE_BYTES:raise ValueError("package exceeds size limit")
        with self.lock:
            self._checked_root()
            stage=Path(tempfile.mkdtemp(prefix="package-",dir=self._area("plugin_staging")))
            target=self.root / manifest.id
            backup=self._area("plugin_previous") / manifest.id
            swapped=False
            had_previous=False
            try:
                (stage/"manifest.json").write_bytes(encoded)
                for relative,raw in payloads.items():
                    path=resolve_plugin_file(stage,relative)
                    path.parent.mkdir(parents=True,exist_ok=True)
                    path.write_bytes(raw)
                load_plugin_package(stage)
                if update:
                    target,old=unique_package_for_plugin_id(manifest.id,self.root)
                    if target.is_symlink() or backup.is_symlink():raise ValueError("plugin package symlink is forbidden")
                    # Retain previous versions using recoverable archival directories.
                    if backup.exists():
                        archive=Path(tempfile.mkdtemp(prefix=manifest.id+"-",dir=self._area("plugin_archive")))
                        os.replace(backup,archive/"package")
                    os.replace(target,backup)
                    had_previous=True
                elif target.exists() or packages_for_plugin_id(manifest.id,self.root):raise FileExistsError(manifest.id)
                os.replace(stage,target)
                swapped=True
                if register:register(manifest)
            except Exception:
                if swapped:
                    failed=Path(tempfile.mkdtemp(prefix="failed-",dir=self._area("plugin_archive")))
                    os.replace(target,failed/"package")
                if had_previous:os.replace(backup,target)
                raise
            finally:
                if stage.exists():shutil.rmtree(stage)
            return {"id":manifest.id,"plugin_version":manifest.version,"operation":"UPDATED" if update else "INSTALLED",
                    "execution_supported":False,"permissions_reset":True,"rollback_available":backup.exists()}

    def rollback(self, plugin_id: str, *, register: Callable | None = None) -> dict:
        with self.lock:
            target,current=unique_package_for_plugin_id(plugin_id,self.root)
            backup=self._area("plugin_previous") / current.id
            if target.is_symlink() or backup.is_symlink():raise ValueError("plugin package symlink is forbidden")
            previous,_=load_plugin_package(backup)
            if previous.id!=plugin_id:raise ValueError("rollback identity mismatch")
            archive=Path(tempfile.mkdtemp(prefix=plugin_id+"-",dir=self._area("plugin_archive")))/"package"
            os.replace(target,archive)
            try:
                os.replace(backup,target)
                if register:register(previous)
            except Exception:
                if target.exists():os.replace(target,backup)
                os.replace(archive,target)
                raise
            return {"id":plugin_id,"operation":"ROLLED_BACK","plugin_version":previous.version,"execution_supported":False,"permissions_reset":True}

    def remove(self, plugin_id: str) -> dict:
        with self.lock:
            target,manifest=unique_package_for_plugin_id(plugin_id,self.root)
            if target.is_symlink():raise ValueError("plugin package symlink is forbidden")
            archive=Path(tempfile.mkdtemp(prefix=manifest.id+"-",dir=self._area("plugin_archive")))
            os.replace(target,archive/"package")
            return {"id":plugin_id,"operation":"REMOVED","recoverable":True,"execution_supported":False}
