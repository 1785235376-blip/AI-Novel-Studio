# Evidence index

- `implementer/baseline-adaptation.*`: original exact compatibility run, 5P3F, path-redacted for delivery.
- `implementer/isolated-baseline.*`: fresh canonical isolated run, 5P3F.
- `implementer/flag-only.*` and `flag-only-test.py`: controlled flag-only intervention, 2P1F.
- `implementer/final.*` and `reverse.*`: final test diff, 10P in both orders.
- `independent/REPORT.md`: independent PASS review.
- `independent/reverse.*`: independent 10P with per-test environment restoration checks.
- `independent/sentinel.*`: independent 5P with nonempty initial environment values restored.
- `independent/source-hashes.json`: canonical/worktree hashes of all tracked app/src sources.
- `independent/tracked-difference.json`: sole executable changed file at review freeze, before delivery docs.
- `PROVENANCE.json`: original and published SHA256 values and machine-prefix replacement counts for copied artifacts.
- `SHA256SUMS`: hashes of all published evidence and the delivery report; verify from this evidence directory with `sha256sum -c SHA256SUMS`.

All copied text differs only by replacement of the machine-specific absolute workspace root with the literal `${WORKSPACE}` token. stdout and XML retain original failures and outcomes; no raw logs were reconstructed. Source hash file contents remain evidence of the review-time files. Original shell/Python wrappers are path-redacted snapshots, not the portable entrypoint.

## Portable final rerun

From this evidence directory:

    REPO=/absolute/path/to/checkout PYTHON=/absolute/path/to/existing/.venv/bin/python bash rerun.sh

For the independent sentinel mode:

    REPO=/absolute/path/to/checkout PYTHON=/absolute/path/to/existing/.venv/bin/python MODE=sentinel bash rerun.sh

The helper creates a fresh temporary runtime directory and prints its location. It reuses the independent runner with its real-import, network-denial and per-test environment-restoration checks. It does not recreate historical red results or overwrite captured evidence. Dependencies must already be installed. No packages are installed and no network access is enabled.
