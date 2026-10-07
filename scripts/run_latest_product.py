"""Start the recovered product with an explicitly selected existing local model.

No weights are downloaded and no inference is performed during bootstrap.
The normal Local AI discovery, identity, validation and dispatch owners are used.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import secrets
import sys
import time


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-file', type=Path, required=True)
    parser.add_argument('--llama-executable', type=Path, required=True)
    parser.add_argument('--model-endpoint', default='http://127.0.0.1:8091')
    parser.add_argument('--upstream-model', default='qwen-local-recovery')
    parser.add_argument('--context-size', type=int, default=16384)
    parser.add_argument('--port', type=int, default=8051)
    parser.add_argument('--frontend-origin', default='http://127.0.0.1:5209')
    parser.add_argument('--data-dir', type=Path, default=Path('.runtime/full-recovery/product-data'))
    parser.add_argument('--session-file', type=Path, default=Path('.runtime/full-recovery/session.json'))
    parser.add_argument('--license-reviewed', action='store_true', required=True,
                        help='Acknowledge review of this already installed model for the intended local use.')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    sys.path.insert(0, str(root))
    args.data_dir = args.data_dir.resolve()
    args.data_dir.mkdir(parents=True, exist_ok=True)
    args.session_file = args.session_file.resolve()
    args.session_file.parent.mkdir(parents=True, exist_ok=True)
    if args.session_file.exists():
        token = json.loads(args.session_file.read_text(encoding='utf-8'))['token']
    else:
        token = secrets.token_urlsafe(32)
        args.session_file.write_text(json.dumps({'token': token}), encoding='utf-8')
    os.environ.update({
        'PROJECT_ROOT': str(root), 'NOVEL_DATA_PATH': str(args.data_dir), 'STORAGE_BACKEND': 'file',
        'MOCK_PROVIDER': 'false', 'ENABLE_CLOUD': 'false', 'CREATION_PROFILE': 'LOCAL_ONLY',
        'ENABLE_PROVIDER_FALLBACK': 'false', 'ENABLE_LORE_CONTEXT': 'true',
        'ENABLE_NARRATIVE_CONTEXT': 'true', 'ENABLE_CONTEXT_PACK_V2': 'true',
        'ENABLE_CONTINUITY_RULES': 'true', 'ENABLE_OPTIMISTIC_CONCURRENCY': 'true',
        'ENABLE_COLLABORATION_RUNTIME': 'false', 'ENABLE_PACKAGED_RUNTIME': 'false',
        'CREDENTIAL_VAULT_BACKEND': 'memory', 'FRONTEND_ORIGIN': args.frontend_origin,
        'EXPERIMENTAL_FEATURES': ','.join([
            'advanced_planning_v2', 'world_character_engines_v2', 'temporal_story_graph_v2',
            'unified_review_inbox', 'author_context_inspector_v2', 'story_record_versions_v1',
            'finding_review_v1', 'revision_intelligence_v2', 'workspace_tools_v2',
            'writing_recovery_v2', 'workspace_interaction_v1', 'reader_preflight_v2',
        ]),
        'COLLABORATION_DEV_SESSIONS_JSON': json.dumps([{
            'token': token, 'session_id': 'recovery-host-session', 'client_id': 'recovery-host-client',
            'actor_id': 'recovery-author', 'workspace_id': 'recovery-workspace',
        }]),
    })
    from app.dependencies import local_ai_discovery
    from app.model_center.discovery_types import LocalRuntimeInput, RegistrationInput
    existing_runtime = next((row for row in local_ai_discovery.snapshot()['settings']['runtimes']
        if row['type'] == 'LLAMA_CPP' and row['endpoint'] == args.model_endpoint
        and row.get('model_path') == str(args.model_file.resolve())), None)
    runtime = local_ai_discovery.configure_runtime(LocalRuntimeInput(
        name='Recovered local writing model', type='LLAMA_CPP', endpoint=args.model_endpoint,
        model_id=args.upstream_model, modality='TEXT', management='EXTERNAL',
        executable=str(args.llama_executable.resolve()), model_path=str(args.model_file.resolve()),
        context_size=args.context_size,
    ), existing_runtime['id'] if existing_runtime else None)
    scan = local_ai_discovery.start_scan()
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        scan = local_ai_discovery.get_scan(scan['id'])
        if scan['status'] not in {'PENDING', 'RUNNING'}:
            break
        time.sleep(0.2)
    candidates = [item for item in scan.get('candidates', []) if item['runtime_id'] == runtime['id']]
    if len(candidates) != 1:
        raise RuntimeError('Selected local model was not unambiguously discovered')
    candidate = local_ai_discovery.validate(candidates[0]['id'])
    local_ai_discovery.register(candidate['id'])
    local_ai_discovery.configure_registration(candidate['id'], RegistrationInput(license_confirmed=True))
    candidate = local_ai_discovery.enable(candidate['id'])
    receipt = {key: candidate[key] for key in ('id', 'provider_id', 'model_name', 'enabled', 'status', 'verified')}
    receipt.update(api_url=f'http://127.0.0.1:{args.port}', frontend_url=args.frontend_origin,
                   execution_mode='real', startup_inference_performed=False, session_file=str(args.session_file), process_id=os.getpid(), data_dir=str(args.data_dir))
    (args.session_file.parent / 'runtime.json').write_text(json.dumps(receipt, ensure_ascii=False, indent=2), encoding='utf-8')
    print(json.dumps(receipt, ensure_ascii=False), flush=True)
    import uvicorn
    uvicorn.run('app.main:app', host='127.0.0.1', port=args.port)


if __name__ == '__main__':
    main()
