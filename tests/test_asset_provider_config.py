import json

import pytest

from app import asset_provider_config as config


def test_save_and_load_uses_atomic_file(monkeypatch, tmp_path):
    target = tmp_path / "providers.json"
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(target))
    saved = config.save("studio", "https://example.test/v1/", "image-model")
    assert saved == {"endpoint": "https://example.test/v1", "default_model": "image-model"}
    assert config.load()["studio"] == saved
    assert json.loads(target.read_text(encoding="utf-8"))["studio"] == saved
    assert not list(tmp_path.glob("*.tmp"))


@pytest.mark.parametrize("endpoint", ["ftp://example.test", "example.test/v1", ""])
def test_save_rejects_non_http_endpoint(monkeypatch, tmp_path, endpoint):
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "providers.json"))
    with pytest.raises(ValueError):
        config.save("studio", endpoint, "model")


def test_delete_custom_provider(monkeypatch, tmp_path):
    monkeypatch.setenv("ASSET_PROVIDER_CONFIG_PATH", str(tmp_path / "providers.json"))
    config.save("studio", "https://example.test/v1", "model")
    assert config.delete("studio") is True
    assert config.delete("studio") is False
    assert config.load() == {}
