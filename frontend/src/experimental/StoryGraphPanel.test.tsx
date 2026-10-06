// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StoryGraphPanel } from './StoryGraphPanel';
import { experimentalClient } from './api';
import type { Chapter } from '../api';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const chapter = { id: 'ch1', title: '第一章', version: 1 } as Chapter;
const catalog = { items: [{ id: 'alice', kind: 'CHARACTER', label: '阿澄' }, { id: 'bob', kind: 'CHARACTER', label: '沈墨' }, { id: 'city', kind: 'LOCATION', label: '月港' }, { id: 'ch1', kind: 'CHAPTER', label: '第一章' }] };
const client = () => experimentalClient('novel', { sessionToken: 'session' });
const reply = (value: unknown, status = 200) => new Response(JSON.stringify(value), { status });
const evidence = { record_id: 'e1', record_version: 2, chapter_id: 'ch1', source_versions: { ch1: { version: 1, digest: 'digest' } } };
const draft = { id: 'r1', version: 1, kind: 'STORY_RELATION', status: 'REVIEW', title: '世界关系', chapter_id: 'ch1', event_order: 0, sources: { ch1: { version: 1 } }, data: { statement: '沈墨藏着铜钥', subject: { kind: 'CHARACTER', id: 'bob' }, object: { kind: 'LOCATION', id: 'city' }, relation: 'ABOUT', layer: 'WORLD_FACT' } };

it('creates a typed relation with selected real IDs, no raw JSON form', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => init.method === 'POST' ? reply(draft, 201) : reply(url.endsWith('/catalog') ? catalog : { items: [] }));
  vi.stubGlobal('fetch', fetch);
  render(<StoryGraphPanel client={client()} chapter={chapter} mindEnabled />);
  await screen.findByLabelText('记录标题');
  fireEvent.change(screen.getByLabelText('记录标题'), { target: { value: '世界关系' } });
  fireEvent.change(screen.getByLabelText('关系起点'), { target: { value: 'CHARACTER:bob' } });
  fireEvent.change(screen.getByLabelText('关系终点'), { target: { value: 'LOCATION:city' } });
  fireEvent.change(screen.getByLabelText('关系陈述'), { target: { value: '沈墨藏着铜钥' } });
  fireEvent.click(screen.getByRole('button', { name: '保存待审记录' }));
  await waitFor(() => expect(fetch.mock.calls.filter(([, init]) => init.method === 'POST')).toHaveLength(1));
  const sent = JSON.parse(fetch.mock.calls.find(([, init]) => init.method === 'POST')![1].body as string);
  expect(sent.kind).toBe('STORY_RELATION');
  expect(sent.data.subject).toEqual({ kind: 'CHARACTER', id: 'bob' });
  expect(sent.data.world_time).toBe(null);
  expect(screen.queryByText(/JSON/)).toBeNull();
});

it('keeps the draft on conflict and sends the reviewed expected version', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => init.method === 'PUT' ? reply({ detail: { code: 'EXPERIMENTAL_VERSION_CONFLICT' } }, 409) : reply(url.endsWith('/catalog') ? catalog : url.includes('/world/') ? { items: [] } : { items: [draft] }));
  vi.stubGlobal('fetch', fetch);
  render(<StoryGraphPanel client={client()} chapter={chapter} mindEnabled />);
  fireEvent.click(await screen.findByRole('button', { name: '编辑语义记录' }));
  fireEvent.change(screen.getByLabelText('记录标题'), { target: { value: '保留草稿' } });
  fireEvent.click(screen.getByRole('button', { name: '保存待审记录' }));
  await waitFor(() => expect(screen.getByRole('alert').textContent).toContain('EXPERIMENTAL_VERSION_CONFLICT'));
  expect((screen.getByLabelText('记录标题') as HTMLInputElement).value).toBe('保留草稿');
  expect(JSON.parse(fetch.mock.calls.find(([, init]) => init.method === 'PUT')![1].body as string).expected_version).toBe(1);
});

it('unmounts omniscient records, never requests them in character mode, and shows only visible counts', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? catalog : url.includes('/query?') ? { edges: [], nodes: [], visible_count: 0 } : url.endsWith('/character-context') ? { known_facts: [], secrets: [], false_beliefs: [{ text: '我相信港口安全', evidence_status: 'HYPOTHESIS', epistemic_status: 'FALSE_BELIEF', evidence }] } : url.includes('/world/') ? { items: [] } : { items: [draft] }));
  vi.stubGlobal('fetch', fetch);
  render(<StoryGraphPanel client={client()} chapter={chapter} mindEnabled />);
  await screen.findByText('沈墨藏着铜钥');
  fireEvent.click(screen.getByRole('button', { name: '人物可知视图' }));
  expect(screen.queryByText('沈墨藏着铜钥')).toBeNull();
  expect(screen.queryByLabelText('记录标题')).toBeNull();
  fetch.mockClear();
  fireEvent.change(screen.getByLabelText('视角人物 ID'), { target: { value: 'alice' } });
  fireEvent.click(screen.getByRole('button', { name: '查询当前视图' }));
  await screen.findByText('可见关系：0');
  expect(screen.queryByText('沈墨藏着铜钥')).toBeNull();
  expect(screen.getByText('我相信港口安全')).toBeTruthy();
  expect(fetch.mock.calls.every(([url]) => url.includes('/query?') || url.endsWith('/character-context'))).toBe(true);
  fireEvent.change(screen.getByLabelText('视角人物 ID'), { target: { value: 'bob' } });
  expect(screen.queryByText('我相信港口安全')).toBeNull();
});

it('uses explicit knowledge changes and marks uninferred motives as hypotheses', async () => {
  const fetch = vi.fn(async (url: string, init: RequestInit) => init.method === 'POST' ? reply({}, 201) : reply(url.endsWith('/catalog') ? catalog : url.includes('/world/') ? { items: [] } : { items: [{ ...draft, status: 'APPROVED', version: 2 }] }));
  vi.stubGlobal('fetch', fetch);
  render(<StoryGraphPanel client={client()} chapter={chapter} mindEnabled />);
  await screen.findByLabelText('记录类型');
  fireEvent.change(screen.getByLabelText('记录类型'), { target: { value: 'KNOWLEDGE_EVENT' } });
  fireEvent.change(screen.getByLabelText('记录标题'), { target: { value: '误解' } });
  fireEvent.change(screen.getByLabelText('观察人物'), { target: { value: 'alice' } });
  fireEvent.change(screen.getByLabelText('知识变化'), { target: { value: 'MISUNDERSTAND' } });
  expect((screen.getByLabelText('心智类别') as HTMLSelectElement).value).toBe('FALSE_BELIEF');
  fireEvent.change(screen.getByLabelText('关联已审核关系'), { target: { value: 'r1' } });
  fireEvent.change(screen.getByLabelText('人物信念或心智状态'), { target: { value: '钥匙已遗失' } });
  fireEvent.click(screen.getByRole('button', { name: '保存待审记录' }));
  await waitFor(() => expect(fetch.mock.calls.some(([, init]) => init.method === 'POST')).toBe(true));
  const body = JSON.parse(fetch.mock.calls.find(([, init]) => init.method === 'POST')![1].body as string);
  expect(body.data.evidence_status).toBe('HYPOTHESIS');
  expect(body.data.category).toBe('FALSE_BELIEF');
  expect(body.data.value).toBe('钥匙已遗失');
});

it('does not request psychology or offer knowledge mutations when the mind flag is off', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? catalog : { items: [] }));
  vi.stubGlobal('fetch', fetch);
  render(<StoryGraphPanel client={client()} chapter={chapter} />);
  await screen.findByLabelText('记录类型');
  expect((screen.getByRole('button', { name: '人物可知视图' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('option', { name: '知识与心智事件' })).toBeNull();
  expect(fetch.mock.calls.some(([url]) => url.includes('/world/'))).toBe(false);
});

it('hands off the exact visible character/chapter and exposes explicit local-only opt-out', async () => {
  const fetch = vi.fn(async (url: string) => reply(url.endsWith('/catalog') ? catalog : url.includes('/query?') ? { edges: [], nodes: [], visible_count: 0 } : url.endsWith('/character-context') ? { known_facts: [], secrets: [] } : { items: [] }));
  vi.stubGlobal('fetch', fetch);
  const useCharacter = vi.fn(), exitCharacter = vi.fn();
  render(<StoryGraphPanel client={client()} chapter={chapter} mindEnabled onUseCharacter={useCharacter} onExitCharacter={exitCharacter} activeCharacterId="alice" />);
  fireEvent.click(screen.getByRole('button', { name: '人物可知视图' }));
  fireEvent.change(screen.getByLabelText('视角人物 ID'), { target: { value: 'alice' } });
  fireEvent.click(screen.getByRole('button', { name: '查询当前视图' }));
  fireEvent.click(await screen.findByRole('button', { name: '以此人物视角准备生成' }));
  expect(useCharacter).toHaveBeenCalledWith('alice', 'ch1');
  expect(screen.getByText(/自动正文、选区、风格与规划资料全部排除/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '退出人物生成视角' }));
  expect(exitCharacter).toHaveBeenCalledTimes(1);
  fireEvent.change(screen.getByLabelText('查询世界时间（留空只按叙事顺序）'), { target: { value: '10' } });
  expect(screen.queryByRole('button', { name: '以此人物视角准备生成' })).toBeNull();
  fireEvent.click(screen.getByRole('button', { name: '查询当前视图' }));
  await waitFor(() => expect((screen.getByRole('button', { name: '以此人物视角准备生成' }) as HTMLButtonElement).disabled).toBe(true));
});
