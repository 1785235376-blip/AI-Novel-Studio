from app import asset_worker_config as config

def test_worker_config_is_persisted_and_clamped(monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_WORKER_CONFIG_PATH", str(tmp_path / "worker.json"))
    saved=config.save(limit=999, interval_seconds=0, timeout_seconds=0, execute=True)
    assert saved == {"limit":100,"interval_seconds":0.1,"timeout_seconds":1,"execute":True}
    assert config.load() == saved
