from __future__ import annotations

import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.packaging.packaged_processes import PackagedProcessConfig, PackagedProcessFactory
from app.packaging.paths import WindowsPackagingPaths
from app import structured_log


def inventory(root):
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*") if path.is_file()
    }


@pytest.fixture
def packaged_config(tmp_path):
    paths = WindowsPackagingPaths.resolve(
        local_app_data=tmp_path / "本地 应用目录",
        user_profile=tmp_path / "用户 文档目录",
    )
    backend = paths.application / "Backend"
    backend.mkdir(parents=True)
    (backend / "package-sentinel.txt").write_text("原始包文件，不可改变", encoding="utf-8")
    layout = SimpleNamespace(
        application=paths.application, backend=backend,
        python=paths.application / "Runtime/Python/python.exe",
        frontend_dist=paths.application / "Frontend/dist",
    )
    return PackagedProcessConfig(layout=layout, paths=paths, version="0.7.0")


def configure_logger(monkeypatch, config, *, packaged):
    monkeypatch.setattr(structured_log, "settings", SimpleNamespace(
        root=config.layout.backend, enable_packaged_runtime=packaged,
    ))
    monkeypatch.setenv("PACKAGED_LOGS_ROOT", str(config.paths.logs))


def test_packaged_child_receives_authoritative_existing_logs_root(packaged_config, monkeypatch):
    config = packaged_config
    monkeypatch.setenv("PACKAGED_LOGS_ROOT", str(config.paths.application / "inherited-wrong-logs"))
    observed = {}

    def spawn(argv, **kwargs):
        observed.update(argv=argv, **kwargs)
        return SimpleNamespace()

    monkeypatch.setattr("app.packaging.packaged_processes.subprocess.Popen", spawn)
    monkeypatch.setattr("app.packaging.packaged_processes.PackagedManagedChild", lambda **kwargs: kwargs)
    factory = PackagedProcessFactory(config, SimpleNamespace())
    before = inventory(config.paths.application)
    try:
        factory._start_backend(54321, SimpleNamespace(runtime_instance_id="isolated-log-test"))
        env = observed["env"]
        assert env["PACKAGED_LOGS_ROOT"] == str(config.paths.logs)
        assert env["PROJECT_ROOT"] == str(config.layout.backend)
        assert env["NOVEL_DATA_PATH"] == str(config.paths.novel_data)
        assert env["ENABLE_PACKAGED_RUNTIME"] == "true"
        assert env["PACKAGED_WINDOWS_MODE"] == "true"
        assert observed["cwd"] == config.layout.backend
        assert inventory(config.paths.application) == before
    finally:
        if observed.get("stdout"):
            observed["stdout"].close()


def test_packaged_jsonl_cjk_space_roundtrip_does_not_mutate_application(packaged_config, monkeypatch):
    config = packaged_config
    configure_logger(monkeypatch, config, packaged=True)
    before = inventory(config.paths.application)
    logger = structured_log.RuntimeLogger()

    logger.write(generation_id="真实保存记录-1", status="COMPLETED", input_tokens=10, output_tokens=20)
    logger.write(generation_id="真实保存记录-2", status="FAILED", error="TEST_ERROR")

    expected = config.paths.logs / "runtime.jsonl"
    assert logger.path == expected
    assert logger.write_failures == 0
    assert inventory(config.paths.application) == before
    records = [json.loads(line) for line in expected.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 2
    assert records[0]["generation_id"] == "真实保存记录-1"
    assert records[0]["input_tokens"] == 10 and records[0]["output_tokens"] == 20
    assert records[1]["generation_id"] == "真实保存记录-2" and records[1]["error"] == "TEST_ERROR"
    assert all(record["timestamp"] for record in records)


def test_development_default_path_ignores_packaged_only_logs_hint(packaged_config, monkeypatch):
    config = packaged_config
    configure_logger(monkeypatch, config, packaged=False)
    logger = structured_log.RuntimeLogger()
    logger.write(request_id="development-log", status="COMPLETED")
    assert logger.path == config.layout.backend / "logs/runtime.jsonl"
    assert json.loads(logger.path.read_text(encoding="utf-8"))["request_id"] == "development-log"
    assert not (config.paths.logs / "runtime.jsonl").exists()


def test_packaged_log_keeps_secret_and_prompt_fields_out(packaged_config, monkeypatch):
    configure_logger(monkeypatch, packaged_config, packaged=True)
    logger = structured_log.RuntimeLogger()
    logger.write(
        request_id="privacy-test", status="COMPLETED",
        prompt="TEST_ONLY_PRIVATE_PROMPT", secret="TEST_ONLY_PRIVATE_SECRET",
        api_key="TEST_ONLY_PRIVATE_KEY", document="TEST_ONLY_PRIVATE_DOCUMENT",
    )
    text = logger.path.read_text(encoding="utf-8")
    assert json.loads(text).keys() == {"timestamp", "request_id", "status"}
    assert all(value not in text for value in (
        "TEST_ONLY_PRIVATE_PROMPT", "TEST_ONLY_PRIVATE_SECRET",
        "TEST_ONLY_PRIVATE_KEY", "TEST_ONLY_PRIVATE_DOCUMENT",
    ))


def test_packaged_logs_write_error_preserves_original_failure_counter(packaged_config, monkeypatch):
    config = packaged_config
    configure_logger(monkeypatch, config, packaged=True)
    config.paths.logs.parent.mkdir(parents=True, exist_ok=True)
    config.paths.logs.write_text("blocked directory fixture", encoding="utf-8")
    before = inventory(config.paths.application)
    logger = structured_log.RuntimeLogger()
    logger.write(request_id="unwritable-log")
    assert logger.write_failures == 1
    assert inventory(config.paths.application) == before
