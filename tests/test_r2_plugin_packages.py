import hashlib
import json

import pytest

from app.plugin_package_manager import PluginPackageManager
from app.plugin_contracts import PluginContractError
from app.plugin_discovery import load_plugin_package


def bundle(version="1.0.0"):
    text=json.dumps({"name":"Synthetic rules","version":version})
    return {"manifest":{"id":"synthetic-pack","name":"Synthetic","version":version,"capabilities":["writing_tool"],"requested_permissions":[],"resources":[{"kind":"writing_presets","relative_path":"presets.json","sha256":hashlib.sha256(text.encode()).hexdigest(),"media_type":"application/json"}]},"resources":{"presets.json":text}}


def test_install_update_rollback_remove_never_enables_execution(tmp_path):
    manager=PluginPackageManager(tmp_path/"plugins")
    installed=manager.install(bundle())
    assert installed["execution_supported"] is False
    updated=manager.install(bundle("2.0.0"),update=True)
    assert updated["rollback_available"]
    assert load_plugin_package(tmp_path/"plugins"/"synthetic-pack")[0].version=="2.0.0"
    rolled=manager.rollback("synthetic-pack")
    assert rolled["plugin_version"]=="1.0.0" and rolled["permissions_reset"]
    removed=manager.remove("synthetic-pack")
    assert removed["recoverable"] and not (tmp_path/"plugins"/"synthetic-pack").exists()
    assert list((tmp_path/"plugin_archive").glob("*/package/manifest.json"))


def test_failed_update_rolls_back_directory_and_preserves_original(tmp_path):
    manager=PluginPackageManager(tmp_path/"plugins")
    manager.install(bundle())
    def reject(_):raise ValueError("registration rejected")
    with pytest.raises(ValueError):manager.install(bundle("2.0.0"),update=True,register=reject)
    assert load_plugin_package(tmp_path/"plugins"/"synthetic-pack")[0].version=="1.0.0"


@pytest.mark.parametrize("mutate", [
    lambda b: b["manifest"].update(entrypoint="run.py"),
    lambda b: b["resources"].update({"../escape.json":"{}"}),
    lambda b: b["resources"].update({"presets.json":"{}"}),
    lambda b: b["manifest"]["resources"][0].update(relative_path="../escape.json"),
])
def test_malformed_or_executable_package_cannot_change_installed_files(tmp_path,mutate):
    manager=PluginPackageManager(tmp_path/"plugins")
    manager.install(bundle())
    bad=bundle("2.0.0");mutate(bad)
    with pytest.raises((ValueError,PluginContractError)):manager.install(bad,update=True)
    assert load_plugin_package(tmp_path/"plugins"/"synthetic-pack")[0].version=="1.0.0"


def test_plugin_root_symlink_is_rejected(tmp_path):
    other=tmp_path/"outside";other.mkdir()
    root=tmp_path/"plugins";root.symlink_to(other,target_is_directory=True)
    with pytest.raises(ValueError):PluginPackageManager(root).install(bundle())
    assert not list(other.iterdir())
