"""Read-only deadline inputs from the original reviewed narrative progress owner.

A status or free-form event is not chapter progress. The atomic owner writes a
link, its typed event, and the subject association together. Resolve the exact
chapter identity through its owner, never by parsing a chapter ID or list order.
"""
from ..collaboration import DEFAULT_WORKSPACE_ID, default_storyline_id, main_branch_id
from ..source_privacy import content_digest


def local_row(row, nid):
    if not isinstance(row, dict) or row.get('project_id') != nid:
        return False
    expected = {'workspace_id': DEFAULT_WORKSPACE_ID,
                'storyline_id': default_storyline_id(nid), 'branch_id': main_branch_id(nid)}
    tagged = any(row.get(key) is not None for key in expected)
    return (not tagged or all(row.get(key) == value for key, value in expected.items())) and (
        row.get('scope') is None or row['scope'] == {'mode': 'local', 'novel_id': nid})


def project_progress(nid, current_chapter, chapters, links, events, threads, foreshadowing):
    """Return verified rule maps and every owner snapshot used to derive them."""
    sources = {'chapter_links': [row for row in links if local_row(row, nid)],
               'threads': [row for row in threads if local_row(row, nid)],
               'foreshadowing': [row for row in foreshadowing if local_row(row, nid)],
               'chapters': {}}
    event_by_id = {row['id']: row for row in events if local_row(row, nid)}
    thread_by_id = {row['id']: row for row in sources['threads']}
    seed_by_id = {row['id']: row for row in sources['foreshadowing']}
    last_progress, payoff_chapter = {}, {}
    for link in sources['chapter_links']:
        kind, progress = link.get('entity_type'), link.get('progress_type')
        if (kind, progress) not in {('PLOT_THREAD', 'ADVANCED'), ('FORESHADOWING', 'PAYOFF')}:
            continue
        cid, version = link.get('chapter_id'), link.get('chapter_version')
        if not isinstance(cid, str) or not cid or type(version) is not int or version < 1:
            continue
        if cid not in sources['chapters']:
            try:
                chapter = chapters.get(cid)
            except (FileNotFoundError, KeyError):
                chapter = None
            sources['chapters'][cid] = None if chapter is None else {
                'chapter_id': chapter.get('id'), 'novel_id': chapter.get('novel_id'),
                'version': chapter.get('version'), 'number': chapter.get('number'),
                'is_archived': bool(chapter.get('is_archived')), 'digest': content_digest(chapter),
                'scope': chapter.get('scope'), 'branch_id': chapter.get('branch_id'),
            }
        source = sources['chapters'][cid]
        if (not source or source['chapter_id'] != cid or source['novel_id'] != nid
                or source['version'] != version or source['is_archived']
                or source['branch_id'] is not None
                or source['scope'] not in (None, {'mode': 'local', 'novel_id': nid})
                or type(source['number']) is not int or not 1 <= source['number'] <= current_chapter):
            continue
        event = event_by_id.get(link.get('event_id'))
        if (not event or event.get('event_type') != f'{kind}:{progress}'
                or event.get('subject_id') != link.get('entity_id')
                or event.get('chapter_version_id') != f'{cid}:v{version}'
                or not isinstance(event.get('payload'), dict)
                or event['payload'].get('link_id') != link.get('id')
                or event['payload'].get('summary') != link.get('summary')
                or event.get('evidence_ids', []) != link.get('evidence_ids', [])):
            continue
        subject_id, number = link.get('entity_id'), source['number']
        if kind == 'PLOT_THREAD':
            subject = thread_by_id.get(subject_id)
            if subject and event['id'] in subject.get('event_ids', []):
                last_progress[subject_id] = max(last_progress.get(subject_id, 0), number)
        else:
            subject = seed_by_id.get(subject_id)
            if subject and subject.get('status') == 'PAYOFF' and subject.get('payoff_event_id') == event['id']:
                payoff_chapter[subject_id] = min(payoff_chapter.get(subject_id, number), number)
    return {'thread_last_progress': last_progress, 'foreshadowing_payoff_chapter': payoff_chapter}, sources
