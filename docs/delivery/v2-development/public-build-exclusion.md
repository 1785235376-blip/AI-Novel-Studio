# Public build exclusion boundary

Date: 2026-10-16. Base: `1feb763d6283cda27f21ff1e10d87d981504ecbb`.
Status: local implementation and offline verification; **not a released or production-verified package**.

## Audit and dependency boundary

The existing `app/creative/content_policy.py` is explicitly RESERVED. Its vocabulary and pure metadata helpers do not implement a mature generation backend. `workspace_models.py` owns the optional persisted preference; `workspace.py` preserves its null-means-unchanged behavior. The preferences endpoint can retain that metadata, but it does not activate a separate backend. Removing these shared compatibility contracts would be an incorrect substitute for backend separation. They remain unchanged, as do existing access gates and safeguards.

No operational optional-mode frontend or backend was found in this checkout. The preferences form now has a shared, unconditionally disabled Button labelled `NSFW 模式（本版本不可用）`, with `type="button"`, no callback, no API client, and no enabling flag. Its tooltip says the public edition does not provide the feature. This does not promise that a private implementation exists.

The dedicated future namespace `studio_private_extensions` is outside every public runtime root. No private implementation is created by this change. An optional backend cannot be moved into `app` to gain automatic inclusion: any unlisted file fails source closure. Public code/configuration must not depend on that namespace; literal imports, dynamic import strings and configuration references are rejected. A future shared dependency must be separated into a reviewed public core module without importing private functionality. Existing safeguards must remain public.

## Implemented build contract

- `packaging/public-build.json` explicitly lists 487 public runtime files under `app`, the two local-interop packages, `config`, `prompts`, and `workflows`. It records the existing required/optional dependency declarations. Additions/removals or dependency changes require an explicit manifest review; no automatic manifest regeneration is part of the build.
- Docker has 40 additional explicit inputs: existing contracts, `pyproject.toml`, and `release/version.json`. Its final application files come only from the checked public stage, plus the generated build receipt. The previous wholesale final-stage `COPY app` is removed.
- `scripts/public_build.py` is a standard-library-only build tool. It checks source closure, rejects symlinks and named private dependencies, stages only listed files into a fresh destination, and compares actual stage hashes with current source hashes. The entire stage tree is checked for unexpected entries, including files outside the known roots. A receipt records the included paths and SHA-256 values.
- Developer bytecode/cache files are not source inputs and are not copied. Bytecode or unexpected archives/native files in a staged public backend fail closure. New non-cache runtime source files are rejected even when the previous Windows copier would have ignored their extension.
- Windows assembly invokes the same source guard before build side effects, checks the freshly staged backend, and rechecks before announcing the assembled Application. The final check allows only the three font filenames already checked by the existing pinned-font assembly logic; it does not replace those digest/license checks. It also inspects the Application's paths and ZIP/WHL/EGG/PYZ members for the excluded namespace.
- ZIP-based archive inspection includes nested archives, bounded to 10,000 inspected members and 128 MiB of expanded nested-archive bytes per outer archive, and a nesting limit. Exceeding the limits fails instead of silently skipping contents. Archives are never extracted or executed.
- The Windows acceptance packager continues to call this assembler and its existing ZIP inventory-closure checks. It is still an internal acceptance package; this profile does not change `public_release = false`, authorize release, or create an installer.

## Offline verification

All tests use synthetic inputs and disposable temporary directories; no application startup, real user data, provider calls, GPU, browser, credentials or database services are involved.

- 37 Python tests passed: new public-build tests plus existing Windows packaging synchronization and host-provenance source-contract tests. Run with `--noconftest`, so application/credential/lifecycle fixtures are not loaded.
- Actual checkout staging passed for all 487 runtime files. A disposable ZIP was created and reopened; its member set and every member SHA-256 matched the receipt. Separate Docker staging passed for 527 files (487 + 40).
- Negative cases cover undeclared Python/native/archive files, private dependency references, frontend private import strings, dependency changes, source symlinks, stage bytecode/tampering/reuse, extra top-level and nested stage files, missing artifact roots, nested private archive members and invalid manifest paths.
- 22 frontend tests passed across the new disabled-placeholder test, existing preference contracts, and graph geometry contracts. Repeated click/keyboard events do not call fetch, save, or preference mutation; locked/read-only rerenders remain disabled.
- TypeScript `tsc -b --pretty false`, UI token guard, and `git diff --check` passed. Shared button styling and the canonical image workspace reference were reviewed; no shell, token or style changes were made.

## Limits and remaining release work

- No Windows build, PowerShell execution, Docker image build, installation, signing, deployed endpoint, CI rerun or browser visual regression was performed. Browser work was outside this task's authorization. Source-contract tests are not execution proof for those platforms.
- Standalone wheel/sdist builds, arbitrary `pip install` directly from the repository, ad hoc copy scripts, repository source archives and other distribution paths are **not** certified public releases by this guard. They require equivalent staging integration before use as public distributions.
- The manifest is a reviewed inclusion list, not a content classifier. Existing public-file edits, computed/obfuscated imports, renamed archives, opaque native payloads and transitive third-party dependency contents still require review/provenance. The check cannot prove that arbitrary future code has no private behavior. It does not alter ordinary model discovery or general generation behavior.
- Windows retains existing frozen runtime dependencies and native/font/migration provenance checks. This change does not certify their full behavior or replace their existing verification. Docker still installs the declared dependencies through pip; no dependency downloads or installed-image validation were performed here.
- No formal release/tag, main merge, deploy, artifact upload or push was performed for this change. Local tracked edits belong to this packaging slice; prior untracked director verification receipts were preserved. The separately blocked lifecycle/authorization work was not inspected, edited, or tested.
