// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { ExperimentalClient } from './api';
import { changeImpactClient, type ImpactNode, type ImpactSource, type ImpactView } from './changeImpactClient';
import { ImpactDecisionPanel } from './ImpactDecisionPanel';
import { checkedDecisionPreview, checkedDecisionRows, type ImpactDecisionRecord } from './changeImpactDecisionContract';

afterEach(cleanup);
function fixture(count = 2) {
  const source: ImpactSource = { kind: 'CHAPTER', id: 'chapter', label: 'Changed source', binding: { version: 2, digest: 'a'.repeat(64) } };
  const nodes: ImpactNode[] = Array.from({ length: count }, (_, index) => ({ key: `PLANNING_NODE:plan-${index}`, kind: 'PLANNING_NODE', id: `plan-${index}`,
    label: `Plan ${index}`, version: 3, status: 'DRAFT', stale: true, locked: index === 0, lock_version: index === 0 ? 1 : 0,
    refresh_candidate: false, refresh_reason: 'ORIGINAL_DOMAIN_MANUAL_REVIEW_REQUIRED', evidence: [] }));
  const view: ImpactView = { source, items: nodes, coverage: 'EXACT_RECORDED_DEPENDENCIES_ONLY', inferred: [], unrecorded_dependencies: 'UNKNOWN', automatic_regeneration: false };
  const rows: ImpactDecisionRecord[] = [];
  const makePreview = (body: any) => ({ source_snapshot: source, preview_digest: 'b'.repeat(64), decision_only: true, automatic_execution: false,
    items: body.selected.map((selected: any) => { const node = nodes.find(node => node.key === selected.key)!; return { key: node.key, kind: node.kind, label: node.label,
      version: node.version, choice: selected.choice, locked: node.locked, stale: node.stale, refresh_candidate: node.refresh_candidate, refresh_reason: node.refresh_reason }; }) });
  const makeSaved = (body: any): ImpactDecisionRecord => ({ id: 'decision-' + rows.length, version: 1, request_id: body.request_id,
    source_snapshot: source, preview_digest: body.preview_digest, current: true, decision_only: true, automatic_execution: false,
    items: body.selected.map((selected: any) => { const node = nodes.find(node => node.key === selected.key)!; return { key: node.key, kind: node.kind, label: node.label,
      version: node.version, current_version: node.version, choice: selected.choice, current: true }; }) });
  const client = { get: vi.fn(async () => ({ items: [...rows] })), post: vi.fn(async (path: string, body: any) => {
    if (path === '/change-impact/decisions/preview') return makePreview(body);
    if (path !== '/change-impact/decisions') throw new Error('Unexpected task/model/lock call');
    const saved = makeSaved(body); rows.push(saved); return saved;
  }) } as unknown as ExperimentalClient;
  const api = changeImpactClient(client);
  return { source, view, nodes, rows, client, api, makePreview, makeSaved };
}
const pick = (index: number, value: string) => fireEvent.change(screen.getByRole('combobox', { name: new RegExp(`^决定 Plan ${index} ·`) }), { target: { value } });
const inspect = async (count = 2) => { fireEvent.click(screen.getByRole('button', { name: `预览 ${count} 项保留 / 重建决定` })); await screen.findByRole('region', { name: '保留与重建决定预览' }); };
const confirm = () => fireEvent.click(screen.getByRole('checkbox', { name: '确认只保存以上决定，保留原成果且不启动任务' }));
const saveButton = () => screen.getByRole('button', { name: '保存保留 / 重建决定' });
const readRows = () => fireEvent.click(screen.getByRole('button', { name: '读取已保存的保留 / 重建决定' }));
const handler = (element: HTMLElement) => (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick;

it('requires explicit choices, preview and consent, saves once, and reopens exact history with no execution or lock changes', async () => {
  const f = fixture(); const mounted = render(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />);
  expect(f.client.post).not.toHaveBeenCalled(); expect(screen.getByRole('button', { name: '预览 0 项保留 / 重建决定' }).hasAttribute('disabled')).toBe(true);
  pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); expect(saveButton().hasAttribute('disabled')).toBe(true); expect(f.rows).toEqual([]);
  expect(screen.getByRole('region', { name: '保留与重建决定预览' }).textContent).toContain('原领域手工核对');
  confirm(); const save = handler(saveButton()); act(() => { save(); save(); });
  await screen.findByText('决定已保存；未锁定、重建或替换任何成果。');
  expect(f.rows).toHaveLength(1); expect(vi.mocked(f.client.post).mock.calls.map(call => call[0])).toEqual(['/change-impact/decisions/preview', '/change-impact/decisions']);
  const payload: any = vi.mocked(f.client.post).mock.calls[1][1]; expect(payload.selected).toEqual([
    { key: f.nodes[0].key, expected_version: 3, choice: 'KEEP' }, { key: f.nodes[1].key, expected_version: 3, choice: 'REBUILD' }]);
  mounted.unmount(); render(<ImpactDecisionPanel api={f.api} view={structuredClone(f.view)} disabled={false} />); readRows();
  const history = await screen.findByRole('region', { name: '已保存的保留与重建决定' });
  expect(history.textContent).toContain('保留原成果'); expect(history.textContent).toContain('请求重建（仅记录意图）'); expect(history.textContent).toContain('保存 v3 / 当前 v3');
  expect(f.client.post).toHaveBeenCalledTimes(2); expect((screen.getByRole('combobox', { name: /^决定 Plan 0/ }) as HTMLSelectElement).value).toBe('');
});

it('retires old consent callbacks after uncheck/recheck and after replacing the reviewed choice set', async () => {
  const f = fixture(); render(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />); pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm();
  const retained = handler(saveButton()); act(() => { confirm(); retained(); }); expect(f.rows).toEqual([]);
  confirm(); act(retained); expect(f.rows).toEqual([]);
  pick(1, 'KEEP'); await inspect(); confirm(); act(retained); expect(f.rows).toEqual([]);
  fireEvent.click(saveButton()); await waitFor(() => expect(f.rows).toHaveLength(1)); expect(f.rows[0].items[1].choice).toBe('KEEP');
});

it.each(['disabled', 'view', 'client'])('does not revive old preview across %s ABA, even after a fresh consent', async kind => {
  const f = fixture(); const mounted = render(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />); pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm();
  const retained = handler(saveButton());
  mounted.rerender(<ImpactDecisionPanel api={kind === 'client' ? fixture().api : f.api} view={kind === 'view' ? structuredClone(f.view) : f.view} disabled={kind === 'disabled'} />);
  mounted.rerender(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />); act(retained); expect(f.rows).toEqual([]);
  pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm(); act(retained); expect(f.rows).toEqual([]);
  fireEvent.click(saveButton()); await waitFor(() => expect(f.rows).toHaveLength(1));
});

it('drops prior-client late preview and prior-source history without exposing old records', async () => {
  const old = fixture(); let finish!: (value: unknown) => void;
  old.client.post = vi.fn(() => new Promise(resolve => { finish = resolve; })) as ExperimentalClient['post'];
  const mounted = render(<ImpactDecisionPanel api={changeImpactClient(old.client)} view={old.view} disabled={false} />); pick(0, 'KEEP'); pick(1, 'REBUILD');
  fireEvent.click(screen.getByRole('button', { name: '预览 2 项保留 / 重建决定' }));
  const next = fixture(); mounted.rerender(<ImpactDecisionPanel api={next.api} view={next.view} disabled={false} />);
  await act(async () => finish(old.makePreview({ selected: [{ key: old.nodes[0].key, choice: 'KEEP' }, { key: old.nodes[1].key, choice: 'REBUILD' }] })));
  expect(screen.queryByRole('region', { name: '保留与重建决定预览' })).toBeNull(); expect(next.client.post).not.toHaveBeenCalled();
});

it('keeps the exact request after uncertain Save and recovers from original history without a duplicate POST', async () => {
  const f = fixture(), normal = f.client.post;
  f.client.post = vi.fn(async (path, body) => { const result = await normal(path, body); if (path === '/change-impact/decisions') throw new Error('lost response'); return result; }) as ExperimentalClient['post'];
  render(<ImpactDecisionPanel api={changeImpactClient(f.client)} view={f.view} disabled={false} />); pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm(); fireEvent.click(saveButton());
  await screen.findByRole('button', { name: '使用同一请求核对保存' }); expect(f.rows).toHaveLength(1); expect(screen.getByRole('combobox', { name: /^决定 Plan 0/ }).hasAttribute('disabled')).toBe(true);
  readRows(); await screen.findByText('已从原保存记录核对此请求，未重复新增决定。'); expect(f.client.post).toHaveBeenCalledTimes(2);
});

it('allows only explicit same-request retry after uncertainty and never retries in the background', async () => {
  const f = fixture(), normal = f.client.post; let failed = false;
  f.client.post = vi.fn(async (path, body) => { if (path === '/change-impact/decisions' && !failed) { failed = true; throw new Error('network'); } return normal(path, body); }) as ExperimentalClient['post'];
  render(<ImpactDecisionPanel api={changeImpactClient(f.client)} view={f.view} disabled={false} />); pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm(); fireEvent.click(saveButton());
  const retry = await screen.findByRole('button', { name: '使用同一请求核对保存' }); expect(f.client.post).toHaveBeenCalledTimes(2); fireEvent.click(retry);
  await waitFor(() => expect(f.rows).toHaveLength(1)); const calls = vi.mocked(f.client.post).mock.calls.filter(call => call[0] === '/change-impact/decisions'); expect(calls).toHaveLength(2); expect(calls[0][1]).toEqual(calls[1][1]);
});

it('keeps an uncertain request recoverable after a parent busy ABA while retiring its old retry callback', async () => {
  const f = fixture(), normal = f.client.post; let failed = false;
  f.client.post = vi.fn(async (path, body) => { if (path === '/change-impact/decisions' && !failed) { failed = true; throw new Error('network'); } return normal(path, body); }) as ExperimentalClient['post'];
  const api = changeImpactClient(f.client), mounted = render(<ImpactDecisionPanel api={api} view={f.view} disabled={false} />);
  pick(0, 'KEEP'); pick(1, 'REBUILD'); await inspect(); confirm(); fireEvent.click(saveButton());
  const retained = handler(await screen.findByRole('button', { name: '使用同一请求核对保存' }));
  mounted.rerender(<ImpactDecisionPanel api={api} view={f.view} disabled />); mounted.rerender(<ImpactDecisionPanel api={api} view={f.view} disabled={false} />);
  act(retained); expect(f.client.post).toHaveBeenCalledTimes(2);
  fireEvent.click(screen.getByRole('button', { name: '使用同一请求核对保存' })); await waitFor(() => expect(f.rows).toHaveLength(1));
  const saves = vi.mocked(f.client.post).mock.calls.filter(call => call[0] === '/change-impact/decisions'); expect(saves[0][1]).toEqual(saves[1][1]);
});

it('refuses wrong response scope/tuple/automatic authority and bounds selections without silently adding a 21st node', async () => {
  const f = fixture(21); render(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />);
  for (let index = 0; index < 21; index++) pick(index, 'KEEP'); await inspect(20);
  expect((vi.mocked(f.client.post).mock.calls[0][1] as any).selected).toHaveLength(20); expect((screen.getByRole('combobox', { name: /^决定 Plan 20 / }) as HTMLSelectElement).value).toBe('');
  const selected = [{ key: f.nodes[0].key, expected_version: 3, choice: 'KEEP' as const }], original = f.makePreview({ selected });
  for (const modified of [{ ...original, automatic_execution: true }, { ...original, source_snapshot: { ...f.source, id: 'foreign' } },
    { ...original, source_snapshot: { ...f.source, binding: { version: 9 } } }, { ...original, items: [{ ...original.items[0], version: 4 }] }]) expect(() => checkedDecisionPreview(modified, f.source, selected)).toThrow();
  expect(() => checkedDecisionRows({ items: Array(26).fill({}) }, f.source)).toThrow();
});

it('hides loaded private decisions after original authority denies a read and drops stale late history', async () => {
  const f = fixture(); f.rows.push(f.makeSaved({ selected: [{ key: f.nodes[0].key, choice: 'KEEP' }], request_id: 'old-intent', preview_digest: 'b'.repeat(64) }));
  const mounted = render(<ImpactDecisionPanel api={f.api} view={f.view} disabled={false} />); readRows(); await screen.findByRole('region', { name: '已保存的保留与重建决定' });
  vi.mocked(f.client.get).mockRejectedValue(new ApiError({ status: 403, code: 'FORBIDDEN', message: 'Denied' })); readRows(); await screen.findByText('当前决定内容不可用，请重新读取有权限的影响范围。');
  expect(screen.queryByText(/old-intent/)).toBeNull(); expect(screen.queryByRole('region', { name: '已保存的保留与重建决定' })).toBeNull();
  const next = fixture(); mounted.rerender(<ImpactDecisionPanel api={next.api} view={next.view} disabled={false} />);
  let finish!: (value: unknown) => void; vi.mocked(next.client.get).mockImplementation(() => new Promise(resolve => { finish = resolve; }) as any); readRows();
  mounted.rerender(<ImpactDecisionPanel api={f.api} view={structuredClone(f.view)} disabled={false} />); await act(async () => finish({ items: [f.rows[0]] }));
  expect(screen.queryByRole('region', { name: '已保存的保留与重建决定' })).toBeNull();
});
