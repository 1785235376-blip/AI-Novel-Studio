"""Additive M1 media execution keeps every protected job and original suite."""
import hashlib
from pathlib import Path
import re
import subprocess


ROOT = Path(__file__).resolve().parents[1]


def test_media_job_is_explicit_bounded_and_has_real_official_prerequisites():
    source = (ROOT / ".github/workflows/cloud-ci.yml").read_text()
    job = re.search(r"^  v2-independent-media:\n(.*?)(?=^  [\w-]+:\n|\Z)", source, re.M | re.S).group(0)
    assert "runs-on: ubuntu-24.04" in job and "timeout-minutes: 25" in job
    assert "persist-credentials: false" in job and "pnpm install --frozen-lockfile" in job
    assert "sudo apt-get update" in job and "sudo apt-get install -y --no-install-recommends ffmpeg" in job
    for receipt in ("ffmpeg-version.txt", "ffprobe-version.txt", "media-package-provenance.txt"):
        assert receipt in job
    assert "dpkg-query -W ffmpeg" in job
    assert job.index("sudo apt-get install") < job.index("playwright.independent-live.config.ts")
    assert "set -o pipefail" in job and "if-no-files-found: error" in job
    assert "github.sha" in job and "github.run_attempt" in job
    assert "continue-on-error" not in job and "|| true" not in job and "--pass-with-no-tests" not in job
    for block in re.findall(r"^        run: \|\n((?:          .*\n)+)", job, re.M):
        result = subprocess.run(["bash", "-n"], input=block, text=True, capture_output=True)
        assert result.returncode == 0, result.stderr


def test_original_live_config_bytes_restored_and_media_subset_remains_additive():
    old = (ROOT / "frontend/playwright.v2-live.config.ts").read_bytes()
    # Independently measured from the published M0 file, not refreshed in CI.
    assert hashlib.sha256(old).hexdigest() == "dbbf62ee540feed65c69e7cd1a16d732220c240b0b016b868de24e91bfc14a36"
    media = (ROOT / "frontend/playwright.independent-live.config.ts").read_text()
    assert "v2-(independent-studio|asset-relationships)-live" in media
    assert "workers: 1" in media and "retries: 0" in media and "timeout: 180000" in media
    assert "reuseExistingServer: false" in media
