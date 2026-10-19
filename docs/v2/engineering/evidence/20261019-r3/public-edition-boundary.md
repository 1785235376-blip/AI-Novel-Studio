# Public edition boundary — real execution evidence (round 3)

Implementation:
- `app/edition.py`: PUBLIC/INTERNAL_RESEARCH declaration, fail-closed `current_edition()`.
- `docs/v2/engineering/edition_manifest.json`: build invariants + honest BLOCKED internal boundary.
- `scripts/verify_public_edition.py`: 24 static public-build invariants (flags default OFF, no wildcard
  enable, packaged launch cloud/mock/fallback OFF and closed experimental list, isolated portable
  launcher, no tracked credential/weight files, env-example placeholders only, internal boundary declared
  BLOCKED). Exits 0 PASS / 1 FAIL / 2 BLOCKED.
- `tests/test_public_edition_boundary.py`: verifier PASS, INTERNAL_RESEARCH BLOCKED, default-off runtime
  surface, versioned-prefix parity, no credential leakage in health/providers/models, V1 acceptance mode,
  fail-closed edition parsing.

Executed commands and results:

```
python scripts/verify_public_edition.py            -> exit 0, status PASS, 24/24 checks
POEMSEED_STUDIO_EDITION=INTERNAL_RESEARCH ...      -> exit 2, status BLOCKED (not claimed as PASS)
python -m pytest -q tests/test_public_edition_boundary.py tests/test_engineering_traceability.py
                                                   -> 9 passed
```

Remaining boundary (declared BLOCKED, not implemented): a separate internal-research deployment with
its own authz/data namespace, packaging exclusion of research-only modules/assets and cross-edition
security tests on a real deployment. See `EDITIONS_AND_BUILD_BOUNDARIES.md`.
