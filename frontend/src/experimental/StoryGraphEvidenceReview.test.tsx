// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StoryGraphPanel } from './StoryGraphPanel';
import { matchesStoryEvidence } from './StoryGraphEvidenceReview';
import { experimentalClient } from './api';
import type { Chapter } from '../api';
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const evidence = { record_id: 'relation-1', record_version: 3, chapter_id: 'ch1', source_versions: { ch1: { version: 2, digest: 'original-digest' } } };
const row = { id: 'relation-1', version: 3, chapter_id: 'ch1', title: '铜钥关系', kind: 'STORY_RELATION', stale: false, status: 'APPROVED', sources: evidence.source_versions, data: { subject: {kind: 'CHARACTER', id: 'alice'}, object: {kind: 'LOCATION', id: 'port'}, statement: '铜钥在港口', layer: 'WORLD_FACT', relation: 'LOCATED_AT', evidence: [{chapter_id: 'ch1', start: 2, quote: '铜钥在港口'}] } };
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status});
function setup(original: unknown = row, status = 200) {
  const fetch = vi.fn(async (url: string, init: RequestInit) => {
    if (url.endsWith('/records/relation-1')) return reply(original, status);
    if (url.includes('/query?')) return reply({perspective:'AUTHOR', nodes:[], visible_count:1, edges:[{id:row.id, ...row.data, calendar:'story', world_time:null, valid_from:null, valid_to:null, evidence}]});
    if (url.endsWith('/catalog')) return reply({items:[{kind:'CHAPTER',id:'ch1'}, row.data.subject, row.data.object]});
    if (init.method === 'POST') return reply(row);
    return reply({items: url.endsWith('/records') ? [row] : []});
  });
  vi.stubGlobal('fetch', fetch);
  const client = experimentalClient('novel', {sessionToken:'session'});
  const view = render(<StoryGraphPanel client={client} chapter={{id:'ch1'} as Chapter} mindEnabled />);
  return {fetch, client, view};
}
async function inspect() {
  fireEvent.click(await screen.findByRole('button', {name:'查询当前视图'}));
  fireEvent.click(await screen.findByRole('button', {name:'核对原关系证据'}));
}
it('reads the exact original evidence and copies approved content into the existing pending form without writing', async () => {
  const {fetch} = setup(); await inspect();
  fireEvent.click(await screen.findByRole('button', {name:'将原关系复制到待审表单'}));
  expect((screen.getByLabelText('记录标题') as HTMLInputElement).value).toBe('铜钥关系');
  expect(screen.getByText(/摘要 original-digest/)).toBeTruthy();
  expect(screen.getByText(/不提供历史原文回放/)).toBeTruthy();
  expect(fetch.mock.calls.filter(([, init]) => init.method !== 'GET')).toHaveLength(0);
  fireEvent.change(screen.getByLabelText('记录标题'), {target:{value:'人工修正候选'}});
  fireEvent.click(screen.getByRole('button', {name:'保存待审记录'}));
  await waitFor(() => expect(fetch.mock.calls.some(([url, init]) => url.endsWith('/records') && init.method === 'POST')).toBe(true));
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/approve'))).toBe(false);
});
it('preserves dirty author inputs while inspecting and blocks replacement and viewpoint departure', async () => {
  setup(); await screen.findByLabelText('记录标题');
  fireEvent.change(screen.getByLabelText('记录标题'), {target:{value:'未保存创作'}});
  await inspect();
  const button = await screen.findByRole('button', {name:'将原关系复制到待审表单'});
  expect((button as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', {name:'人物可知视图'}) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('记录标题') as HTMLInputElement).value).toBe('未保存创作');
  fireEvent.click(screen.getByRole('button', {name:'取消编辑'}));
  await waitFor(() => expect((button as HTMLButtonElement).disabled).toBe(false));
});
it.each([
  [{...row, version:4}, 200], [{...row, sources:{ch1:{version:2,digest:'changed'}}},200], [{...row, stale:true},200], [{detail:'denied'},403], [{detail:'missing'},404],
])('withholds original edits after mismatch or unavailable read', async (original, status) => {
  setup(original, status); await inspect();
  await waitFor(() => expect(screen.queryByText('正在读取…')).toBeNull());
  expect(screen.queryByRole('button', {name:'将原关系复制到待审表单'})).toBeNull();
});
it('clears evidence on owner replacement and never loads author evidence in character mode', async () => {
  const {fetch, view} = setup(); await inspect(); await screen.findByText(/摘要 original-digest/);
  view.rerender(<StoryGraphPanel client={experimentalClient('other', {sessionToken:'other'})} chapter={{id:'ch1'} as Chapter} mindEnabled />);
  expect(screen.queryByText(/摘要 original-digest/)).toBeNull();
  fireEvent.click(screen.getByRole('button', {name:'人物可知视图'})); fetch.mockClear();
  expect(screen.queryByRole('button', {name:'核对原关系证据'})).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.endsWith('/records/relation-1'))).toBe(false);
});
it('rejects absent, extra or malformed source pins rather than assuming equality', () => {
  expect(matchesStoryEvidence(row, evidence)).toBe(true);
  for (const sources of [{}, {...evidence.source_versions, extra:{version:1,digest:'x'}}, {ch1:{version:2,digest:''}}, {ch1:null}]) expect(matchesStoryEvidence({...row,sources}, evidence)).toBe(false);
});
it('keeps pending original reads out of a replaced owner', async () => {
  let finish: (response: Response) => void = () => {};
  const {fetch, view} = setup();
  const normal = fetch.getMockImplementation()!;
  fetch.mockImplementation((url, init) => url.endsWith('/records/relation-1') ? new Promise(resolve => {finish = resolve;}) : normal(url, init));
  await inspect();
  await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/records/relation-1'))).toBe(true));
  view.rerender(<StoryGraphPanel client={experimentalClient('new-owner', {sessionToken:'new'})} chapter={{id:'ch1'} as Chapter} mindEnabled />);
  finish(reply(row));
  await screen.findByLabelText('记录标题');
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
  expect((screen.getByLabelText('记录标题') as HTMLInputElement).value).toBe('');
});
it('blocks a previously inspected target as soon as original author input changes', async () => {
  setup(); await inspect();
  const load = await screen.findByRole('button', {name:'将原关系复制到待审表单'});
  fireEvent.change(screen.getByLabelText('记录标题'), {target:{value:'保留我'}});
  fireEvent.click(load);
  expect((screen.getByLabelText('记录标题') as HTMLInputElement).value).toBe('保留我');
  expect((load as HTMLButtonElement).disabled).toBe(true);
});
it('invalidates original inspection on changed query inputs including A to B to A and on requery', async () => {
  setup(); await inspect(); await screen.findByText(/摘要 original-digest/);
  fireEvent.change(screen.getByLabelText('查询章节 ID'), {target:{value:'ch2'}});
  fireEvent.change(screen.getByLabelText('查询章节 ID'), {target:{value:'ch1'}});
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
  await inspect(); await screen.findByText(/摘要 original-digest/);
  fireEvent.click(screen.getByRole('button', {name:'查询当前视图'}));
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
});
it('withholds malformed record metadata and author-only quote pins', () => {
  for (const changed of [ {...row, stale:undefined}, {...row, data:{...row.data, relation:'INVENTED'}}, {...row, data:{...row.data, subject:{kind:'UNKNOWN',id:'alice'}}}, {...row, data:{...row.data, evidence:[{chapter_id:'other',quote:'private',start:0}]}} ]) expect(matchesStoryEvidence(changed, evidence)).toBe(false);
  for (const changed of [{...evidence, record_id:''}, {...evidence, record_version:undefined}, {...evidence, source_versions:{ch1:{version:2,digest:' '}}}]) expect(matchesStoryEvidence(row, changed as typeof evidence)).toBe(false);
});
it('invalidates original inspection on original record directory refresh', async () => {
  setup(); await inspect(); await screen.findByText(/摘要 original-digest/);
  fireEvent.click(screen.getByRole('button', {name:'刷新实验记录'}));
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
});
it('withholds old query inspection while a replacement query is pending', async () => {
  const {fetch} = setup(); await inspect(); await screen.findByText(/摘要 original-digest/);
  let finish: (response: Response) => void = () => {};
  const normal = fetch.getMockImplementation()!;
  fetch.mockImplementation((url, init) => url.includes('/query?') ? new Promise(resolve => {finish = resolve;}) : normal(url, init));
  fireEvent.click(screen.getByRole('button', {name:'查询当前视图'}));
  expect(screen.queryByRole('button', {name:'核对原关系证据'})).toBeNull();
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
  finish(reply({perspective:'AUTHOR', nodes:[], edges:[], visible_count:0}));
  await screen.findByText('可见关系：0');
  expect(screen.queryByLabelText('原语义记录证据核对')).toBeNull();
});
it('withholds malformed original form temporal and event metadata', () => {
  for (const data of [{world_time:{}}, {world_time:0.5}, {valid_from:4,valid_to:4}, {calendar:{}}, {scene_id:[]}, {observer_id:1}]) expect(matchesStoryEvidence({...row,data:{...row.data,...data}}, evidence)).toBe(false);
  for (const event_order of [-1, 0.5, 1000001, {}]) expect(matchesStoryEvidence({...row,event_order}, evidence)).toBe(false);
});
