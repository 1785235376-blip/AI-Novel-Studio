"""F3 regression: verifier negatives require REAL preparation and helper rejection.

Hermia's counterexample: when the "different compiled artifact" mutation did not
change the digest, the verifier threw its own expected error and counted a PASS.
These checks require a valid, loadable, really different artifact, an actual
call into the delivered helper and the expected binding code; a deliberately
no-op mutation must make the whole acceptance FAIL (SETUP_ERROR), never PASS.
"""
import base64
import json

from test_r4_revision_intelligence import revision_env
from test_r5_interactive_story import approve, create, interactive_env
from app.experimental.interactive_export_contract import read_zip_safely
from test_interactive_ink_current_artifact import _export_current, _run_verifier, _runtime_env


def test_verifier_negative_artifact_preparation_is_real(interactive_env, tmp_path):
    node, root = _runtime_env()
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    completed, report, _ = _run_verifier(tmp_path, files, node, root, 'negative-setup')
    assert completed.returncode == 0, (completed.stderr or '')[-3000:]
    assert report['result'] == 'PASS'
    preparation = report['different_artifact_preparation']
    assert preparation['digest_changed'] is True
    assert preparation['parse_ok'] is True
    assert preparation['original_sha256'] != preparation['modified_sha256']
    assert preparation['modified_sha256'] != report['compile']['artifact_sha256']
    negatives = report['save_restore_negatives']
    assert len(negatives) >= 8
    for record in negatives:
        assert record['setup_ok'] is True, record
        assert record['entry_called'] is True, record
        assert record['passed'] is True, record
        assert record['actual_code'] == record['expected_code'], record
    artifact_negative = next(item for item in negatives if item['case'] == 'different compiled artifact')
    assert artifact_negative['phase'] == 'REJECTION'
    assert 'did not change' not in str(artifact_negative['message'])


def test_verifier_fails_when_negative_artifact_mutation_is_noop(interactive_env, tmp_path):
    node, root = _runtime_env()
    e = interactive_env
    row = approve(e, create(e))
    value = {'expected_version': row['version']}
    _, out = _export_current(e, row, value)
    prefix = 'interactive-ink-2-3-2-current-artifact-v1-' + row['id'] + '/'
    files = read_zip_safely(base64.b64decode(out['content_base64']), prefix)
    completed, report, _ = _run_verifier(tmp_path, files, node, root, 'fault-noop',
                                         extra_args=['--fault-negative-artifact-noop', 'true'])
    assert completed.returncode != 0, 'a no-op negative preparation must never be accepted'
    assert report is not None and report['result'] == 'FAIL'
    artifact_negative = next(item for item in report['save_restore_negatives']
                             if item['case'] == 'different compiled artifact')
    assert artifact_negative['phase'] == 'SETUP_ERROR'
    assert artifact_negative['setup_ok'] is False and artifact_negative['passed'] is False
    assert artifact_negative['entry_called'] is False
    assert any(failure.get('check') == 'save_restore_negative_setup' for failure in report['failures'])
