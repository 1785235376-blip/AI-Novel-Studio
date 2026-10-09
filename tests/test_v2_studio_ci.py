"""Independent studio browser prerequisites stay explicit and fail closed."""
from pathlib import Path
import re


def test_v2_media_browser_job_requires_real_decoders_before_journeys():
    root = Path(__file__).resolve().parents[1]
    source = (root / '.github/workflows/cloud-ci.yml').read_text()
    job = re.search(r'^  v2-creative-browser:\n(.*?)(?=^  [\w-]+:\n|\Z)', source, re.M | re.S).group(0)
    assert job.index('sudo apt-get install -y --no-install-recommends ffmpeg') < job.index('playwright.v2-live.config.ts')
    assert 'v2-ffmpeg-version.txt' in job and 'v2-ffprobe-version.txt' in job
    assert "assert shutil.which('ffmpeg') and shutil.which('ffprobe')" in job
    assert 'continue-on-error' not in job and '--pass-with-no-tests' not in job
    assert 'timeout-minutes: 25' in job


def test_studio_browser_config_preserves_legacy_spec_and_real_default_off_override():
    root = Path(__file__).resolve().parents[1]
    source = (root / 'frontend/playwright.v2-live.config.ts').read_text()
    assert 'v2-(creative|independent-studio|asset-relationships)-live' in source
    assert "...servers('default-off', 8018, 5178, false)" in source
    assert "...servers('acceptance-mode', 8019, 5179, true, true)" in source
    assert 'V1_ACCEPTANCE_MODE: String(acceptance)' in source
    assert 'retries: 0' in source and 'reuseExistingServer: false' in source
