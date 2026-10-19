// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { experimentalClient } from './api';
import { VoiceDirectionPanel } from './VoiceDirectionPanel';

const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const client = () => experimentalClient('novel-voice', { sessionToken: 'token-voice', scope: { branchId: 'branch', projectId: 'novel-voice' } as never });
type Segment = { id: string; version: number; kind: 'NARRATION' | 'DIALOGUE'; text: string; character_id: string | null; profile_id: string; attribution_status: string; locked: boolean; start_ms: number; end_ms: number; direction: Record<string, unknown> };
type Plan = { id: string; version: number; title: string; status: 'DRAFT' | 'PENDING_REVIEW' | 'APPROVED'; needs_review_count: number; voice_direction: boolean; stale: boolean; segments?: Segment[] };

const segment = (id: string, index: number): Segment => ({ id, version: 1, kind: 'NARRATION', text: '原文 ' + id, character_id: '__narrator__', profile_id: 'voice', attribution_status: 'NARRATION', locked: false, start_ms: index * 1000, end_ms: index * 1000 + 1000, direction: { reviewed_text: '原文 ' + id, text_reviewed: true, voice_authorized: true, emotion: 'neutral', speech_rate: 1, pause_ms: 280, pronunciation_rules: [] } });
const makePlan = (over: Partial<Plan> = {}): Plan => ({ id: 'plan', version: 1, title: 'Synthetic voice', status: 'PENDING_REVIEW', needs_review_count: 1, voice_direction: true, stale: false, segments: [segment('A', 0), segment('B', 1), segment('C', 2), segment('D', 3)], ...over });

type ReorderBody = { expected_version: number; segment_ids: string[] };
function transport(initial: Plan, reorder?: (body: ReorderBody) => Promise<Response> | Response | undefined) {
  let current = initial;
  const reorderBodies: ReorderBody[] = [];
  const fetch = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/voice-direction/catalog')) return reply({ plans: [current], mixes: [], mixer: 'local-pcm16-wav-v1', profiles: [{ id: 'voice', display_name: 'Synthetic' }], characters: [{ id: '__narrator__', name: '旁白' }], tts: {} });
    if (url.endsWith('/voice-direction/jobs')) return reply({ items: [] });
    if (url.endsWith('/voice-direction/plans/plan/reorder')) {
      const body = JSON.parse(String(init?.body)) as ReorderBody;
      reorderBodies.push(body);
      const custom = await reorder?.(body);
      if (custom) return custom;
      const byId = new Map((current.segments || []).map(row => [row.id, row]));
      current = { ...current, version: current.version + 1, segments: body.segment_ids.map(id => byId.get(id) as Segment) };
      return reply(current);
    }
    throw new Error('Unhandled ' + url);
  });
  return { fetch, reorderBodies, setPlan: (plan: Plan) => { current = plan; }, getPlan: () => current };
}
async function openPlan(ui: ReturnType<typeof transport>) {
  vi.stubGlobal('fetch', ui.fetch);
  const view = render(<VoiceDirectionPanel client={client()} />);
  await screen.findByText('Synthetic voice · v' + ui.getPlan().version + ' · ' + ui.getPlan().status);
  fireEvent.change(screen.getByLabelText('声音导演有声计划'), { target: { value: 'plan' } });
  return view;
}
const moveDown = () => screen.queryAllByRole('button', { name: '下移片段' });
const trackTimes = () => within(screen.getByLabelText('片段轨道预览')).getAllByRole('listitem').map(item => item.textContent || '');
const sourceOrder = () => screen.queryAllByText(/^原文：/).map(item => (item.textContent || '').replace('原文：原文 ', ''));
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

it('moves a middle segment down by swapping only it with the immediately following segment', async () => {
  const ui = transport(makePlan()); await openPlan(ui);
  fireEvent.click(moveDown()[1]);
  await waitFor(() => expect(ui.reorderBodies).toHaveLength(1));
  expect(ui.reorderBodies[0]).toEqual({ expected_version: 1, segment_ids: ['A', 'C', 'B', 'D'] });
  expect(ui.fetch.mock.calls.find(([url]) => String(url).endsWith('/reorder'))![0]).toMatch(/\/voice-direction\/plans\/plan\/reorder$/);
  await screen.findByText('Synthetic voice · v2 · PENDING_REVIEW');
  expect(sourceOrder()).toEqual(['A', 'C', 'B', 'D']);
});

it('moves the first segment down and the penultimate segment down onto the last position', async () => {
  const first = transport(makePlan({ segments: [segment('A', 0), segment('B', 1), segment('C', 2)] })); await openPlan(first);
  fireEvent.click(moveDown()[0]);
  await waitFor(() => expect(first.reorderBodies).toHaveLength(1));
  expect(first.reorderBodies[0].segment_ids).toEqual(['B', 'A', 'C']);
  cleanup(); vi.unstubAllGlobals();
  const penultimate = transport(makePlan()); await openPlan(penultimate);
  fireEvent.click(moveDown()[2]);
  await waitFor(() => expect(penultimate.reorderBodies).toHaveLength(1));
  expect(penultimate.reorderBodies[0].segment_ids).toEqual(['A', 'B', 'D', 'C']);
});

it('disables move-down on the last segment, on a single segment and on an empty plan', async () => {
  const four = transport(makePlan()); await openPlan(four);
  const buttons = moveDown();
  expect(buttons).toHaveLength(4);
  expect((buttons[0] as HTMLButtonElement).disabled).toBe(false);
  expect((buttons[3] as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(buttons[3]);
  await waitFor(() => expect(four.fetch.mock.calls.length).toBeGreaterThan(0));
  expect(four.reorderBodies).toHaveLength(0);
  cleanup(); vi.unstubAllGlobals();
  const single = transport(makePlan({ segments: [segment('A', 0)] })); await openPlan(single);
  expect(moveDown()).toHaveLength(1);
  expect((moveDown()[0] as HTMLButtonElement).disabled).toBe(true);
  cleanup(); vi.unstubAllGlobals();
  const empty = transport(makePlan({ segments: [] })); await openPlan(empty);
  expect(moveDown()).toHaveLength(0);
  expect(empty.reorderBodies).toHaveLength(0);
});

it('uses the currently loaded plan version as expected_version and never the version captured at mount', async () => {
  const ui = transport(makePlan({ version: 5 })); await openPlan(ui);
  fireEvent.click(moveDown()[0]);
  await waitFor(() => expect(ui.reorderBodies).toHaveLength(1));
  expect(ui.reorderBodies[0].expected_version).toBe(5);
  await screen.findByText('Synthetic voice · v6 · PENDING_REVIEW');
  fireEvent.click(moveDown()[1]);
  await waitFor(() => expect(ui.reorderBodies).toHaveLength(2));
  expect(ui.reorderBodies[1].expected_version).toBe(6);
});

it('keeps the pending-review restriction on the move-down operation itself', async () => {
  const approved = transport(makePlan({ status: 'APPROVED' })); await openPlan(approved);
  expect(moveDown().every(button => (button as HTMLButtonElement).disabled)).toBe(true);
  fireEvent.click(moveDown()[0]);
  await waitFor(() => expect(approved.fetch.mock.calls.length).toBeGreaterThan(0));
  expect(approved.reorderBodies).toHaveLength(0);
  cleanup(); vi.unstubAllGlobals();
  const live = transport(makePlan()); await openPlan(live);
  live.setPlan(makePlan({ status: 'APPROVED', version: 2 }));
  fireEvent.click(screen.getByRole('button', { name: '刷新声音来源与任务' }));
  await screen.findByText('Synthetic voice · v2 · APPROVED');
  expect(moveDown().every(button => (button as HTMLButtonElement).disabled)).toBe(true);
  fireEvent.click(moveDown()[0]);
  await waitFor(() => expect(live.fetch.mock.calls.length).toBeGreaterThan(2));
  expect(live.reorderBodies).toHaveLength(0);
});

it('prevents duplicate move-down submissions while a reorder is running', async () => {
  let finish!: (value: Response) => void;
  const ui = transport(makePlan(), () => new Promise<Response>(resolve => { finish = resolve; })); await openPlan(ui);
  const button = moveDown()[1];
  fireEvent.click(button); fireEvent.click(button);
  await waitFor(() => expect(ui.fetch.mock.calls.some(([url]) => String(url).endsWith('/reorder'))).toBe(true));
  expect(ui.reorderBodies).toHaveLength(1);
  const reordered = makePlan({ version: 2, segments: [segment('A', 0), segment('C', 1), segment('B', 2), segment('D', 3)] });
  ui.setPlan(reordered); finish(reply(reordered));
  await screen.findByText('Synthetic voice · v2 · PENDING_REVIEW');
  expect(sourceOrder()).toEqual(['A', 'C', 'B', 'D']);
});

it('reports a rejected reorder, keeps the previous order and never pretends success', async () => {
  const ui = transport(makePlan(), () => reply({ detail: { code: 'FORBIDDEN' } }, 403)); await openPlan(ui);
  fireEvent.click(moveDown()[1]);
  await screen.findByText(/FORBIDDEN/);
  expect(sourceOrder()).toEqual(['A', 'B', 'C', 'D']);
  expect(screen.queryByText('已调整顺序，字幕绑定会按来源检查')).toBeNull();
  expect(ui.fetch.mock.calls.filter(([url]) => String(url).endsWith('/voice-direction/catalog'))).toHaveLength(1);
});

it('does not silently bump or overwrite state after a version conflict', async () => {
  const ui = transport(makePlan(), () => reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409)); await openPlan(ui);
  fireEvent.click(moveDown()[1]);
  await screen.findByText(/EXPERIMENTAL_VERSION_CONFLICT/);
  fireEvent.click(moveDown()[1]);
  await waitFor(() => expect(ui.reorderBodies).toHaveLength(2));
  expect(ui.reorderBodies.map(body => body.expected_version)).toEqual([1, 1]);
  expect(sourceOrder()).toEqual(['A', 'B', 'C', 'D']);
});

it('sends only the adjacent ID order and never rewrites timing or other segment fields', async () => {
  const plan = makePlan(); const fixture = JSON.stringify(plan);
  const ui = transport(plan); await openPlan(ui);
  fireEvent.click(moveDown()[1]);
  await waitFor(() => expect(ui.reorderBodies).toHaveLength(1));
  expect(Object.keys(ui.reorderBodies[0]).sort()).toEqual(['expected_version', 'segment_ids']);
  expect(JSON.stringify(plan)).toBe(fixture);
  await screen.findByText('Synthetic voice · v2 · PENDING_REVIEW');
  expect(trackTimes()[0]).toContain('0–1000 ms');
  expect(trackTimes()[1]).toContain('2000–3000 ms');
  expect(trackTimes()[2]).toContain('1000–2000 ms');
  expect(trackTimes()[3]).toContain('3000–4000 ms');
});

it('a stale plan hides segments and offers no move-down operation', async () => {
  const ui = transport({ ...makePlan(), stale: true, segments: undefined }); await openPlan(ui);
  await screen.findByText('来源已变化。旧片段已隐藏，请从当前章节重建计划并重新审核。');
  expect(moveDown()).toHaveLength(0);
  expect(ui.reorderBodies).toHaveLength(0);
});
