# PUBLIC wheel artifact verification

## Result

A real offline setuptools wheel was built from the existing PUBLIC stage. The final packaging-only run passed **56 tests** (26 wheel-artifact cases plus 30 existing PUBLIC-profile cases). Independent review and the wheel suite passed **26 tests**.

The artifact has **505 source/data payloads and 4 metadata entries**. Every payload matches the captured PUBLIC-stage hash, and every ZIP member has exact RECORD coverage, digest and byte length; RECORD's own row must remain unhashed. The verifier rejects missing, extra, tampered, duplicate, unsafe and symlink members, unsupported wheel metadata, and altered dependency/extra declarations even when a derivative has a self-consistent RECORD. Neutral private-namespace and native-extra fixtures are never executed.

The wheel SHA256 is `41470b1795d04fb79cf0f4b8f3a38c27d52fec249e3d68d38b0704ff9c161f44`. It remains an owned test artifact; no binary is committed, installed, uploaded or published.

## Source boundary

The final run began at commit `b1f161663974a9b0d489ef119a7c35bfcb55c9d5` with approved packaging and graph-capacity work uncommitted. No sources changed during that check. All **528** PUBLIC-stage input hashes matched the frozen current source when verified.

The wheel includes graph-capacity `app/creative/graph.py` blob `0cf6a482588d234129ab71e9429fb98afa959060`. Therefore it is **not** a wheel for the packaging-only commit tree. The eventual combined commit must retain all hashes in `stage-receipt.json`. `verification.json` records the exact owned blobs and dirty-source boundary.

The original guard correctly stopped the first attempt because the incoming Codex standard lifecycle file `app/project_retirement.py` was missing from the allowlist. After independent provenance corroboration and explicit approval, exactly that one sorted entry was added. Its bytes are preserved in the wheel; the module is never imported or executed. The original failure is retained in `stage-blocked.json` and `stage-blocked.log`.

A second expected rejection occurred when the live graph source changed after the first probe was staged. The stage and wheel still matched each other; the verifier refused to claim that they matched the changed live file. See `source-drift-rejected.json`.

## Implementation and checks

- `packaging/public-build.json`: the single approved standard-module addition.
- `scripts/public_build.py`: optional `--wheel` verification reuses the existing PUBLIC source closure, hashes and nested archive scanner. Existing guard paths remain stdlib-only; wheel verification lazily uses the already-installed `packaging` parser. No installation is attempted.
- `tests/test_public_wheel_artifact.py`: builds through installed `setuptools.build_meta` in a disposable copy of a pristine PUBLIC stage. Application-package imports, networking and child process launches are blocked in the builder. Tests run with `--noconftest` and plugin autoload disabled, without application runtime fixtures or lifecycle/security tests.

All build tooling was already installed. Shared standard/policy/model inputs, including `app/creative/content_policy.py`, retain their original hashes. Dependency metadata remains equal to the declared project requirements. The independent review found and verified the dependency-parity fix; positive-build tests alone would not have protected against altered metadata.

## Limits

`py3-none-any` describes this project's wheel payload. External dependencies, including `psycopg[binary]`, are not bundled or platform-tested. Config, prompts, workflows and other companion files remain separate stage assets, listed explicitly in the wheel receipt. This does not make the wheel a standalone application.

No sdist/tar artifact, Docker image/startup or Windows assembly/startup was verified. Existing opaque-native/renamed-module provenance limitations remain. No dedicated mature-content backend or generation behavior was added; shared compatibility vocabulary and standard behavior were not changed.
