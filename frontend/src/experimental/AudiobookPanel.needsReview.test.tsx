// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ExperimentalClient } from './api';
import { AudiobookPanel } from './AudiobookPanel';

type SegmentRow = Record<string, any> & { id: string };

const segment = (id: string, attributionStatus?: string, over: Record<string, any> = {}): SegmentRow => ({
  id, version: 1, kind: 'DIALOGUE', text: '原文 ' + id, character_id: 'alice', profile_id: 'voice',
  attribution_status: attributionStatus, emotion: 'neutral', speaking_style: '', timing_status: 'UNMEASURED',
  start_ms: null, end_ms: null, locked: false, attribution_evidence: {}, source_start: 0, source_end: 1,
  source_text_digest: 'a'.repeat(64), ...over
});
const planRow = (segments: SegmentRow[], over: Record<string, any> = {}) => ({
  id: 'plan', version: 3, status: 'PENDING_REVIEW', title: '合成有声计划',
  needs_review_count: segments.filter(row => row.attribution_status === 'NEEDS_REVIEW').length,
  duration_ms: null, sources: {}, tracks: [], segments, stale: false, ...over
});
function fakeClient(plan: Record<string, any>) {
  const get = vi.fn(async (path: string) => {
    if (path === '/audiobook/capabilities') return { tts: 'EXISTING', mixer: 'LOCAL', subtitles: 'PARTIAL', alignment: 'NOT_CONFIGURED' };
    if (path === '/audiobook/profiles') return { items: [{ id: 'voice', display_name: '合成声音' }] };
    if (path === '/audiobook/mappings') return { items: [] };
    if (path === '/audiobook/plans') return { items: [plan] };
    throw new Error('unexpected GET ' + path);
  });
  const post = vi.fn(async () => plan), put = vi.fn(async () => plan);
  return { client: { get, post, put, blob: vi.fn() } as unknown as ExperimentalClient, get, post, put };
}
const filterBox = () => screen.getByRole('checkbox', { name: '仅看待核对白' }) as HTMLInputElement;
const wrappers = (container: HTMLElement) => Array.from(container.querySelectorAll<HTMLElement>('[data-audiobook-segment]'));
const visibleIds = (container: HTMLElement) => wrappers(container).filter(node => !node.hidden).map(node => node.getAttribute('data-audiobook-segment'));
const countText = (visible: number, total: number) => screen.getByText('当前可见 ' + visible + ' / 总数 ' + total);
async function openPanel(plan: Record<string, any>) {
  const fake = fakeClient(plan);
  const view = render(<AudiobookPanel client={fake.client} />);
  await screen.findByRole('region', { name: '有声计划详情' });
  expect(wrappers(view.container)).toHaveLength(plan.segments.length);
  return { ...fake, view };
}
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

it('shows every loaded segment by default with the full-plan count', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED'), segment('c', 'NARRATION')]);
  const { view } = await openPanel(plan);
  expect(filterBox().checked).toBe(false);
  expect(visibleIds(view.container)).toEqual(['a', 'b', 'c']);
  countText(3, 3);
  expect(wrappers(view.container).every(node => node.hidden === false)).toBe(true);
});

it('filters exactly by attribution_status NEEDS_REVIEW when enabled', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED'), segment('c', 'NEEDS_REVIEW'), segment('d', 'NARRATION')]);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox());
  expect(visibleIds(view.container)).toEqual(['a', 'c']);
  expect(wrappers(view.container).filter(node => node.hidden).map(node => node.getAttribute('data-audiobook-segment'))).toEqual(['b', 'd']);
  countText(2, 4);
});

it('keeps the original relative order of matching segments and restores the full list on uncheck', async () => {
  const plan = planRow([segment('first'), segment('one', 'NEEDS_REVIEW'), segment('two'), segment('three', 'NEEDS_REVIEW')]);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox());
  expect(visibleIds(view.container)).toEqual(['one', 'three']);
  const texts = wrappers(view.container).filter(node => !node.hidden).map(node => node.textContent);
  expect(texts[0]).toContain('原文 one');
  expect(texts[1]).toContain('原文 three');
  fireEvent.click(filterBox());
  expect(filterBox().checked).toBe(false);
  expect(visibleIds(view.container)).toEqual(['first', 'one', 'two', 'three']);
  countText(4, 4);
});

it('reports no rows when every segment is already reviewed, without claiming the plan is missing', async () => {
  const plan = planRow([segment('a', 'REVIEWED'), segment('b', 'NARRATION')]);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox());
  expect(visibleIds(view.container)).toEqual([]);
  countText(0, 2);
  expect(screen.getByText(/没有待核对白片段/)).toBeTruthy();
});

it('keeps the original empty-plan behaviour and does not misreport it as a filter miss', async () => {
  const plan = planRow([]);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox());
  expect(wrappers(view.container)).toHaveLength(0);
  countText(0, 0);
  expect(screen.queryByText(/没有待核对白片段/)).toBeNull();
});

it('does not treat a missing attribution_status as NEEDS_REVIEW', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', undefined), segment('c')]);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox());
  expect(visibleIds(view.container)).toEqual(['a']);
  countText(1, 3);
});

it('preserves unsaved editor inputs across filter toggles because hidden rows stay mounted', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED')]);
  const { view } = await openPanel(plan);
  const nodeA = wrappers(view.container).find(node => node.getAttribute('data-audiobook-segment') === 'a')!;
  const nodeB = wrappers(view.container).find(node => node.getAttribute('data-audiobook-segment') === 'b')!;
  fireEvent.change(within(nodeA).getByLabelText('片段情绪标签'), { target: { value: '紧张' } });
  fireEvent.change(within(nodeA).getByLabelText('片段人物 ID（旁白为 __narrator__）'), { target: { value: 'bob' } });
  fireEvent.change(within(nodeB).getByLabelText('片段说话风格'), { target: { value: '低声' } });
  fireEvent.click(filterBox());
  expect(nodeB.hidden).toBe(true);
  expect((within(nodeB).getByLabelText('片段说话风格') as HTMLInputElement).value).toBe('低声');
  expect((within(nodeA).getByLabelText('片段情绪标签') as HTMLInputElement).value).toBe('紧张');
  fireEvent.click(filterBox());
  expect(nodeB.hidden).toBe(false);
  expect((within(nodeA).getByLabelText('片段人物 ID（旁白为 __narrator__）') as HTMLInputElement).value).toBe('bob');
  expect((within(nodeB).getByLabelText('片段说话风格') as HTMLInputElement).value).toBe('低声');
  expect(within(nodeA).queryByText(/片段元数据已保存/)).toBeNull();
});

it('never requests the server or saves anything when the filter is toggled', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED')]);
  const { view, get, post, put } = await openPanel(plan);
  const getCalls = get.mock.calls.length;
  fireEvent.click(filterBox()); fireEvent.click(filterBox()); fireEvent.click(filterBox());
  expect(get.mock.calls.length).toBe(getCalls);
  expect(post).not.toHaveBeenCalled();
  expect(put).not.toHaveBeenCalled();
  expect(wrappers(view.container)).toHaveLength(2);
});

it('does not modify the plan data or segment order', async () => {
  const plan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED')]);
  const before = JSON.stringify(plan);
  const { view } = await openPanel(plan);
  fireEvent.click(filterBox()); fireEvent.click(filterBox());
  expect(JSON.stringify(plan)).toBe(before);
  expect(wrappers(view.container).map(node => node.getAttribute('data-audiobook-segment'))).toEqual(['a', 'b']);
});

it('keeps approval bound to the complete plan, not the filtered rows', async () => {
  const readyPlan = planRow([segment('a', 'REVIEWED'), segment('b', 'REVIEWED')]);
  const { post } = await openPanel(readyPlan);
  fireEvent.click(filterBox());
  const approve = screen.getByRole('button', { name: '批准有声计划' }) as HTMLButtonElement;
  expect(approve.disabled).toBe(false);
  fireEvent.click(approve);
  await waitFor(() => expect(post).toHaveBeenCalledWith('/audiobook/plans/plan/approve', { expected_version: 3 }));
  cleanup();
  const blockedPlan = planRow([segment('a', 'NEEDS_REVIEW'), segment('b', 'REVIEWED')]);
  await openPanel(blockedPlan);
  fireEvent.click(filterBox());
  expect((screen.getByRole('button', { name: '批准有声计划' }) as HTMLButtonElement).disabled).toBe(true);
  cleanup();
  const missingProfile = planRow([segment('a', 'REVIEWED'), segment('b', 'REVIEWED', { profile_id: null })]);
  await openPanel(missingProfile);
  fireEvent.click(filterBox());
  expect((screen.getByRole('button', { name: '批准有声计划' }) as HTMLButtonElement).disabled).toBe(true);
});
