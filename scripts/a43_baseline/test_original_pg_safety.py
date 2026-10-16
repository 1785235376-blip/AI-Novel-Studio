"""Unchanged safety claim must be RED on the fixed historical baseline."""
import json, os
from pathlib import Path

def test_move_preserves_same_external_id_document_and_uuid():
    result = json.loads(Path(os.environ['A43_PG_OBSERVATION']).read_text())
    assert result['layer'] == 'REAL_POSTGRESQL_16_ORIGINAL_REPOSITORY_SYNTHETIC_MANUSCRIPT'
    assert result['move_exception'] is None, result['move_exception']
    assert result['before']['document'] == result['after']['document'], 'A43-03: same external ID resolves another manuscript after real PostgreSQL move'
    before = next(x for x in result['before_rows'] if x['number'] == result['before']['number'])
    after = next(x for x in result['after_rows'] if x['number'] == result['after']['number'])
    assert before['uuid'] == after['uuid']
