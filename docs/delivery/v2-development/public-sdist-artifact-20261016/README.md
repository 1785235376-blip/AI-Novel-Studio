# PUBLIC source-distribution verification

## Result

The current-source run passed **147 tests**, including real offline wheel and sdist builds, the existing PUBLIC profile regressions, and inert archive/metadata negatives. Independent review reran the same **147 tests** successfully. No source changed during final verification.

The retained test sdist contains **506 source/data payloads, seven generated metadata files and 21 directories** (534 logical members). Its SHA256 is `6c19645cbac0ca69d051405a000b4c6f91b175a0c6ed6c7b2f2d1d0f4978d86e`. The actual artifact stays in the owned ignored profile; no binary is committed or published.

## Scope

This is verification for a **future distribution format**, not evidence that a source distribution is already shipped or a standalone application. The installed setuptools backend builds a genuine `.tar.gz` source distribution from a disposable copy of a fresh immutable PUBLIC stage. The build blocks application imports, network activity and subprocess launches. Nothing is installed or downloaded.

The verifier reuses PUBLIC source closure, allowlists, namespace exclusions, source hashes and dependency validation. It checks 506 original source/data inputs, including `pyproject.toml`, plus exactly seven generated metadata files. All standard policy/model inputs and the approved incoming standard lifecycle module remain unchanged by hash. No application module or lifecycle/security test executes.

## Archive profile

Named `.tar`, `.tar.gz` and `.tgz` archives are inspected without filesystem extraction. ZIP/wheel/egg/pyz inspection remains available, including mixed ZIP-to-TAR and TAR-to-ZIP nesting.

- At most 10,000 physical headers/ZIP entries, 128 MiB of charged inspection bytes and three nested archive levels, shared across mixed recursion.
- At most 32 MiB for an individual TAR member; local PAX is at most 64 KiB and 128 keys, with only `path` and `mtime` accepted.
- Raw gzip output is bounded before any header is parsed. A single gzip stream is required; concatenated streams and trailing compressed data fail.
- Physical 512-byte TAR headers are inspected directly, including PAX headers. Links, devices, FIFOs, sparse files, GNU long-name/link records, global PAX and unknown types fail.
- Absolute paths, traversal, backslashes, drive-like paths, duplicate effective paths, file-parent collisions, nonzero member padding, missing end blocks and hidden trailing archives fail.
- PAX length/key validation happens before applying an effective path. No TAR iterator can silently consume unsupported physical records.

The sdist verifier requires exact source-payload and directory closure. Root and egg-info PKG-INFO must agree and match project identity, Python requirements, runtime dependencies and extras. SOURCES.txt must cover exactly the expected source and egg-info inputs. Generated setup.cfg, dependency_links.txt, top_level.txt and requires.txt are explicitly checked. Unknown egg-info files are not blanket-allowed.

## Limits

This narrow profile supports the observed installed setuptools layout (metadata version 2.4 and requirements without environment markers). Future layout or marker changes fail for review rather than being guessed. bzip2/xz, opaque native libraries and renamed archives/modules remain outside the scanner's format/provenance claim.

External dependencies, including `psycopg[binary]`, are metadata only, not bundled or installed. Config/prompts/workflows and other companion files remain separate stage assets and are enumerated in the receipt. The backend's missing-README warning is retained. No Docker image, Windows assembly/startup, release upload or publication is accepted by these checks. No dedicated mature backend or generation behavior was added.

## Source boundary

The final run captured HEAD `1278e4f95affb1e33d8b7676c2930226ad7b49e0` with the approved packaging code and separate frontend handoff work still uncommitted. All **528 PUBLIC-stage input hashes** were compared with the Git blobs at that HEAD and matched exactly. The final stage was also reverified against the frozen current source. `verification.json` records the exact four verifier/test blobs, the dirty-source boundary, both real artifact hashes, installed tooling, original runner-receipt hash and unchanged-source result. `stage-receipt.json` and `sdist-receipt.json` retain the complete payload hash maps.

The earlier development run passed 143 cases. Four additional inert effective-PAX-path and physical size-header cases are included in both 147-case final and independent runs. The existing wheel suite remains green after the shared build fixture and dependency validator refactor.
