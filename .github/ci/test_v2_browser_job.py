"""Additive browser checks cannot consume or weaken the legacy frontend gate."""
import hashlib
from pathlib import Path
import re
import subprocess


WORKFLOW = Path(__file__).resolve().parents[1] / "workflows" / "cloud-ci.yml"


def job(name):
    match = re.search(
        rf"^  {re.escape(name)}:\n(.*?)(?=^  [\w-]+:\n|\Z)",
        WORKFLOW.read_text(encoding="utf-8"), re.MULTILINE | re.DOTALL,
    )
    assert match is not None, name
    return match.group(0)


def test_original_frontend_gate_is_preserved_byte_for_byte():
    # The complete frontend job at d444901, before the additive V2 browser
    # insertion: all original checks, if conditions, evidence and 25m cap.
    assert hashlib.sha256(job("frontend").encode()).hexdigest() == "fbfe69540e4a9d5a48a43d1bc3d44c06e2909271c78c4fb932a5b0a687c04798"


def test_v2_browser_job_has_independent_finite_fail_closed_suites():
    source = job("v2-creative-browser")
    assert "timeout-minutes: 25" in source
    assert "persist-credentials: false" in source
    assert "pnpm install --frozen-lockfile" in source
    assert "python -m pip check" in source
    assert source.count("pnpm exec playwright test") == 2
    assert source.count("set -o pipefail") == 2
    assert "playwright.v2-live.config.ts" in source
    assert "playwright.creative.config.ts --update-snapshots=none" in source
    assert "if: success() || failure()" in source
    assert "continue-on-error" not in source
    assert "|| true" not in source and "--pass-with-no-tests" not in source
    assert "needs: frontend" not in source
    assert "if: always() && env.CI_RECEIPTS != ''" in source
    assert "if-no-files-found: error" in source
    assert "github.sha" in source and "github.run_attempt" in source


def test_v2_browser_shell_blocks_are_syntactically_valid():
    source = job("v2-creative-browser")
    commands = re.findall(r"^        run: \|\n((?:          .*\n)+)", source, re.MULTILINE)
    assert len(commands) == 5
    for command in commands:
        result = subprocess.run(["bash", "-n"], input=command, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr
