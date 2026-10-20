// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import type { ExperimentalClient } from './api';
import { ProductionLineagePanel } from './ProductionLineagePanel';

const hash = 'a'.repeat(64);
const asset = { id: 'asset-child', label: 'Derived image', version: 2, kind: 'image', digest: hash, deleted: false, integrity: 'VERIFIED', origin: 'DERIVED_PROCESSING', license: { label: 'CC0 declaration', source: 'Author statement', note: '' }, operation: 'Crop', parents: [{ id: 'parent', label: 'Original image', version: 1, digest: hash, state: 'CURRENT' }], sources: [], stale: false, impact: { assets: [], usages: [{ id: 'brief', kind: 'MEDIA_BRIEF', label: 'COVER', version: 1 }], other_dependencies: 'UNKNOWN' } };
const parent = { ...asset, id: 'parent', label: 'Original image', version: 1, origin: 'ORIGINAL_INPUT', parents: [] };
const manifest = { id: 'manifest', version: 1, status: 'RECORDED', created_at: '2026-10-05T10:00:00Z', task_id: 'original-task', task_version: 3, operation: 'cover_generation', input_digest: hash, manifest_digest: hash, adapter_id: 'mock-image-v1', model_id: 'mock-png-v1', parameters: { candidate_count: 2 }, seed: { value: null }, verification: 'MOCK_ONLY', environment: { app_version: '0.7.0', runtime: { python: '3.11', zlib: '1.2' }, adapter_version: '1', adapter_digest: hash, workflow_version: 'r3-media-request-v1', workflow_digest: hash, model_digest: hash, deterministic: true }, outputs: [{ proposal_id: 'old-output', candidate_index: 0, digest: hash }], input_versions: [] };
const preflight = { manifest_id: 'manifest', manifest_version: 1, ready: true, blockers: [], preflight_digest: hash, broker_decision_id: null, broker_decision_version: null, verification: 'SYNTHETIC_PROTOCOL_ONLY', cost: { state: 'KNOWN_SYNTHETIC_ZERO', currency: 'USD', estimate_microusd: 0 }, states: { traceable: true, rebuildable: true, replayable: true, deterministic: true, byte_equal: null } };
const replay = { id: 'replay', version: 1, manifest_id: 'manifest', task_id: 'new-task', task_version: 1, status: 'QUEUED', byte_equal: null, outputs: [], recovery: null, recoverable: false, broker_required: false, reservation_id: null };
function client() {
  return { get: vi.fn(async (path: string) => {
    if (path === '/production/assets') return { items: [parent, asset] };
    if (path.startsWith('/production/assets/')) return path.endsWith('/parent') ? parent : asset;
    if (path === '/production/manifests') return { items: [manifest] };
    if (path === '/media/tasks') return { items: [{ id: 'original-task', version: 3, status: 'SUCCEEDED', operation: 'cover_generation' }] };
    if (path === '/production/replays') return { items: [replay] };
    if (path.endsWith('/export')) return { schema: 'production-public-manifest-v2', manifest_digest: hash, redaction: { raw_prompts: false } };
    throw new Error(path);
  }), post: vi.fn(async (path: string) => path.endsWith('/preflight') ? preflight : path.endsWith('/replay') ? replay : manifest), put: vi.fn(async () => asset), blob: vi.fn() } as unknown as ExperimentalClient;
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('ProductionLineagePanel real API actions', () => {
  it("[migrated variant] reopening reads existing replay result and links to review without approving", async () => {
    const api = client(), read = api.get, navigate = vi.fn();
    api.get = vi.fn(async (path: string) => path === '/production/replays' ? { items: [{ ...replay, status: 'SUCCEEDED', task_version: 3, byte_equal: true, outputs: [{ proposal_id: 'new', candidate_index: 0, digest: hash, status: 'PENDING_REVIEW' }] }] } : read(path)) as ExperimentalClient['get'];
    render(<ProductionLineagePanel client={api} manifestsEnabled onNavigate={navigate} />);
    const history = await screen.findByRole('region', { name: '重放历史' });
    expect(await within(history).findByText('输出逐字节一致：是')).toBeTruthy();
    fireEvent.click(within(history).getByRole('button', { name: '核对确切重放任务' }));
    expect(navigate).not.toHaveBeenCalled();
    fireEvent.click(within(history).getByRole('button', { name: '确认离开并核对确切重放任务' }));
    expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'new-task', feature: 'cover_storyboard_generation', task_authority: 'media' }); expect(api.post).not.toHaveBeenCalled();
  });
});
