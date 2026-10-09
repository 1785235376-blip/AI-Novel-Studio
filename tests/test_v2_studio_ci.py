"""Independent studio browser prerequisites stay explicit and fail closed."""
from pathlib import Path
import re


def test_v2_media_browser_job_requires_real_decoders_before_journeys():
    root = Path(__file__).resolve().parents[1]
    source = (root / '.github/workflows/cloud-ci.yml').read_text()
    job = re.search(r'^  v2-creative-browser:\n(.*?)(?=^  [\w-]+:\n|\Z)', source, re.M | re.S).group(0)
    # A new media fixture may require installed decoders, but must not change
    # the original job's provisioning behavior. Its setup records real tools
    # and fails before media creation if either executable is unavailable.
    fixture = (root / 'frontend/tests/e2e/v2-independent-studio-live.spec.ts').read_text()
    helper = (root / 'scripts/v2_media_prerequisites.mjs').read_text()
    assert fixture.index('await verifyInstalledMediaTools()') < fixture.index("await executeFixtureTool('ffmpeg'")
    assert 'independent-video-installed-tools' in fixture and 'independent-video-prerequisite-failure' in fixture
    assert "['ffmpeg', 'ffprobe']" in helper and "execute(tool, ['-version'], MEDIA_PROBE_LIMITS)" in helper
    assert 'timeout: 5000' in helper and 'maxBuffer: 64 * 1024' in helper and "throw failure" in helper
    assert 'install_attempted: false' in helper and 'sudo apt-get' not in job + helper
    assert 'continue-on-error' not in job and '--pass-with-no-tests' not in job
    assert 'timeout-minutes: 25' in job


def test_studio_browser_config_preserves_legacy_spec_and_real_default_off_override():
    root = Path(__file__).resolve().parents[1]
    legacy = (root / 'frontend/playwright.v2-live.config.ts').read_text()
    source = (root / 'frontend/playwright.independent-live.config.ts').read_text()
    assert 'testMatch: /v2-creative-live' in legacy
    assert 'v2-(independent-studio|asset-relationships)-live' in source
    assert "...servers('default-off', 8018, 5178, false)" in source
    assert "...servers('acceptance-mode', 8019, 5179, true, true)" in source
    assert 'V1_ACCEPTANCE_MODE: String(acceptance)' in source
    assert 'retries: 0' in source and 'reuseExistingServer: false' in source
