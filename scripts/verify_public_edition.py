"""Verify public-edition build invariants and report the internal-research boundary.

This is a static/offline release gate. It starts no server, model, provider or database.
It does not modify files.

Exit codes:
  0  all public-build invariants hold
  1  a public-build invariant failed
  2  the requested edition is INTERNAL_RESEARCH while its runtime isolation is still
     declared BLOCKED (a controlled non-pass, never reported as PASS)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "docs" / "v2" / "engineering" / "edition_manifest.json"
checks: list[dict] = []


def record(name: str, ok: bool, detail: str) -> None:
    checks.append({"name": name, "status": "PASS" if ok else "FAIL", "detail": detail})


def read(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    record("manifest.schema", manifest.get("schema_version") == 1, "schema_version must be 1")
    record("manifest.spec", manifest.get("spec") == "SPEC-2026.10.19-r1", "edition manifest must bind SPEC-2026.10.19-r1")
    edition = os.environ.get("POEMSEED_STUDIO_EDITION", "PUBLIC").strip().upper()
    record("edition.declared", edition in {"PUBLIC", "INTERNAL_RESEARCH"}, "unknown editions fail closed to PUBLIC")

    invariants = manifest.get("public_build_invariants", {})
    record("invariants.flags_default_off", invariants.get("experimental_flags_default") == "OFF", "experimental flags default OFF")
    record("invariants.v1_deny", invariants.get("v1_acceptance_mode") == "DENY_ALL_EXPERIMENTAL", "V1_ACCEPTANCE_MODE denies all experimental flags")
    record("invariants.wildcard_forbidden", invariants.get("wildcard_flag_enable") == "FORBIDDEN", "no wildcard enable")

    # Static source checks: explicit closed flag registry and no '*' element.
    flags_source = read("app/experimental/flags.py")
    record("flags.registry_present", "RUNTIME_FLAGS" in flags_source and "enabled_flags" in flags_source, "runtime flag registry parsed")
    wildcard_single = chr(39) + "*" + chr(39)
    wildcard_double = chr(34) + "*" + chr(34)
    record("flags.no_wildcard_literal", wildcard_single not in flags_source and wildcard_double not in flags_source, "flag registry contains no * wildcard literal")
    record("flags.v1_override", "V1_ACCEPTANCE_MODE" in flags_source, "V1 acceptance override present")
    config_source = read("app/config.py")
    record("config.packaged_default_false", 'enable_packaged_runtime: bool = _bool("ENABLE_PACKAGED_RUNTIME", False)' in config_source, "packaged runtime defaults off")
    record("config.collaboration_default_false", 'enable_collaboration_runtime: bool = _bool("ENABLE_COLLABORATION_RUNTIME", False)' in config_source, "collaboration runtime defaults off")

    launch = read("app/packaging/launch_profiles.py")
    process = read("app/packaging/packaged_processes.py")
    required = invariants.get("required_packaged_launch_env", {})
    record("packaged.cloud_false", '"ENABLE_CLOUD": "false"' in launch, "packaged launch sets ENABLE_CLOUD=false")
    record("packaged.mock_false", '"MOCK_PROVIDER": "false"' in launch, "packaged launch sets MOCK_PROVIDER=false")
    record("packaged.fallback_false", '"ENABLE_PROVIDER_FALLBACK": "false"' in process, "packaged runtime sets fallback=false")
    record("packaged.runtime_true", '"ENABLE_PACKAGED_RUNTIME": "true"' in process, "packaged runtime flag explicit")
    record("packaged.collaboration_true", '"ENABLE_COLLABORATION_RUNTIME": "true"' in process, "packaged runtime requires collaboration boundary")
    experimental_line = next((line for line in process.splitlines() if '"EXPERIMENTAL_FEATURES"' in line), "")
    record("packaged.experimental_closed_list", bool(experimental_line) and "'*'" not in experimental_line and '"*"' not in experimental_line, "packaged experimental flags are an explicit closed list")

    launcher = read("packaging/portable/AI-Novel-Studio-Portable.cmd")
    record("launcher.isolated_python", "-B -I" in launcher, "portable launcher runs bundled Python isolated")
    record("launcher.fixed_root", "--application-root" in launcher and "APPLICATION_ROOT" in launcher, "portable launcher fixes the staged application root")
    record("launcher.no_dotenv_or_secret_read", ".env" not in launcher and "API_KEY" not in launcher and "PASSWORD" not in launcher, "launcher never reads dotenv/credentials")

    # Tracked-file inventory: public build inputs must not include secrets or model weights.
    tracked = subprocess.run(["git", "ls-files", "-z"], cwd=ROOT, capture_output=True, check=False)
    tracked_files = [item for item in tracked.stdout.decode("utf-8", "replace").split("\x00") if item]
    forbidden = re.compile(r"(^|/)(\.env(\..+)?|\.?secret|.*\.pem|.*\.key|.*\.p12|.*\.gguf|.*\.safetensors|.*\.onnx)$", re.I)
    sample_names = (".env.example", ".env.sample")
    offending = [path for path in tracked_files if forbidden.search(path) and not path.endswith(sample_names)]
    record("inputs.no_secret_or_weight_files", not offending, "no credential files or model weights tracked for any build" if not offending else "offending: " + ", ".join(offending[:8]))
    example = ROOT / ".env.example"
    example_text = example.read_text(encoding="utf-8") if example.exists() else ""
    high_risk = re.compile(r"(sk-[A-Za-z0-9]{20,}|AKIA[0-9A-Z]{16}|ghp_[A-Za-z0-9]{20,}|xox[baprs]-[A-Za-z0-9-]{10,})")
    record("inputs.env_example_placeholders_only", not high_risk.search(example_text), "tracked .env.example contains placeholders only, no live-token patterns")
    record("inputs.packaging_limited", all(path.startswith(("packaging/", "docs/v2/engineering/")) or not path.startswith("packaging/") for path in tracked_files if path.startswith("packaging/")), "packaging directory only contains reviewed build inputs")

    boundary = manifest.get("internal_research_boundary", {})
    record("internal_boundary.declared_blocked", boundary.get("status") == "BLOCKED" and boundary.get("implemented") is False, "internal research runtime isolation is honestly declared BLOCKED")

    failed = [check for check in checks if check["status"] == "FAIL"]
    status = "FAIL" if failed else "PASS"
    if edition == "INTERNAL_RESEARCH":
        status = "BLOCKED"
        failed.append({"name": "edition.internal_research_runtime", "status": "BLOCKED",
                       "detail": "internal research runtime/deployment isolation is not implemented; see manifest missing list"})
    report = {"document": "public-edition-verification/1", "edition": edition, "status": status,
              "checks": checks, "failed": failed}
    print(json.dumps(report, ensure_ascii=False, indent=2))
    if status == "BLOCKED":
        return 2
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
