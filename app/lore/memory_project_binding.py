"""Private File memory operation identity; never an admission/execution grant."""
from copy import deepcopy
from uuid import UUID, uuid5

FIELD = 'memory_project_binding'
NAMESPACE = UUID('93e54f54-f779-5d9f-a354-fdfcc48bc146')
KEYS = {'schema_version', 'project_incarnation', 'project_id', 'chapter_id', 'chapter_version', 'job_id'}
OTHER_BINDINGS = {'ordinary_project_binding', 'graph_binding', 'adaptation_binding',
                  'creative_director_binding', 'director_image_binding', 'research_ocr_binding',
                  'research_ocr_output_evidence', '_creative_director_terminal_evidence', 'director_image_terminal_v3'}


def create_binding(nid, cid, version, incarnation):
    if not isinstance(incarnation, str) or not incarnation.startswith('file:'):
        raise ValueError('MEMORY_FILE_OWNER_REQUIRED')
    identity = UUID(incarnation[5:])
    if identity.version != 4 or str(identity) != incarnation[5:]:
        raise ValueError('MEMORY_FILE_OWNER_REQUIRED')
    if (not isinstance(nid, str) or not nid or any(c in nid for c in '/\\\x00:')
            or nid in {'.', '..'} or not isinstance(cid, str) or not cid.startswith(nid + ':')
            or not cid[len(nid) + 1:] or type(version) is not int or version < 1):
        raise ValueError('MEMORY_SOURCE_IDENTITY_INVALID')
    # A distinct domain and original incarnation prevent a new owner's enqueue
    # from inheriting an old QUEUED/GENERATING/COMPLETED receipt.
    import json
    jid = str(uuid5(NAMESPACE, 'bound-memory-v1:' + json.dumps(
        [incarnation, nid, cid, version], separators=(',', ':'))))
    return dict(schema_version=1, project_incarnation=incarnation, project_id=nid,
                chapter_id=cid, chapter_version=version, job_id=jid)


def memory_job_binding(item):
    if FIELD not in item:
        return None
    binding = item[FIELD]
    if not isinstance(binding, dict) or set(binding) != KEYS or type(binding['schema_version']) is not int or binding['schema_version'] != 1:
        raise ValueError('MEMORY_BINDING_INVALID')
    expected = create_binding(binding['project_id'], binding['chapter_id'],
                              binding['chapter_version'], binding['project_incarnation'])
    if binding != expected or item.get('id') != binding['job_id'] or item.get('operation') != 'MEMORY_EXTRACTION' or item.get('novel_id') != binding['project_id'] or item.get('chapter_id') != binding['chapter_id']:
        raise ValueError('MEMORY_BINDING_INVALID')
    request = item.get('request')
    if not isinstance(request, dict) or type(request.get('chapter_version')) is not int or request['chapter_version'] != binding['chapter_version']:
        raise ValueError('MEMORY_BINDING_INVALID')
    if OTHER_BINDINGS.intersection(item) or any(item.get(k) is not None for k in ('experimental_origin', 'actor_id', 'workspace_id', 'scope', 'scope_type', 'scope_id')):
        raise ValueError('MEMORY_BINDING_MIXED')
    return deepcopy(binding)
