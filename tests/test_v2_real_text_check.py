"""Harness safety contracts only: no native host, model inference or download.

Process, metadata and mounted-API doubles below test orchestration. Their
simulated receipts are not real-inference acceptance evidence.
"""
from collections import deque
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from scripts import run_v2_real_text_check as runner

# The runner fails closed on Windows before input validation because owned process-tree
# cleanup is not supported there (BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM).
# These contracts describe the POSIX runner that hosted Linux CI exercises.
pytestmark = pytest.mark.skipif(
    os.name == "nt",
    reason="real-text runner is BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM on Windows; POSIX CI covers the harness contracts",
)


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


def test_adaptation_scenario_uses_bounded_owned_cpu_context_only(inputs):
    argv = runner.runtime_argv(inputs.server, inputs.model, inputs.port, scenario="adaptation")
    original = runner.runtime_argv(inputs.server, inputs.model, inputs.port)
    expected = list(original)
    expected[expected.index("--ctx-size") + 1] = "8192"
    assert argv == expected
    assert argv[argv.index("--n-gpu-layers") + 1] == "0"
    assert argv[argv.index("--threads") + 1] == "2"
    assert "--offline" in argv


def test_unknown_acceptance_scenario_cannot_construct_runtime_command(inputs):
    with pytest.raises(ValueError, match="UNKNOWN_OWNED_ACCEPTANCE_SCENARIO"):
        runner.runtime_argv(inputs.server, inputs.model, inputs.port, scenario="unapproved")


def test_adaptation_acceptance_uses_saved_get_version_not_create_projection(tmp_path):
    from scripts.run_v2_real_adaptation_scenario import run
    observed = []
    class StopBeforeModel(Exception): pass
    def api(method, path, payload=None, status=200):
        observed.append((method, path, payload))
        if path.endswith("/chapters"):
            return {"id": "owned-project:1"}  # Existing create API omits version.
        if method == "GET":
            return {"id": "owned-project:1", "version": 7, "content": "Saved source"}
        assert path.endswith("/adaptation-proposals")
        assert payload["expected_source_version"] == 7
        raise StopBeforeModel
    with pytest.raises(StopBeforeModel):
        run(tmp_path, api, None, {}, "owned-project", {}, {})
    assert len(observed) == 3


def test_adaptation_acceptance_reads_typed_binding_not_unset_generic_actor_scope():
    from scripts.run_v2_real_adaptation_scenario import archive_authority
    scope = {"mode": "local", "novel_id": "project"}
    proposal = {"id": "proposal", "novel_id": "project", "scope": scope, "created_by": "local-author"}
    binding = {"proposal_id": "proposal", "project_id": "project", "scope": scope, "actor_id": "local-author"}
    job = SimpleNamespace(scope=None, actor_id=None, adaptation_binding=binding)
    assert archive_authority(proposal, job) == (scope, "local-author")
    for key in ("proposal_id", "project_id", "scope", "actor_id"):
        changed = dict(binding); changed[key] = "different"
        with pytest.raises(AssertionError):
            archive_authority(proposal, SimpleNamespace(adaptation_binding=changed))


@pytest.mark.parametrize("platform", ["win32", "cygwin"])
@pytest.mark.parametrize("isolated_child", [False, True])
def test_unsupported_platform_blocks_before_input_or_workspace_work(
        tmp_path, inputs, monkeypatch, capsys, platform, isolated_child):
    root = tmp_path / "must-not-be-created"
    args = cli_args(inputs, root)
    if isolated_child:
        args.append("--isolated-child")
    monkeypatch.setattr(runner.sys, "argv", args)
    monkeypatch.setattr(runner.sys, "platform", platform)
    validate = Mock(side_effect=AssertionError("MUST_NOT_READ_MODEL_OR_PROBE_PORT"))
    identity = Mock(side_effect=AssertionError("MUST_NOT_INSPECT_SOURCE"))
    execute = Mock(side_effect=AssertionError("MUST_NOT_START_ACCEPTANCE"))
    monkeypatch.setattr(runner, "validated_inputs", validate)
    monkeypatch.setattr(runner, "source_identity", identity)
    monkeypatch.setattr(runner, "execute", execute)
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert "BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM" in capsys.readouterr().err
    assert not root.exists()
    validate.assert_not_called()
    identity.assert_not_called()
    execute.assert_not_called()
    inputs.socket_factory.assert_not_called()


@pytest.mark.parametrize("owner,name", [
    ("os", "killpg"), ("os", "setsid"),
    ("signal", "SIGKILL"), ("signal", "SIGTERM"), ("signal", "signal"),
])
@pytest.mark.parametrize("unavailable", ["missing", "none"])
def test_missing_process_group_api_blocks_before_any_owned_acceptance_work(
        tmp_path, inputs, monkeypatch, owner, name, unavailable):
    namespace = getattr(runner, owner)
    if unavailable == "missing":
        monkeypatch.delattr(namespace, name)
    else:
        monkeypatch.setattr(namespace, name, None)
    validate = Mock(side_effect=AssertionError("MUST_NOT_READ_MODEL_OR_PROBE_PORT"))
    monkeypatch.setattr(runner, "validated_inputs", validate)
    root = tmp_path / "not-created"
    with pytest.raises(ValueError, match="^BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM$"):
        runner.execute(root, inputs.server, inputs.model, inputs.sha, inputs.port)
    assert not root.exists()
    validate.assert_not_called()
    inputs.socket_factory.assert_not_called()


def test_non_posix_os_blocks_even_when_process_group_api_names_exist(monkeypatch):
    monkeypatch.setattr(runner, "os", SimpleNamespace(name="nt", killpg=Mock(), setsid=Mock()))
    with pytest.raises(ValueError, match="^BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM$"):
        runner.validate_process_platform()


def test_supported_posix_process_platform_preflight_is_read_only():
    assert runner.validate_process_platform() is None


def test_all_temp_conventions_use_only_the_private_owned_directory(tmp_path, monkeypatch):
    private = tmp_path / "owned"
    private.mkdir()
    foreign = tmp_path / "foreign-temp"
    foreign.mkdir()
    marker = foreign / "keep.txt"
    marker.write_text("unchanged", encoding="utf-8")
    inherited = {key: str(foreign) for key in ("TEMP", "TMP", "TMPDIR")}
    monkeypatch.setattr(runner.os, "environ", inherited)
    env = runner.isolated_environment(private)
    for key in ("TEMP", "TMP", "TMPDIR"):
        assert env[key] == str(private / "tmp")
        assert Path(env[key]).is_dir()
    assert inherited == {key: str(foreign) for key in ("TEMP", "TMP", "TMPDIR")}
    assert list(foreign.iterdir()) == [marker]
    assert marker.read_text(encoding="utf-8") == "unchanged"
    monkeypatch.setattr(runner.os, "environ", env)
    runner.validate_isolated_environment(private)


@pytest.mark.parametrize("isolated_child", [False, True])
def test_cli_missing_process_group_cleanup_api_blocks_before_workspace_creation(
        tmp_path, inputs, monkeypatch, capsys, isolated_child):
    root = tmp_path / "blocked-no-group-cleanup"
    args = cli_args(inputs, root) + (["--isolated-child"] if isolated_child else [])
    monkeypatch.setattr(runner.sys, "argv", args)
    monkeypatch.delattr(runner.os, "killpg")
    with pytest.raises(SystemExit) as error:
        runner.main()
    assert error.value.code == 2
    assert "BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM" in capsys.readouterr().err
    assert not root.exists()
    inputs.socket_factory.assert_not_called()


def test_platform_preflight_does_not_call_process_control_apis(monkeypatch):
    platform_os = SimpleNamespace(name="posix", killpg=Mock(), setsid=Mock())
    handler = Mock()
    monkeypatch.setattr(runner, "os", platform_os)
    monkeypatch.setattr(runner.sys, "platform", "linux")
    monkeypatch.setattr(runner.signal, "signal", handler)
    runner.validate_process_platform()
    platform_os.killpg.assert_not_called()
    platform_os.setsid.assert_not_called()
    handler.assert_not_called()


def test_direct_input_validation_rejects_unsupported_platform_before_model_read(inputs, monkeypatch):
    monkeypatch.setattr(runner.sys, "platform", "win32")
    model_read = Mock(side_effect=AssertionError("MUST_NOT_HASH_MODEL"))
    monkeypatch.setattr(runner, "sha256_file", model_read)
    with pytest.raises(ValueError, match="^BLOCKED_UNSUPPORTED_OWNED_PROCESS_PLATFORM$"):
        validate(inputs)
    model_read.assert_not_called()
    inputs.socket_factory.assert_not_called()


def fail_owned_cleanup(harness, monkeypatch, stage, error):
    """Inject one owned-process failure without starting or signalling a process."""
    timeout = runner.subprocess.TimeoutExpired("test-owned-host", 15)
    if stage in {"terminate", "kill"}:
        def failed_signal():
            harness.process.calls.append((stage,))
            raise error
        monkeypatch.setattr(harness.process, stage, failed_signal)
    if stage == "wait":
        harness.process.waits = deque([error])
    elif stage == "kill":
        harness.process.waits = deque([timeout])
    elif stage == "final_wait":
        harness.process.waits = deque([timeout, error])
    elif stage == "initial_poll":
        monkeypatch.setattr(harness.process, "poll", Mock(side_effect=[None, error]))
    elif stage == "final_poll":
        monkeypatch.setattr(harness.process, "poll", Mock(side_effect=[None, None, error]))
    return {
        "initial_poll": [], "terminate": [("terminate",)],
        "wait": [("terminate",), ("wait", 15)],
        "kill": [("terminate",), ("wait", 15), ("kill",)],
        "final_wait": [("terminate",), ("wait", 15), ("kill",), ("wait", 5)],
        "final_poll": [("terminate",), ("wait", 15)],
    }[stage]


@pytest.mark.parametrize("operational_failure", [None, "runtime", "interrupt"])
@pytest.mark.parametrize("stage", ["initial_poll", "terminate", "wait", "kill", "final_wait", "final_poll"])
def test_cleanup_error_retains_acceptance_and_original_failure(
        execute_harness, monkeypatch, operational_failure, stage):
    harness = execute_harness
    cleanup_error = OSError("simulated-owned-" + stage)
    calls = fail_owned_cleanup(harness, monkeypatch, stage, cleanup_error)
    original = {None: None, "runtime": RuntimeError("simulated-operational-failure"),
                "interrupt": KeyboardInterrupt("simulated-operational-interruption")}[operational_failure]
    if original is not None:
        harness.acceptance.side_effect = original
    with pytest.raises(BaseException) as raised:
        execute(harness)
    value = receipt(harness)
    assert raised.value is (original if original is not None else cleanup_error)
    assert value["status"] == ("FAIL" if original is not None else "FAIL_RUNTIME_SHUTDOWN")
    assert value["real_inference"] == ("NOT_RUN" if original is not None else "PASS")
    if original is not None:
        assert value["error_type"] == type(original).__name__ and value["error"] == str(original)
    assert value["cleanup_error_type"] == "OSError" and value["cleanup_error"] == str(cleanup_error)
    assert value["owned_runtime_stopped"] is (stage == "final_poll")
    assert value["runtime_returncode"] == (0 if stage == "final_poll" else None)
    assert value.get("forced_stop", False) is (stage == "final_wait")
    assert value["source_stable"] is True
    assert (harness.root / "source-after.json").is_file()
    assert value["finished_utc"] and value["elapsed_seconds"] >= 0
    assert harness.process.calls == calls
    assert harness.identity.call_count == 2


@pytest.mark.parametrize("operational_failure", [None, "runtime", "interrupt"])
@pytest.mark.parametrize("source_failure", ["read", "write"])
def test_provenance_error_retains_acceptance_and_original_failure(
        execute_harness, monkeypatch, operational_failure, source_failure):
    harness = execute_harness
    source_error = OSError("simulated-final-source-" + source_failure)
    if source_failure == "read":
        harness.identity.side_effect = [harness.identity.return_value, source_error]
    else:
        original_write = runner.write_json
        def fail_source_write(path, value):
            if path.name == "source-after.json":
                raise source_error
            original_write(path, value)
        monkeypatch.setattr(runner, "write_json", fail_source_write)
    original = {None: None, "runtime": RuntimeError("simulated-operational-failure"),
                "interrupt": KeyboardInterrupt("simulated-operational-interruption")}[operational_failure]
    if original is not None:
        harness.acceptance.side_effect = original
    with pytest.raises(BaseException) as raised:
        execute(harness)
    value = receipt(harness)
    assert raised.value is (original if original is not None else source_error)
    assert value["status"] == ("FAIL" if original is not None else "INCONCLUSIVE_SOURCE_IDENTITY")
    assert value["real_inference"] == ("NOT_RUN" if original is not None else "PASS")
    if original is not None:
        assert value["error_type"] == type(original).__name__ and value["error"] == str(original)
    assert value["source_error_type"] == "OSError" and value["source_error"] == str(source_error)
    assert value["source_stable"] is None
    assert value["owned_runtime_stopped"] is True and value["runtime_returncode"] == 0
    assert harness.process.calls == [("terminate",), ("wait", 15)]
    assert (harness.root / "source-before.json").is_file()
    assert value["finished_utc"] and value["elapsed_seconds"] >= 0


@pytest.mark.parametrize("operational_failure", [False, True])
def test_cleanup_and_provenance_errors_both_survive_in_acceptance(
        execute_harness, monkeypatch, operational_failure):
    harness = execute_harness
    original = RuntimeError("simulated-operational-failure")
    cleanup_error = OSError("simulated-owned-final-wait")
    source_error = RuntimeError("simulated-source-read-failure")
    fail_owned_cleanup(harness, monkeypatch, "final_wait", cleanup_error)
    harness.identity.side_effect = [harness.identity.return_value, source_error]
    if operational_failure:
        harness.acceptance.side_effect = original
    with pytest.raises(BaseException) as raised:
        execute(harness)
    value = receipt(harness)
    assert raised.value is (original if operational_failure else cleanup_error)
    assert value["status"] == ("FAIL" if operational_failure else "FAIL_RUNTIME_SHUTDOWN")
    assert value["cleanup_error"] == str(cleanup_error) and value["cleanup_error_type"] == "OSError"
    assert value["source_error"] == str(source_error) and value["source_error_type"] == "RuntimeError"
    assert value["source_stable"] is None and value["owned_runtime_stopped"] is False
    assert value["runtime_returncode"] is None and value["forced_stop"] is True


def test_cleanup_error_keeps_already_observed_exit_evidence(execute_harness):
    harness = execute_harness
    harness.process.returncode = 2
    harness.process.waits = deque([OSError("simulated-reap-failure")])
    with pytest.raises(RuntimeError, match="^OWNED_RUNTIME_EXITED_BEFORE_READINESS$"):
        execute(harness)
    value = receipt(harness)
    assert value["status"] == "FAIL" and value["error"] == "OWNED_RUNTIME_EXITED_BEFORE_READINESS"
    assert value["owned_runtime_stopped"] is True and value["runtime_returncode"] == 2
    assert value["cleanup_error"] == "simulated-reap-failure"
    assert harness.process.calls == [("wait", 15)]


def test_shutdown_without_exit_evidence_cannot_receive_pass(execute_harness, monkeypatch):
    harness = execute_harness
    wait = Mock(return_value=None)
    monkeypatch.setattr(harness.process, "wait", wait)
    with pytest.raises(SystemExit) as raised:
        execute(harness)
    value = receipt(harness)
    assert raised.value.code == 1 and value["status"] == "FAIL_RUNTIME_SHUTDOWN"
    assert value["owned_runtime_stopped"] is False and value["runtime_returncode"] is None
    wait.assert_called_once_with(timeout=15)
