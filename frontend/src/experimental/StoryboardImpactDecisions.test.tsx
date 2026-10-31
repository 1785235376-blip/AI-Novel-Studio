// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { changeImpactClient } from './changeImpactClient';
import { StoryboardImpactDecisions } from './StoryboardImpactDecisions';
import { checkedStoryboardImpact } from './storyboardImpactContract';

afterEach(cleanup);
function response(count = 1) {
  return { source: { kind: 'CREATIVE_STORYBOARD', id: 'board', label: 'Storyboard · board',
    binding: { version: 1, digest: 'a'.repeat(64), incarnation_digest: 'c'.repeat(64) } },
  coverage: 'EXACT_AUTHORIZED_DIRECT_STORYBOARD_GRAPH_REFERENCES_ONLY', other_owner_coverage: 'NOT_EVALUATED',
  unrecorded_dependencies: 'UNKNOWN', inferred: [], automatic_regeneration: false, truncated: false, target_limit: 20,
  items: Array.from({ length: count }, (_, index) => ({ key: 'CREATIVE_GRAPH_NODE:' + index.toString(16).padStart(64, '0'),
    kind: 'CREATIVE_GRAPH_NODE', id: `graph/Board${index}`, label: `Original graph · Board${index}`, version: 1,
    status: 'SAVED', feature: 'narrative_production_v2', stale: false, locked: false, lock_version: 0,
    refresh_candidate: false, refresh_reason: 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED',
    evidence_type: 'EXACT_SAVED_DIRECT_STORYBOARD_REFERENCE', evidence: [{ key: 'CREATIVE_STORYBOARD:board',
      label: 'Storyboard · board', state: 'CURRENT', recorded_version: 1, current_version: 1 }] })) };
}
function fixture() {
  const value = response(), saved: unknown[] = [];
  const client = { get: vi.fn(async () => ({ items: saved })), post: vi.fn(async (path: string, body: any) => {
    if (path === '/change-impact/query') return structuredClone(value);
    if (path === '/change-impact/decisions/preview') return { source_snapshot: value.source, preview_digest: 'b'.repeat(64),
      decision_only: true, automatic_execution: false, items: body.selected.map((item: any) => ({ ...value.items[0], choice: item.choice })) };
    if (path !== '/change-impact/decisions') throw new Error('Unexpected execution or mutation');
    const row = { id: 'intent', version: 1, request_id: body.request_id, source_snapshot: value.source, preview_digest: body.preview_digest,
      decision_only: true, automatic_execution: false, current: true, items: body.selected.map((item: any) => ({ ...value.items[0],
        choice: item.choice, current_version: 1, current: true })) };
    saved.push(row); return row;
  }) } as unknown as ExperimentalClient;
  return { client, api: changeImpactClient(client), saved };
}
async function inspect() {
  fireEvent.change(screen.getByLabelText('Storyboard 文档 ID'), { target: { value: 'board' } });
  fireEvent.click(screen.getByRole('button', { name: '读取 Storyboard 直接影响' }));
  await screen.findByRole('combobox', { name: /^决定 Original graph/ });
}

it('uses the original explicit decision preview/consent/save flow and never execution endpoints', async () => {
  const f = fixture(); render(<StoryboardImpactDecisions api={f.api} />);
  expect(f.client.post).not.toHaveBeenCalled(); await inspect();
  fireEvent.change(screen.getByRole('combobox', { name: /^决定 Original graph/ }), { target: { value: 'REBUILD' } });
  fireEvent.click(screen.getByRole('button', { name: '预览 1 项保留 / 重建决定' }));
  await screen.findByRole('region', { name: '保留与重建决定预览' });
  const save = screen.getByRole('button', { name: '保存保留 / 重建决定' });
  expect(save.hasAttribute('disabled')).toBe(true);
  fireEvent.click(screen.getByRole('checkbox')); fireEvent.click(save);
  await waitFor(() => expect(f.saved).toHaveLength(1));
  expect(vi.mocked(f.client.post).mock.calls.map(([path]) => path)).toEqual([
    '/change-impact/query', '/change-impact/decisions/preview', '/change-impact/decisions']);
  fireEvent.click(screen.getByRole('button', { name: '读取已保存的保留 / 重建决定' }));
  expect(await screen.findByRole('region', { name: '已保存的保留与重建决定' })).toBeTruthy();
});

it.each(['source', 'client'])('discards a delayed private observation after %s replacement', async kind => {
  const f = fixture(); let finish!: (v: unknown) => void;
  vi.mocked(f.client.post).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const rendered = render(<StrictMode><StoryboardImpactDecisions api={f.api} /></StrictMode>);
  fireEvent.change(screen.getByLabelText('Storyboard 文档 ID'), { target: { value: 'board' } });
  fireEvent.click(screen.getByRole('button', { name: '读取 Storyboard 直接影响' }));
  if (kind === 'source') fireEvent.change(screen.getByLabelText('Storyboard 文档 ID'), { target: { value: 'other' } });
  else rendered.rerender(<StrictMode><StoryboardImpactDecisions api={fixture().api} /></StrictMode>);
  const stale = response(); stale.items[0].label = 'PRIVATE_OLD_SCOPE';
  await act(async () => finish(stale));
  expect(screen.queryByText(/PRIVATE_OLD_SCOPE/)).toBeNull();
  expect(screen.queryByRole('combobox')).toBeNull();
  expect(screen.getByRole('button', { name: '读取 Storyboard 直接影响' }).hasAttribute('disabled')).toBe(false);
});

it.each([0, 20])('accepts the complete bounded %i target observation', count => {
  expect(checkedStoryboardImpact(response(count), 'board').items).toHaveLength(count);
});
it.each(['over-limit', 'truncated', 'execution', 'duplicate', 'wrong-source', 'missing-incarnation'])('fails closed on %s owner response', kind => {
  const value = response(kind === 'over-limit' ? 21 : 2);
  if (kind === 'truncated') value.truncated = true;
  if (kind === 'execution') value.items[0].refresh_candidate = true;
  if (kind === 'duplicate') value.items[1] = value.items[0];
  if (kind === 'wrong-source') value.source.id = 'foreign';
  if (kind === 'missing-incarnation') (value.source.binding as any).incarnation_digest = undefined;
  expect(() => checkedStoryboardImpact(value, 'board')).toThrow(ApiError);
});
it('clears the decision surface when a fresh original read is denied', async () => {
  const f = fixture(); render(<StoryboardImpactDecisions api={f.api} />); await inspect();
  vi.mocked(f.client.post).mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'denied' }));
  fireEvent.click(screen.getByRole('button', { name: '读取 Storyboard 直接影响' }));
  await screen.findByRole('alert'); expect(screen.queryByRole('combobox')).toBeNull();
});
