"""Harness safety contracts only: no native host, model inference or download.

Process, metadata and mounted-API doubles below test orchestration. Their
simulated receipts are not real-inference acceptance evidence.
"""
from collections import deque
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import run_v2_real_text_check as runner


@pytest.fixture(autouse=True)
def prohibit_unmocked_external_work(monkeypatch):
    def forbidden(*_args, **_kwargs):
        raise AssertionError("HARNESS_CONTRACT_MUST_NOT_START_HOST_OR_NETWORK")

    for name in ("Popen", "run", "check_output"):
        monkeypatch.setattr(runner.subprocess, name, forbidden)
    monkeypatch.setattr(runner.urllib.request, "build_opener", forbidden)
    monkeypatch.setattr(runner.socket, "socket", forbidden)


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    server = tmp_path / "verified-server"
    server.write_bytes(b"unit-test executable placeholder; never run\n")
    server.chmod(0o700)
    model = tmp_path / "verified-model.gguf"
    model.write_bytes(b"unit-test model placeholder; never loaded\n")
    probe = Mock()
    probe.connect_ex.return_value = 111
    socket = Mock()
    socket.__enter__ = Mock(return_value=probe)
    socket.__exit__ = Mock(return_value=False)
    factory = Mock(return_value=socket)
    monkeypatch.setattr(runner.socket, "socket", factory)
    return SimpleNamespace(server=server, model=model, sha=runner.sha256_file(model),
                           port=18080, probe=probe, socket_factory=factory)


def validate(inputs, **overrides):
    values = {"server": inputs.server, "model": inputs.model,
              "expected_sha": inputs.sha, "port": inputs.port}
    values.update(overrides)
    return runner.validated_inputs(**values)


def test_sha256_streams_the_full_input(tmp_path):
    payload = b"0123456789abcdef" * 131_073
    file = tmp_path / "hash-input"
    file.write_bytes(payload)
    assert runner.sha256_file(file) == hashlib.sha256(payload).hexdigest()


@pytest.mark.parametrize("sha", ["", "0" * 63, "0" * 65, "A" * 64, "g" * 64, "0" * 64 + "\n"])
def test_inputs_require_explicit_lowercase_sha256(inputs, sha):
    with pytest.raises(ValueError, match="^EXPLICIT_MODEL_SHA256_REQUIRED$"):
        validate(inputs, expected_sha=sha)
    inputs.socket_factory.assert_not_called()


@pytest.mark.parametrize("name", ["server", "model"])
@pytest.mark.parametrize("kind", ["relative", "missing", "directory", "symlink", "linked_parent"])
def test_inputs_reject_non_owned_file_paths(inputs, tmp_path, name, kind):
    original = getattr(inputs, name)
    path = tmp_path / (name + "-invalid")
    if kind == "relative":
        path = Path(original.name)
    elif kind == "directory":
        path.mkdir()
    elif kind == "symlink":
        path.symlink_to(original)
    elif kind == "linked_parent":
        path.symlink_to(tmp_path, target_is_directory=True)
        path = path / original.name
    expected = "LINKED_INPUT_PATH_REJECTED" if kind == "linked_parent" else "VERIFIED_ABSOLUTE_INPUT_FILE_REQUIRED"
    with pytest.raises(ValueError, match="^" + expected + "$"):
        validate(inputs, **{name: path})
    inputs.socket_factory.assert_not_called()


def test_inputs_require_executable_server(inputs):
    inputs.server.chmod(0o600)
    with pytest.raises(ValueError, match="^VERIFIED_EXECUTABLE_REQUIRED$"):
        validate(inputs)
    inputs.socket_factory.assert_not_called()


@pytest.mark.parametrize("port", [-1, 0, 80, 1023, 65536])
def test_inputs_reject_privileged_or_invalid_ports(inputs, port):
    with pytest.raises(ValueError, match="^UNPRIVILEGED_LOOPBACK_PORT_REQUIRED$"):
        validate(inputs, port=port)
    inputs.socket_factory.assert_not_called()


@pytest.mark.parametrize("port", [1024, 18080, 65535])
def test_inputs_probe_only_requested_loopback_port(inputs, port):
    validate(inputs, port=port)
    inputs.probe.connect_ex.assert_called_once_with(("127.0.0.1", port))


def test_inputs_reject_model_hash_mismatch_before_port_probe(inputs):
    with pytest.raises(ValueError, match="^MODEL_SHA256_MISMATCH$"):
        validate(inputs, expected_sha="0" * 64)
    inputs.socket_factory.assert_not_called()


def test_inputs_never_reuse_an_occupied_port(inputs):
    inputs.probe.connect_ex.return_value = 0
    with pytest.raises(ValueError, match="^OWNED_PORT_ALREADY_IN_USE$"):
        validate(inputs)


def test_child_environment_is_allowlisted_and_all_storage_is_isolated(tmp_path, monkeypatch):
    inherited = {"PATH": "/test/toolchain", "LANG": "C.UTF-8", "LC_ALL": "C", "SYSTEMROOT": "/system",
                 "HOME": "/private/home", "NOVEL_DATA_PATH": "/private/manuscripts", "OPENAI_API_KEY": "fake-secret",
                 "HF_TOKEN": "fake-secret", "AWS_ACCESS_KEY_ID": "fake-secret", "DATABASE_URL": "fake-secret",
                 "HTTP_PROXY": "http://proxy.invalid", "https_proxy": "http://proxy.invalid", "ALL_PROXY": "http://proxy.invalid",
                 "PYTHONPATH": "/untrusted", "PYTHONSTARTUP": "/untrusted/startup", "LD_PRELOAD": "/untrusted/lib.so",
                 "COLLABORATION_DEV_SESSIONS_JSON": "private-session", "MOCK_PROVIDER": "true", "ENABLE_CLOUD": "true"}
    monkeypatch.setattr(runner.os, "environ", inherited)
    env = runner.isolated_environment(tmp_path)
    assert inherited["OPENAI_API_KEY"] == "fake-secret"
    assert {key: env[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")} == {
        key: inherited[key] for key in ("PATH", "LANG", "LC_ALL", "SYSTEMROOT")}
    assert not (set(inherited) - {"PATH", "LANG", "LC_ALL", "SYSTEMROOT", "HOME", "NOVEL_DATA_PATH",
                                  "COLLABORATION_DEV_SESSIONS_JSON", "MOCK_PROVIDER", "ENABLE_CLOUD"}) & set(env)
    for key, folder in {"HOME": "home", "USERPROFILE": "home", "XDG_DATA_HOME": "data", "XDG_CACHE_HOME": "cache",
                        "XDG_CONFIG_HOME": "config", "APPDATA": "local", "LOCALAPPDATA": "local", "TMPDIR": "tmp"}.items():
        assert env[key] == str(tmp_path / folder)
        assert Path(env[key]).is_dir()
    assert env["NOVEL_DATA_PATH"] == str(tmp_path / "novel-data")
    assert env["PROJECT_ROOT"] == str(runner.REPO)
    assert env["V2_REAL_TEXT_CHECK_ROOT"] == str(tmp_path)
    assert env["STORAGE_BACKEND"] == "file"
    assert env["CREDENTIAL_VAULT_BACKEND"] == "memory"
    assert env["CREDENTIAL_VAULT_ALLOW_MEMORY_FALLBACK"] == "true"
    assert env["EXPERIMENTAL_FEATURES"] == runner.FLAGS
    assert env["CREATION_PROFILE"] == "LOCAL_ONLY"
    assert env["COLLABORATION_DEV_SESSIONS_JSON"] == ""
    for key in ("MOCK_PROVIDER", "ENABLE_CLOUD", "ENABLE_PROVIDER_FALLBACK", "ENABLE_COLLABORATION_RUNTIME",
                "ENABLE_PACKAGED_RUNTIME", "V1_ACCEPTANCE_MODE"):
        assert env[key] == "false"
    assert env["HF_HUB_OFFLINE"] == env["TRANSFORMERS_OFFLINE"] == "1"


def test_complete_parent_created_environment_passes_child_guard(tmp_path, monkeypatch):
    env = runner.isolated_environment(tmp_path)
    monkeypatch.setattr(runner.os, "environ", env)
    runner.validate_isolated_environment(tmp_path)


@pytest.mark.parametrize("key", tuple(runner.required_child_environment(Path("/owned-test-root"))))
@pytest.mark.parametrize("mode", ["missing", "changed"])
def test_child_guard_requires_every_safe_flag_path_and_ownership_marker(tmp_path, monkeypatch, key, mode):
    env = runner.isolated_environment(tmp_path)
    if mode == "missing":
        del env[key]
    else:
        env[key] = "unowned-or-unsafe-value"
    monkeypatch.setattr(runner.os, "environ", env)
    with pytest.raises(ValueError, match="^ISOLATED_CHILD_ENVIRONMENT_REQUIRED$"):
        runner.validate_isolated_environment(tmp_path)


@pytest.mark.parametrize("key", ["OPENAI_API_KEY", "HF_TOKEN", "DATABASE_URL", "HTTP_PROXY", "https_proxy", "ALL_PROXY",
                                 "LD_PRELOAD", "PYTHONPATH", "UNKNOWN_PROVIDER_SETTING"])
def test_child_guard_rejects_inherited_secrets_proxies_and_unknown_configuration_without_logging(
        tmp_path, monkeypatch, key):
    env = runner.isolated_environment(tmp_path)
    env[key] = "private-value-must-not-appear-in-errors"
    monkeypatch.setattr(runner.os, "environ", env)
    with pytest.raises(ValueError, match="^UNEXPECTED_CHILD_ENVIRONMENT$") as error:
        runner.validate_isolated_environment(tmp_path)
    assert "private-value" not in str(error.value) and key not in str(error.value)


@pytest.mark.parametrize("folder", runner.OWNED_ENV_FOLDERS)
@pytest.mark.parametrize("kind", ["missing", "linked"])
def test_child_guard_requires_all_owned_real_directories(tmp_path, monkeypatch, folder, kind):
    env = runner.isolated_environment(tmp_path)
    path = tmp_path / folder
    path.rmdir()
    if kind == "linked":
        elsewhere = tmp_path / "elsewhere"
        elsewhere.mkdir()
        path.symlink_to(elsewhere, target_is_directory=True)
    monkeypatch.setattr(runner.os, "environ", env)
    with pytest.raises(ValueError, match="^OWNED_CHILD_DIRECTORIES_REQUIRED$"):
        runner.validate_isolated_environment(tmp_path)


def test_runtime_argv_is_cpu_only_bounded_offline_and_has_no_download_route(inputs):
    argv = runner.runtime_argv(inputs.server, inputs.model, inputs.port)
    assert argv[0] == str(inputs.server)
    expected = {"-m": str(inputs.model), "--alias": runner.ALIAS, "--host": "127.0.0.1", "--port": str(inputs.port),
                "--device": "none", "--n-gpu-layers": "0", "--ctx-size": "2048", "--parallel": "1",
                "--threads": "2", "--threads-batch": "2", "--batch-size": "128", "--ubatch-size": "128",
                "--cache-ram": "0", "--cors-origins": f"http://127.0.0.1:{inputs.port}"}
    switches = {"--offline", "--no-ui", "--no-agent", "--no-ui-mcp-proxy", "--no-cors-credentials"}
    position = 1
    parsed = {}
    present = set()
    while position < len(argv):
        flag = argv[position]
        assert flag not in parsed and flag not in present
        if flag in switches:
            present.add(flag)
            position += 1
        else:
            assert flag in expected
            parsed[flag] = argv[position + 1]
            position += 2
    assert parsed == expected and present == switches
    assert not {"--model-url", "--hf-repo", "-hf", "--hf-file", "--hf-token", "--rpc"} & set(argv)


def test_source_identity_uses_shared_snapshot_excluding_generated_runtime_outputs(tmp_path, monkeypatch):
    sources = {"app/source.py": b"first source\n", "scripts/new file.py": b"untracked source\n",
               "frontend/src/view.tsx": b"frontend source\n",
               "tests/fixtures/tracked/chapter_identity.json": b"tracked source fixture\n"}
    outputs = {".runtime/acceptance.json", "docs/delivery/v2-development/run.json", "app/__pycache__/source.pyc",
               "tests/fixtures/generated/chapter_identity.json", "tests/fixtures/generated/.workspace-mutation-locks/lock"}
    for name, content in {**sources, **{name: b"generated output" for name in outputs}}.items():
        file = tmp_path / name
        file.parent.mkdir(parents=True, exist_ok=True)
        file.write_bytes(content)
    monkeypatch.setattr(runner, "REPO", tmp_path)
    calls = []

    def git(args, **kwargs):
        calls.append((args, kwargs))
        assert args == ["git", "rev-parse", "HEAD"]
        return "test-git-head\n"

    tracked = Mock(return_value=SimpleNamespace(returncode=0,
        stdout=b"app/source.py\0tests/fixtures/tracked/chapter_identity.json\0"))
    monkeypatch.setattr(runner.subprocess, "run", tracked)
    monkeypatch.setattr(runner.subprocess, "check_output", git)
    identity = runner.source_identity()
    expected = {name: runner.sha256_file(tmp_path / name) for name in sources}
    assert identity == {"git_head": "test-git-head", "input_files": expected,
                        "sha256": hashlib.sha256(json.dumps(expected, sort_keys=True, separators=(",", ":")).encode()).hexdigest()}
    tracked.assert_called_once_with(["git", "ls-files", "-z"], cwd=tmp_path,
                                    stdout=runner.subprocess.PIPE, stderr=runner.subprocess.DEVNULL)
    assert all(kwargs["cwd"] == tmp_path for _, kwargs in calls)


def metadata_response(monkeypatch, data):
    response = Mock()
    response.read.return_value = data
    response.__enter__ = Mock(return_value=response)
    response.__exit__ = Mock(return_value=False)
    opener = Mock()
    opener.open.return_value = response
    factory = Mock(return_value=opener)
    monkeypatch.setattr(runner.urllib.request, "build_opener", factory)
    return response, opener, factory


def test_metadata_probe_disables_proxies_and_redirects_and_bounds_read_and_timeout(monkeypatch):
    response, opener, factory = metadata_response(monkeypatch, b'{"status":"ok"}')
    assert runner.native_json("http://127.0.0.1:18080", "/health") == {"status": "ok"}
    opener.open.assert_called_once_with("http://127.0.0.1:18080/health", timeout=2)
    response.read.assert_called_once_with(256_001)
    proxy, redirect = factory.call_args.args
    assert proxy.proxies == {}
    assert redirect.redirect_request(None, None, 302, "redirect", {}, "https://external.invalid") is None


def test_metadata_probe_rejects_oversized_content(monkeypatch):
    metadata_response(monkeypatch, b" " * 256_001)
    with pytest.raises(ValueError, match="^NATIVE_METADATA_TOO_LARGE$"):
        runner.native_json("http://127.0.0.1:18080", "/props")


class HarnessProcess:
    """No OS process is started; records only owned-process control calls."""

    def __init__(self, waits=(), returncode=None):
        self.pid = 123456789
        self.returncode = returncode
        self.waits = deque(waits)
        self.calls = []

    def poll(self):
        return self.returncode

    def wait(self, timeout):
        self.calls.append(("wait", timeout))
        outcome = self.waits.popleft() if self.waits else (self.returncode or 0)
        if isinstance(outcome, BaseException):
            raise outcome
        self.returncode = outcome
        return outcome

    def terminate(self):
        self.calls.append(("terminate",))

    def kill(self):
        self.calls.append(("kill",))


@pytest.fixture
def execute_harness(tmp_path, inputs, monkeypatch):
    root = tmp_path / "execute-output"
    root.mkdir()
    process = HarnessProcess(waits=(0,))
    launch = Mock(return_value=process)
    version = Mock(return_value=SimpleNamespace(stdout="unit-test version", stderr=""))
    def simulated_acceptance(_root, _server, _model, _port, outcome):
        outcome["real_inference"] = "PASS"
        return {"harness_test_double": True}

    acceptance = Mock(side_effect=simulated_acceptance)
    identity = Mock(return_value={"git_head": "same-test-head", "input_files": {}, "sha256": "same-test-sha"})
    handlers = Mock()
    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setattr(runner.subprocess, "run", version)
    monkeypatch.setattr(runner, "source_identity", identity)
    monkeypatch.setattr(runner, "native_json", lambda endpoint, path: {"status": "ok"})
    monkeypatch.setattr(runner, "mounted_acceptance", acceptance)
    monkeypatch.setattr(runner.signal, "signal", handlers)
    return SimpleNamespace(root=root, inputs=inputs, process=process, launch=launch, version=version,
                           acceptance=acceptance, identity=identity, handlers=handlers)


def execute(harness):
    inputs = harness.inputs
    return runner.execute(harness.root, inputs.server, inputs.model, inputs.sha, inputs.port)


def receipt(harness):
    return json.loads((harness.root / "acceptance.json").read_text())


def test_simulated_success_stops_only_its_owned_process_and_retains_artifacts(execute_harness):
    harness = execute_harness
    execute(harness)
    value = receipt(harness)
    assert value["status"] == "PASS" and value["source_stable"] is True
    assert value["mounted_acceptance"] == {"harness_test_double": True}
    assert value["owned_runtime_stopped"] is True and value["runtime_returncode"] == 0
    assert harness.process.calls == [("terminate",), ("wait", 15)]
    harness.acceptance.assert_called_once()
    assert harness.acceptance.call_args.args[:4] == (harness.root, harness.inputs.server, harness.inputs.model, harness.inputs.port)
    assert harness.acceptance.call_args.args[4]["real_inference"] == "PASS"
    harness.version.assert_called_once_with([str(harness.inputs.server), "--version"], capture_output=True,
                                            text=True, timeout=10, check=True)
    args, kwargs = harness.launch.call_args
    assert args == (runner.runtime_argv(harness.inputs.server, harness.inputs.model, harness.inputs.port),)
    assert "shell" not in kwargs
    assert set(kwargs) == {"stdout", "stderr"}
    for name in ("source-before.json", "source-after.json", "native-runtime.log", "native-props.json", "native-models.json"):
        assert (harness.root / name).is_file()
    for name in ("paid_api", "gpu", "private_credentials_used", "automatic_model_download"):
        assert value[name] is False


@pytest.mark.parametrize("error", [RuntimeError("harness-controlled failure"), KeyboardInterrupt()])
def test_mounted_failure_or_interruption_still_stops_owned_runtime(execute_harness, error):
    harness = execute_harness
    harness.acceptance.side_effect = error
    with pytest.raises(type(error)):
        execute(harness)
    value = receipt(harness)
    assert value["status"] == "FAIL" and value["real_inference"] == "NOT_RUN"
    assert value["error_type"] == type(error).__name__ and value["owned_runtime_stopped"] is True
    assert harness.process.calls == [("terminate",), ("wait", 15)]


def test_native_cleanup_escalates_only_its_owned_process_with_bounded_waits(execute_harness):
    harness = execute_harness
    harness.process.waits = deque([runner.subprocess.TimeoutExpired("test-owned-host", 15), -9])
    with pytest.raises(SystemExit) as error:
        execute(harness)
    assert error.value.code == 1
    assert harness.process.calls == [("terminate",), ("wait", 15), ("kill",), ("wait", 5)]
    assert receipt(harness)["forced_stop"] is True
    assert receipt(harness)["owned_runtime_stopped"] is True
    assert receipt(harness)["status"] == "FAIL_RUNTIME_SHUTDOWN"
    assert receipt(harness)["real_inference"] == "PASS"


@pytest.mark.parametrize("returncode", [1, -15, -9])
def test_nonzero_native_shutdown_cannot_receive_overall_acceptance_pass(execute_harness, returncode):
    harness = execute_harness
    harness.process.waits = deque([returncode])
    with pytest.raises(SystemExit) as error:
        execute(harness)
    value = receipt(harness)
    assert error.value.code == 1 and value["status"] == "FAIL_RUNTIME_SHUTDOWN"
    assert value["real_inference"] == "PASS" and value["runtime_returncode"] == returncode
    assert value["owned_runtime_stopped"] is True and not value.get("forced_stop")


@pytest.mark.parametrize("inference_status", ["DISPATCH_ATTEMPTED_OUTCOME_UNCONFIRMED", "PASS"])
def test_post_dispatch_failure_preserves_separate_inference_outcome(execute_harness, inference_status):
    harness = execute_harness

    def post_dispatch_failure(_root, _server, _model, _port, outcome):
        outcome["real_inference"] = inference_status
        raise RuntimeError("simulated-later-asset-failure")

    harness.acceptance.side_effect = post_dispatch_failure
    with pytest.raises(RuntimeError, match="^simulated-later-asset-failure$"):
        execute(harness)
    value = receipt(harness)
    assert value["status"] == "FAIL" and value["real_inference"] == inference_status
    assert value["owned_runtime_stopped"] is True


def test_mounted_return_without_confirmed_inference_cannot_synthesize_pass(execute_harness):
    harness = execute_harness
    harness.acceptance.side_effect = None
    harness.acceptance.return_value = {"harness_test_double": True}
    with pytest.raises(RuntimeError, match="^REAL_INFERENCE_RECEIPT_UNCONFIRMED$"):
        execute(harness)
    assert receipt(harness)["real_inference"] == "NOT_RUN"
    assert receipt(harness)["status"] == "FAIL"


def test_already_exited_runtime_is_reaped_without_signalling_other_processes(execute_harness):
    harness = execute_harness
    harness.process.returncode = 2
    harness.process.waits = deque([2])
    with pytest.raises(RuntimeError, match="^OWNED_RUNTIME_EXITED_BEFORE_READINESS$"):
        execute(harness)
    assert harness.process.calls == [("wait", 15)]
    harness.acceptance.assert_not_called()
    assert receipt(harness)["status"] == "FAIL"


def test_sigterm_handler_enters_normal_owned_cleanup(execute_harness):
    harness = execute_harness

    def interrupted(*_args):
        signal_number, handler = harness.handlers.call_args.args
        assert signal_number == runner.signal.SIGTERM
        handler(signal_number, None)

    harness.acceptance.side_effect = interrupted
    with pytest.raises(TimeoutError, match="^OWNED_ACCEPTANCE_CANCELLED$"):
        execute(harness)
    assert harness.process.calls == [("terminate",), ("wait", 15)]
    assert receipt(harness)["owned_runtime_stopped"] is True


def test_source_drift_cannot_be_reported_as_overall_acceptance_pass(execute_harness):
    harness = execute_harness
    harness.identity.side_effect = [{"sha256": "before"}, {"sha256": "after"}]
    with pytest.raises(SystemExit) as error:
        execute(harness)
    assert error.value.code == 2
    value = receipt(harness)
    assert value["source_stable"] is False
    assert value["status"] == "INCONCLUSIVE_SOURCE_DRIFT"
    assert value["real_inference"] == "PASS"  # Simulated orchestration state only.


def cli_args(inputs, root, *, confirmed=True):
    args = ["run_v2_real_text_check.py", "--server", str(inputs.server), "--model", str(inputs.model),
            "--model-sha256", inputs.sha, "--workspace", str(root), "--port", str(inputs.port)]
    return args + (["--confirm-owned-cpu-runtime"] if confirmed else [])


def test_cli_requires_explicit_owned_cpu_confirmation_before_any_work(tmp_path, inputs, monkeypatch):
    root = tmp_path / "not-created"
    monkeypatch.setattr(runner.sys, "argv", cli_args(inputs, root, confirmed=False))
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert not root.exists()
    inputs.socket_factory.assert_not_called()


def test_cli_refuses_existing_workspace_without_modifying_it(tmp_path, inputs, monkeypatch):
    root = tmp_path / "existing"
    root.mkdir()
    preserved = root / "user-data.txt"
    preserved.write_text("keep")
    monkeypatch.setattr(runner.sys, "argv", cli_args(inputs, root))
    with pytest.raises(FileExistsError):
        runner.main()
    assert list(root.iterdir()) == [preserved] and preserved.read_text() == "keep"


def test_parent_launches_only_one_sanitized_isolated_child_with_fixed_deadline(tmp_path, inputs, monkeypatch):
    root = tmp_path / "new-output"
    args = cli_args(inputs, root)
    process = HarnessProcess(waits=[0])
    launch = Mock(return_value=process)
    monkeypatch.setattr(runner.sys, "argv", args)
    monkeypatch.setattr(runner.subprocess, "Popen", launch)
    monkeypatch.setenv("OPENAI_API_KEY", "fake-secret")
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 0
    assert process.calls == [("wait", 360)]
    launch.assert_called_once()
    argv = launch.call_args.args[0]
    kwargs = launch.call_args.kwargs
    assert argv == [runner.sys.executable, str(Path(runner.__file__).resolve()), *args[1:], "--isolated-child"]
    assert kwargs["start_new_session"] is True and kwargs["cwd"] == runner.REPO
    assert "OPENAI_API_KEY" not in kwargs["env"] and "shell" not in kwargs
    assert kwargs["env"]["NOVEL_DATA_PATH"] == str(root / "novel-data")


@pytest.mark.parametrize("force_kill", [False, True])
def test_parent_timeout_stops_only_the_owned_child_group(tmp_path, inputs, monkeypatch, force_kill):
    root = tmp_path / "timeout-output"
    waits = [runner.subprocess.TimeoutExpired("test-owned-child", 360)]
    waits += [runner.subprocess.TimeoutExpired("test-owned-child", 25), -9] if force_kill else [-15]
    process = HarnessProcess(waits=waits)
    kill_group = Mock()
    monkeypatch.setattr(runner.sys, "argv", cli_args(inputs, root))
    monkeypatch.setattr(runner.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(runner.os, "killpg", kill_group)
    with pytest.raises(runner.subprocess.TimeoutExpired) as error:
        runner.main()
    assert error.value.timeout == 360
    assert process.calls == [("wait", 360), ("terminate",), ("wait", 25)] + ([("wait", 5)] if force_kill else [])
    kill_group.assert_called_once_with(process.pid, runner.signal.SIGKILL)


@pytest.mark.parametrize("returncode", [1, 2, -9, -11])
@pytest.mark.parametrize("group_exists", [False, True])
def test_abnormal_child_exit_cleans_owned_descendants_even_after_child_is_reaped(
        tmp_path, inputs, monkeypatch, returncode, group_exists):
    process = HarnessProcess(waits=[returncode])
    kill_group = Mock(side_effect=None if group_exists else ProcessLookupError)
    monkeypatch.setattr(runner.sys, "argv", cli_args(inputs, tmp_path / "crashed-child"))
    monkeypatch.setattr(runner.subprocess, "Popen", Mock(return_value=process))
    monkeypatch.setattr(runner.os, "killpg", kill_group)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == returncode
    assert process.calls == [("wait", 360)]
    kill_group.assert_called_once_with(process.pid, runner.signal.SIGKILL)


def test_direct_child_rejects_missing_isolated_data_path(tmp_path, inputs, monkeypatch):
    monkeypatch.setattr(runner.sys, "argv", cli_args(inputs, tmp_path) + ["--isolated-child"])
    monkeypatch.delenv("NOVEL_DATA_PATH", raising=False)
    execute = Mock()
    monkeypatch.setattr(runner, "execute", execute)
    with pytest.raises(ValueError, match="^ISOLATED_CHILD_ENVIRONMENT_REQUIRED$"):
        runner.main()
    execute.assert_not_called()
