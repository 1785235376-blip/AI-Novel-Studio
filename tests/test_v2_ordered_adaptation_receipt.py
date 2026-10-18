"""Passive ordered chapter receipts: no provider dispatch or model calls."""
from copy import deepcopy

import pytest

from app.creative import adaptation_receipt as contract
from app.creative.proposals import digest
from test_v2_adaptation_asset_owner import source, request, receipt, route


def snapshots():
    result = []
    for ordinal in (1, 2):
        chapter_id, body = f'chapter-{ordinal}', f'Entire chapter {ordinal}.\n原文。'
        item = {'kind': 'CHAPTER', 'id': chapter_id, 'version': ordinal,
            'label': f'Chapter {ordinal}', 'source_digest': str(ordinal) * 64,
            'citation': None, 'evidence': {'chapter_id': chapter_id, 'chapter_version': ordinal},
            'privacy_level': 'LOCAL_ONLY', 'text': body, 'layer': 'AUTHOR_REFERENCE',
            'untrusted_data': True, 'instructions_allowed': False, 'truncated': False,
            'truncation_reason': None}
        result.append({'ordinal': ordinal, 'chapter_id': chapter_id, 'source_version': ordinal,
            'source_digest': 'a' * 64, 'selected_text': body, 'selection_digest': digest(body),
            'native_source_digest': item['source_digest'], 'native_item': item})
    return result


def ordered():
    sources = snapshots()
    origin = {**source(), 'schema_version': 2, 'sources': sources,
        'ordered_sources_digest': digest(sources), **{key: sources[0][key] for key in
            ('chapter_id', 'source_version', 'source_digest', 'selection_digest')}}
    payload = {**request(), 'context': contract.ordered_context(sources)}
    return origin, payload


def validate(origin, payload):
    return contract.validate_receipt(receipt(origin, payload), source=origin,
        provider_id=payload['provider_id'], model_id=payload['model_id'],
        parameters=contract.asset_parameters(payload, route()))


def test_exact_v2_and_legacy_v1_receipts():
    origin, payload = ordered()
    result = validate(origin, payload)
    assert result['schema_version'] == 2 and result['workflow'] == origin
    assert validate(source(), request())['schema_version'] == 1
    assert contract.validate_source(origin) == origin


@pytest.mark.parametrize('change', [
    lambda c: c.update(chapter=1),
    lambda c: c['explicit_sources']['items'].reverse(),
    lambda c: c['explicit_sources']['items'].pop(),
    lambda c: c['explicit_sources']['items'].append(deepcopy(c['explicit_sources']['items'][0])),
    lambda c: c['explicit_sources']['items'][1].update(text='truncated'),
    lambda c: c['explicit_sources']['items'][1].update(version=5),
    lambda c: c['explicit_sources']['items'][1].update(source_digest='f' * 64),
    lambda c: c['explicit_sources']['items'][1].update(label='different'),
    lambda c: c['explicit_sources']['items'][1].update(privacy_level='CLOUD_ALLOWED'),
    lambda c: c['explicit_sources']['items'][1].update(truncated=True),
    lambda c: c['explicit_sources'].update(instructions_allowed=True),
    lambda c: c['explicit_sources'].update(untrusted_data=1),
])
def test_request_context_must_match_snapshots_exactly(change):
    origin, payload = ordered()
    change(payload['context'])
    with pytest.raises(ValueError): validate(origin, payload)


@pytest.mark.parametrize('change', [
    lambda s: s.reverse(),
    lambda s: s.pop(),
    lambda s: s[1].update(ordinal=1),
    lambda s: s[1].update(chapter_id=s[0]['chapter_id']),
    lambda s: s[1].update(selected_text='changed'),
    lambda s: s[1]['native_item'].update(truncated=True),
    lambda s: s[1]['native_item'].update(instructions_allowed=True),
    lambda s: s[1].update(unexpected='extension'),
])
def test_even_rehashed_malformed_snapshots_rejected(change):
    origin, payload = ordered()
    change(origin['sources'])
    origin['ordered_sources_digest'] = digest(origin['sources'])
    with pytest.raises(ValueError): contract.validate_source(origin)


def test_anchor_and_order_digest_are_binding_and_no_v1_downgrade():
    origin, payload = ordered()
    for key, value in [('source_version', 4), ('ordered_sources_digest', 'f' * 64), ('schema_version', 1)]:
        tampered = {**origin, key: value}
        with pytest.raises(ValueError): contract.validate_source(tampered)
    with pytest.raises(ValueError): validate(source(), payload)
    with pytest.raises(ValueError): validate(origin, request())


def test_limits_are_characters_and_total_budget():
    sources = snapshots()
    for row in sources:
        row['selected_text'] = '界' * 8000
        row['selection_digest'] = digest(row['selected_text'])
        row['native_item']['text'] = row['selected_text']
    assert contract.validate_ordered_sources(sources, digest(sources)) == sources
    sources[1]['selected_text'] += 'x'
    sources[1]['native_item']['text'] = sources[1]['selected_text']
    sources[1]['selection_digest'] = digest(sources[1]['selected_text'])
    with pytest.raises(ValueError): contract.validate_ordered_sources(sources, digest(sources))


@pytest.mark.parametrize(('count', 'characters', 'valid'), [(16, 1, True), (17, 1, False), (4, 8000, True), (5, 8000, False)])
def test_source_count_and_aggregate_character_limits(count, characters, valid):
    template = snapshots()[0]
    sources = []
    for ordinal in range(1, count + 1):
        row = deepcopy(template)
        row.update(ordinal=ordinal, chapter_id=f'chapter-{ordinal}', selected_text='x' * characters)
        row['selection_digest'] = digest(row['selected_text'])
        row['native_item'].update(id=row['chapter_id'], text=row['selected_text'],
            evidence={'chapter_id': row['chapter_id'], 'chapter_version': row['source_version']})
        sources.append(row)
    if valid:
        assert contract.validate_ordered_sources(sources, digest(sources)) == sources
    else:
        with pytest.raises(ValueError): contract.validate_ordered_sources(sources, digest(sources))


from test_v2_adaptation_asset_owner import owner, rig, create as create_asset, lease


def test_v2_receipts_round_trip_through_existing_asset_dispatcher(owner):
    origin, payload = ordered()
    with lease(owner):
        asset = create_asset(owner, source_receipt=origin,
            parameters=contract.asset_parameters(payload, route()),
            execution_receipt=receipt(origin, payload))
        assert asset['_text_result_origin'] == origin
        assert asset['_text_execution_receipt']['schema_version'] == 2
        reread = owner.assets.get(asset['id'], actor_id=owner.actor)
        assert reread['_text_result_origin']['sources'] == origin['sources']
