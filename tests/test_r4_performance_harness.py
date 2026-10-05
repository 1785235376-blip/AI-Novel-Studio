"""Deterministic benchmark helper contracts, not latency acceptance evidence."""
import hashlib
import json
from pathlib import Path

import pytest

from scripts.measure_r4_large_project import (
    CHAPTERS, QUERIES, SAMPLES, SIZES, WARMUPS, han_count, percentile,
    prefix_han, safe_environment, summary, synthetic_fixture,
)


@pytest.mark.parametrize('size', SIZES)
def test_fixture_has_exact_han_count_and_is_reproducible(size):
    first, second = synthetic_fixture(size), synthetic_fixture(size)
    assert first == second
    assert len(first['chapters']) == CHAPTERS
    assert len(first['characters']) == 3
    assert len(first['story_routes']) == 2
    assert sum(han_count(row['content']) for row in first['chapters']) == size
    assert max(han_count(row['content']) for row in first['chapters']) - min(han_count(row['content']) for row in first['chapters']) <= 1
    assert all(han_count(row['title']) == 0 for row in first['chapters'])
    content = '\n'.join(row['content'] for row in first['chapters'])
    for expected in ('阿澄', '乔岚', '沈墨', '尚不知道', '误以为', '时间冲突', '伏笔已经过期', '同名船只', '再次解释'):
        assert expected in content
    for absent in QUERIES[-2:]:
        assert absent not in content
    assert hashlib.sha256(content.encode()).hexdigest() == hashlib.sha256('\n'.join(row['content'] for row in second['chapters']).encode()).hexdigest()


def test_han_count_excludes_unicode_punctuation_emoji_and_combining_marks():
    assert han_count('中，文。𠀀👩🏽‍💻e\u0301') == 3
    assert prefix_han('甲，乙👩🏽‍💻丙', 2) == '甲，乙'
    assert prefix_han('甲', 0) == ''
    with pytest.raises(ValueError): prefix_han('甲', 2)


def test_measurement_bounds_and_failure_misses_are_not_filtered():
    assert WARMUPS == 3 and SAMPLES == 30
    samples = [{'duration_ms': n, 'status': 200, 'item_count': 1} for n in range(1, 29)]
    samples += [{'duration_ms': 900, 'status': 200, 'item_count': 0},
                {'duration_ms': 1100, 'status': 503, 'truncated': True}]
    result = summary(samples)
    assert result['sample_count'] == 30 and result['p50_ms'] == 15 and result['p95_ms'] == 900
    assert result['misses'] == result['http_errors'] == result['truncated_samples'] == 1
    assert result['samples'] == samples
    assert percentile([], .95) is None


def test_environment_does_not_inherit_credentials_database_or_profiles(monkeypatch, tmp_path):
    for key in ('OPENAI_API_KEY', 'DATABASE_URL', 'HOME', 'NOVEL_DATA_PATH', 'PYTHONPATH', 'EXPERIMENTAL_FEATURES', 'HTTP_PROXY'):
        monkeypatch.setenv(key, 'do-not-inherit')
    env = safe_environment(tmp_path, False)
    assert 'do-not-inherit' not in json.dumps(env)
    assert not {'OPENAI_API_KEY', 'DATABASE_URL', 'PYTHONPATH', 'HTTP_PROXY'} & env.keys()
    assert env['ENABLE_CLOUD'] == env['ENABLE_PROVIDER_FALLBACK'] == env['MOCK_PROVIDER'] == 'false'
    assert env['EXPERIMENTAL_FEATURES'] == ''
    assert Path(env['NOVEL_DATA_PATH']).parent == tmp_path
    assert safe_environment(tmp_path, True)['EXPERIMENTAL_FEATURES'] == 'workspace_tools_v2'


@pytest.mark.parametrize('size', [0, 3999, 1_000_001])
def test_invalid_fixture_sizes_rejected(size):
    with pytest.raises(ValueError): synthetic_fixture(size)


@pytest.mark.file_backend_only
def test_flags_off_worker_uses_real_mounted_file_api_and_no_network(tmp_path):
    import subprocess
    import sys
    from scripts.measure_r4_large_project import ROOT
    (tmp_path / '.r4-owned').write_text('owned test fixture')
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/measure_r4_large_project.py'),
                             '--worker', '100000', '--mode', 'off'],
                            cwd=ROOT, env=safe_environment(tmp_path, False),
                            text=True, capture_output=True, timeout=120)
    assert result.returncode == 0, result.stderr
    measured = json.loads(result.stdout)
    assert measured['persisted_han_characters'] == 100000
    assert measured['flags_off_gate'] == {'http_status': 404, 'index_scope_count': 0}
    assert measured['network']['blocked_connect_attempts'] == 0
    assert measured['startup_heavy_modules'] == []
    assert measured['flags_off_chapter_open']['sample_count'] == 30
    assert measured['model_execution_requested'] is False
    assert measured['browser_input_latency'].startswith('NOT_RUN')
