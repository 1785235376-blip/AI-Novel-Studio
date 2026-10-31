// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.

import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { experimentalClient } from './api';
import { StorySimulatorPanel } from './StorySimulatorPanel';
import { simulatorOwnerNavigation } from './simulatorOwnerNavigation';
import type { SimulatorRun, SimulatorInput } from './storySimulatorClient';

const chapter = { id: 'chapter-one', title: '雨夜', version: 3 } as Chapter;
const catalog = { chapters: [chapter], characters: [{ id: 'alice', name: '小林' }], planning_nodes: [{ id: 'node-one', title: '原有规划', version: 2, chapter_ids: [chapter.id] }], limits: { max_steps: 32, max_branches: 8, max_expansions: 256 }, model_configured: false };
const context = { chapter_id: chapter.id, character_id: 'alice', world_time: null, calendar: 'story', context_digest: 'a'.repeat(64), knowledge: [{ id: 'fact-one', version: 2, text: '钥匙能开门', category: 'KNOWN_FACT' }], goals: [], graph_links: [{ id: 'relation-one', version: 2, text: '钥匙能开门' }] };
const ready: SimulatorRun = { id: 'run-one', version: 1, status: 'READY', stale: false, chapter_id: chapter.id, source_version: 3, expansions: 0, limits: catalog.limits, model_called: false, limitations: ['不提供未来概率。'], routes: [{ id: 'route-1', title: '强行开门', cursor: 0, status: 'PENDING', steps: [], violations: [], unresolved_questions: [], motivation_hypothesis: '作者的忠诚假设', character_goal: '进城' }], provenance: { method: 'bounded-manual-transitions-v1', execution: 'DETERMINISTIC_MANUAL', source_versions: { [chapter.id]: { version: 3, digest: 'b'.repeat(64) } }, context_digest: context.context_digest, input_digest: 'c'.repeat(64) } };
const completed: SimulatorRun = { ...ready, version: 2, status: 'COMPLETED', expansions: 1, routes: [{ ...ready.routes![0], cursor: 1, status: 'COMPLETED', steps: [{ event_id: 'event-1', title: '试着开门', at: 1, applied: false, violations: [{ code: 'UNMET_PREREQUISITE', message: '事件前提尚未满足。' }], question: '钥匙在哪里？', foreshadowing_links: [] }], violations: [{ code: 'UNMET_PREREQUISITE', message: '事件前提尚未满足。' }], unresolved_questions: ['钥匙在哪里？'] }] };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('novel-one', { sessionToken: 'session-one', scope: { workspaceId: 'workspace-one', projectId: 'novel-one', storylineId: 'story-one', branchId: 'branch-one' } });
function transport(initial?: SimulatorRun) {
  let row = initial;
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/catalog')) return reply(catalog);
    if (url.endsWith('/context')) return reply(context);
    if (url.endsWith('/runs/run-one/step')) { row = completed; return reply(row); }
    if (url.endsWith('/runs/run-one/cancel')) { row = { ...ready, version: 2, status: 'CANCELLED' }; return reply(row); }
    if (url.endsWith('/runs/run-one/save')) { row = { ...completed, version: 3, routes: completed.routes!.map(r => ({ ...r, saved_proposal_id: 'proposal-one' })) }; return reply({ proposal_id: 'proposal-one', status: 'REVIEW', run_id: 'run-one' }); }
    if (url.endsWith('/runs/run-one')) return reply(row);
    if (url.endsWith('/runs') && init?.method === 'POST') { row = ready; return reply(row, 201); }
    if (url.endsWith('/runs')) return reply({ items: row ? [row] : [] });
    throw new Error(`Unhandled ${init?.method} ${url}`);
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('reopens the persisted route review after remount without saving again or copying input', async () => {
  const input: SimulatorInput = { chapter_ids: [chapter.id], expected_versions: { [chapter.id]: 3 }, chapter_id: chapter.id, character_id: 'alice', world_time: null, calendar: 'story', node_id: 'node-one', expected_node_version: 2, context_digest: 'original-context-digest', assumptions: ['Author hypothesis'], character_goal: 'Original goal', motivation_hypothesis: 'Unverified motive', knowledge_ids: ['fact-one'], resources: {}, hard_constraints: { forbidden_facts: ['forbidden outcome'], resource_caps: {}, required_final_facts: [] }, max_steps: 4, max_branches: 2, model_id: null, model_budget: 0, routes: [] };
  const navigate = vi.fn(), saved = { ...completed, input, version: 3, routes: completed.routes!.map(route => ({ ...route, saved_proposal_id: 'proposal-one' })) };
  const fetch = transport(saved); vi.stubGlobal('fetch', fetch);
  render(<StorySimulatorPanel client={client()} chapter={chapter} requestedRunId="run-one" onNavigate={simulatorOwnerNavigation(navigate)} />);
  fireEvent.click(await screen.findByRole('button', { name: '重新打开待审规划：强行开门' }));
  expect(navigate).toHaveBeenCalledWith({ kind: 'feature', id: 'proposal-one', feature: 'advanced_planning_v2', task_authority: 'planning_proposal' });
  expect(fetch.mock.calls.every(([, options]) => options?.method === 'GET')).toBe(true);
  expect((screen.getByLabelText('路线 1 名称') as HTMLInputElement).value).toBe('');
  expect(screen.getByText(/人物知识仅为当时明确选择/).textContent).toContain('original-context-digest');
  expect(screen.getByText(/\"forbidden outcome\"/).textContent).toContain('Unverified motive');
  expect(screen.getByText(/来源 chapter-one · v3 · 摘要/).textContent).toContain('b'.repeat(64));
});
it('does not substitute the run list when an exact original run is unavailable or wrong', async () => {
  const fetch = transport(completed);
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => url.endsWith('/runs/missing') ? reply(completed) : fetch(url, init)));
  render(<StorySimulatorPanel client={client()} chapter={chapter} requestedRunId="missing" />);
  await screen.findByText('读取或操作失败，请重试。');
  expect(screen.queryByRole('article', { name: '比较路线 强行开门' })).toBeNull();
  expect((screen.queryByRole('button', { name: '将所选路线另存为待审规划' }) as HTMLButtonElement | null)).toBeNull();
});

it('hides exact run constraints on target ABA and late responses without changing the editable form', async () => {
  let resolveOld!: (value: Response) => void, first = true;
  const base = transport(completed);
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/runs/run-one') && first) { first = false; return new Promise<Response>(resolve => { resolveOld = resolve; }); }
    if (url.endsWith('/runs/run-two')) return reply({ ...completed, id: 'run-two', routes: [{ ...completed.routes![0], title: 'Second run' }] });
    return base(url, init);
  }));
  const owner = client(), view = render(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-one" />);
  await waitFor(() => expect(resolveOld).toBeTypeOf('function'));
  fireEvent.change(screen.getByLabelText('人物目标'), { target: { value: 'Keep current form' } });
  view.rerender(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-two" />);
  await screen.findByRole('article', { name: '比较路线 Second run' });
  view.rerender(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-one" />);
  await screen.findByRole('article', { name: '比较路线 强行开门' });
  await act(async () => resolveOld(reply({ ...completed, routes: [{ ...completed.routes![0], title: 'Late stale run' }] })));
  expect(screen.queryByRole('article', { name: '比较路线 Late stale run' })).toBeNull();
  expect((screen.getByLabelText('人物目标') as HTMLTextAreaElement).value).toBe('Keep current form');
});

it('clears route consent and temporary proposal receipts when the exact target changes', async () => {
  const base = transport(completed);
  vi.stubGlobal('fetch', vi.fn(async (url: string, init?: RequestInit) => url.endsWith('/runs/run-two') ? reply({ ...completed, id: 'run-two' }) : base(url, init)));
  const owner = client(), view = render(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-one" onNavigate={vi.fn()} />);
  const choose = async () => {
    fireEvent.click(await screen.findByLabelText('选择路线 强行开门 另存待审规划'));
    fireEvent.click(screen.getByLabelText('已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划'));
  };
  await choose();
  expect((screen.getByRole('button', { name: '将所选路线另存为待审规划' }) as HTMLButtonElement).disabled).toBe(false);
  view.rerender(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-two" onNavigate={vi.fn()} />);
  await screen.findByRole('article', { name: '比较路线 强行开门' });
  expect((screen.getByLabelText('已核对所选路线的违规、未决问题和动机假设，仅另存为待审规划') as HTMLInputElement).checked).toBe(false);
  expect((screen.getByRole('button', { name: '将所选路线另存为待审规划' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-one" onNavigate={vi.fn()} />);
  await choose(); fireEvent.click(screen.getByRole('button', { name: '将所选路线另存为待审规划' }));
  await screen.findByRole('button', { name: '前往分层规划审核' });
  view.rerender(<StorySimulatorPanel client={owner} chapter={chapter} requestedRunId="run-two" onNavigate={vi.fn()} />);
  await screen.findByRole('article', { name: '比较路线 强行开门' });
  expect(screen.queryByRole('button', { name: '前往分层规划审核' })).toBeNull();
  expect(screen.queryByRole('button', { name: '重新打开待审规划：强行开门' })).toBeNull();
});
