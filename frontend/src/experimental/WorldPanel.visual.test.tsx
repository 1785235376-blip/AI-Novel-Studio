// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { WorldPanel } from './WorldPanel';
import { experimentalClient, type Row } from './api';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
const characterData = { character_id: 'Character/Exact ID', appearance: '瘦高\n短发', clothing: '深色风衣', distinguishing: '左手旧疤', reference_asset_ids: ['asset/one,exact', 'asset 二'] };
const sceneData = { location_id: 'Place/Exact ID', architecture: '砖楼', material: '水泥', lighting: '暖光', weather: '阴雨', mood: '安静', time_of_day: '黎明', reference_asset_ids: [] };
const oldKinds = ['HISTORY', 'GEOGRAPHY', 'CIVILIZATION', 'ABILITY', 'CHARACTER_EVENT', 'PSYCHOLOGY', 'RELATIONSHIP', 'ABILITY_USE'];
const characterFields = { character_id: '视觉人物 ID', appearance: '外貌', clothing: '服装', distinguishing: '辨识特征' };
const sceneFields = { location_id: '视觉地点 ID', architecture: '建筑形态', material: '材质', lighting: '光照', weather: '天气', mood: '氛围', time_of_day: '时段' };
function fixture(rows: Row[] = [], write?: (method: string, path: string, body: any) => Promise<Response>) {
  const writes: { method: string; path: string; body: any }[] = [];
  const reads: string[] = [];
  vi.stubGlobal('fetch', vi.fn(async (url: string, options: RequestInit) => {
    const path = url.split('/experimental')[1], method = options.method || 'GET';
    if (method !== 'GET') {
      const body = JSON.parse(String(options.body)); writes.push({ method, path, body });
      return write ? write(method, path, body) : new Response(JSON.stringify({}), { status: 200 });
    }
    reads.push(path);
    return new Response(JSON.stringify(path.endsWith('/history') ? { items: [{ data: characterData, version: 1 }] } : { items: path === '/world/records' ? rows : [] }), { status: 200 });
  }));
  const client = experimentalClient('synthetic-project', { sessionToken: '' });
  render(<WorldPanel client={client} />);
  return { writes, reads };
}
async function ready() { await waitFor(() => expect((screen.getByRole('button', { name: '刷新实验记录' }) as HTMLButtonElement).disabled).toBe(false)); }
function change(label: string, value: string) { fireEvent.change(screen.getByLabelText(label), { target: { value } }); }
function choose(kind: string) { change('世界记录类型', kind); }
function fillCharacter() {
  choose('CHARACTER_VISUAL'); change('世界记录标题', '人物视觉设定');
  for (const [key, label] of Object.entries(characterFields)) change(label, characterData[key as keyof typeof characterFields]);
}
function submit() { fireEvent.submit(screen.getByLabelText('世界记录标题').closest('form')!); }
function record(kind = 'CHARACTER_VISUAL', status = 'REVIEW'): Row {
  return { id: 'visual/exact id', kind, title: '已有视觉设定', status, version: 7, chapter_id: null, event_order: 2, data: kind === 'CHARACTER_VISUAL' ? characterData : sceneData };
}

describe('guided world visual authoring through the existing owner', () => {
  it('keeps all eight JSON kinds and exposes the two guided visual kinds', async () => {
    fixture(); await ready();
    const select = screen.getByLabelText('世界记录类型');
    expect(within(select).getAllByRole('option').map(option => (option as HTMLOptionElement).value)).toEqual([...oldKinds, 'CHARACTER_VISUAL', 'SCENE_VISUAL']);
    for (const kind of oldKinds) { choose(kind); expect(JSON.parse((screen.getByLabelText('类型数据（JSON；真实人物 / 地点 / 规则 ID）') as HTMLTextAreaElement).value)).toBeTypeOf('object'); }
    choose('CHARACTER_VISUAL'); expect(screen.getByLabelText('视觉人物 ID')).toBeTruthy();
    expect(screen.queryByLabelText('类型数据（JSON；真实人物 / 地点 / 规则 ID）')).toBeNull();
    choose('SCENE_VISUAL'); expect(screen.getByLabelText('视觉地点 ID')).toBeTruthy();
  });

  it('posts the exact character payload with optional chapter and verbatim reference IDs', async () => {
    const { writes } = fixture(); await ready(); fillCharacter();
    for (const [index, id] of characterData.reference_asset_ids.entries()) { fireEvent.click(screen.getByRole('button', { name: '添加参考资产 ID' })); change(`参考资产 ID ${index + 1}`, id); }
    submit(); await screen.findByText('世界记录已进入审核');
    expect(writes).toEqual([{ method: 'POST', path: '/world/records', body: { kind: 'CHARACTER_VISUAL', title: '人物视觉设定', chapter_id: null, event_order: 0, data: characterData } }]);
    expect(screen.getByText(/参考资产 ID 仅为声明/)).toBeTruthy();
    expect(screen.getByText(/辨识特征保存在世界记录/)).toBeTruthy();
  });

  it('posts every scene field and preserves case and spaces in the existing location ID', async () => {
    const { writes } = fixture(); await ready(); choose('SCENE_VISUAL'); change('世界记录标题', '场景视觉设定');
    for (const [key, label] of Object.entries(sceneFields)) change(label, sceneData[key as keyof typeof sceneFields]);
    change('世界记录来源章节 ID', 'chapter/exact'); change('事件顺序', '3'); submit(); await screen.findByText('世界记录已进入审核');
    expect(writes).toEqual([{ method: 'POST', path: '/world/records', body: { kind: 'SCENE_VISUAL', title: '场景视觉设定', chapter_id: 'chapter/exact', event_order: 3, data: sceneData } }]);
  });

  it('labels required subjects, field lengths and nonnegative integer event order', async () => {
    fixture(); await ready(); choose('CHARACTER_VISUAL');
    for (const [label, maximum] of [['世界记录标题', 240], ['视觉人物 ID', 160], ['外貌', 4000], ['服装', 4000], ['辨识特征', 2000]] as const) expect(document.getElementById(screen.getByLabelText(label).getAttribute('aria-describedby')!)!.textContent).toContain(` / ${maximum} 字符`);
    expect((screen.getByLabelText('视觉人物 ID') as HTMLInputElement).required).toBe(true);
    expect((screen.getByLabelText('世界记录来源章节 ID') as HTMLInputElement).required).toBe(false);
    expect((screen.getByLabelText('事件顺序') as HTMLInputElement).min).toBe('0');
    choose('SCENE_VISUAL');
    for (const [label, maximum] of [['视觉地点 ID', 160], ['建筑形态', 4000], ['材质', 4000], ['光照', 2000], ['天气', 2000], ['氛围', 2000], ['时段', 1000]] as const) expect(document.getElementById(screen.getByLabelText(label).getAttribute('aria-describedby')!)!.textContent).toContain(` / ${maximum} 字符`);
  });

  it('refuses invalid guided submissions even when a synthetic submit bypasses native validation', async () => {
    const { writes } = fixture(); await ready(); fillCharacter();
    for (const [label, bad, restored] of [['视觉人物 ID', '', characterData.character_id], ['视觉人物 ID', 'x'.repeat(161), characterData.character_id], ['世界记录标题', 't'.repeat(241), '人物视觉设定'], ['外貌', 'x'.repeat(4001), characterData.appearance], ['事件顺序', '-1', '0'], ['事件顺序', '1.5', '0']] as const) {
      change(label, bad); submit(); expect(writes).toEqual([]); change(label, restored);
    }
    submit(); await screen.findByText('世界记录已进入审核'); expect(writes).toHaveLength(1);
  });

  it('uses schema character counts and preserves a valid non-BMP profile on edit', async () => {
    const row = record(); row.data = { ...characterData, appearance: '🌙'.repeat(4000), clothing: '雪'.repeat(4000), distinguishing: '🦊'.repeat(2000) };
    row.title = '🌙'.repeat(240);
    const { writes } = fixture([row]); await ready(); fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' }));
    expect((screen.getByRole('button', { name: '保存世界候选' }) as HTMLButtonElement).disabled).toBe(false);
    change('外貌', row.data.appearance + '🌙'); expect(screen.getByLabelText('外貌').getAttribute('aria-invalid')).toBe('true');
    submit(); expect(writes).toEqual([]);
    change('外貌', row.data.appearance); submit(); await screen.findByText('世界记录已进入审核');
    expect(writes[0].body.data).toEqual(row.data); expect(writes[0].body.title).toBe(row.title);
  });

  it('bounds the editable reference list at 50 without silently removing entries', async () => {
    const row = record(); row.data = { ...characterData, reference_asset_ids: Array.from({ length: 49 }, (_, i) => `ref-${i}`) };
    const { writes } = fixture([row]); await ready(); fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' }));
    fireEvent.click(screen.getByRole('button', { name: '添加参考资产 ID' })); change('参考资产 ID 50', 'ref-49');
    expect((screen.getByRole('button', { name: '添加参考资产 ID' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: '移除参考资产 ID 2' }));
    expect((screen.getByLabelText('参考资产 ID 2') as HTMLInputElement).value).toBe('ref-2');
    submit(); await screen.findByText('世界记录已进入审核');
    expect(writes[0].body.data.reference_asset_ids).toEqual(Array.from({ length: 50 }, (_, i) => `ref-${i}`).filter(id => id !== 'ref-1'));
  });

  it.each(['CHARACTER_VISUAL', 'SCENE_VISUAL'])('hydrates %s edits and sends the original expected_version', async kind => {
    const row = record(kind), { writes } = fixture([row]); await ready();
    fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' }));
    expect((screen.getByLabelText('世界记录类型') as HTMLSelectElement).disabled).toBe(true);
    const fields = kind === 'CHARACTER_VISUAL' ? characterFields : sceneFields;
    for (const [key, label] of Object.entries(fields)) expect((screen.getByLabelText(label) as HTMLInputElement).value).toBe(row.data[key]);
    expect(writes).toEqual([]); change('世界记录标题', '编辑后'); submit(); await screen.findByText('世界记录已进入审核');
    expect(writes).toEqual([{ method: 'PUT', path: '/world/records/visual%2Fexact%20id', body: { kind, title: '编辑后', chapter_id: null, event_order: 2, data: row.data, expected_version: 7 } }]);
  });

  it('cancels visual editing without making a request', async () => {
    const { writes } = fixture([record()]); await ready(); fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' }));
    change('辨识特征', '未保存特征'); fireEvent.click(screen.getByRole('button', { name: '取消编辑世界记录' }));
    expect(screen.queryByRole('button', { name: '保存世界候选' })).toBeNull(); expect(writes).toEqual([]);
  });

  it('single-flights a pending save and keeps a failed edit available for explicit retry', async () => {
    let finish!: (response: Response) => void;
    const { writes } = fixture([record()], () => new Promise(resolve => { finish = resolve; }));
    await ready(); fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' })); change('辨识特征', '保留输入');
    submit(); submit(); expect(writes).toHaveLength(1);
    expect((screen.getByRole('button', { name: '保存世界候选' }) as HTMLButtonElement).disabled).toBe(true);
    await act(async () => finish(new Response(JSON.stringify({ code: 'VERSION_CONFLICT' }), { status: 409 })));
    await screen.findByRole('alert'); expect((screen.getByLabelText('辨识特征') as HTMLTextAreaElement).value).toBe('保留输入');
    expect((screen.getByLabelText('世界记录标题') as HTMLInputElement).value).toBe('已有视觉设定');
    submit(); expect(writes).toHaveLength(2); expect(writes[1].body.expected_version).toBe(7);
    await act(async () => finish(new Response('{}', { status: 200 })));
  });

  it('retains review/reopen/history actions with the row version and does not imply a Canon replacement', async () => {
    const row = record('CHARACTER_VISUAL', 'REJECTED'), { writes, reads } = fixture([row]); await ready();
    fireEvent.click(screen.getByRole('button', { name: '重开世界审核' })); await screen.findByText('世界审核已更新'); await ready();
    expect(writes).toEqual([{ method: 'POST', path: '/world/records/visual%2Fexact%20id/reopen', body: { expected_version: 7 } }]);
    fireEvent.click(screen.getByRole('button', { name: '世界记录历史' })); await screen.findByText('世界历史已读取');
    expect(reads).toContain('/world/records/visual%2Fexact%20id/history');
    expect(screen.getByText('世界历史版本').parentElement!.textContent).toContain('左手旧疤');
    choose('CHARACTER_VISUAL'); expect(screen.getByText(/新建视觉记录不会自动替换 Canon/)).toBeTruthy();
  });

  it('preserves but locks the current draft after its record is approved', async () => {
    const row = record();
    const { writes } = fixture([row], async (_method, path) => {
      if (path.endsWith('/approve')) { row.status = 'APPROVED'; row.version = 8; }
      return new Response(JSON.stringify(row), { status: 200 });
    });
    await ready(); fireEvent.click(screen.getByRole('button', { name: '编辑世界记录' })); change('辨识特征', '尚未保存的辨识特征');
    fireEvent.click(screen.getByRole('button', { name: '批准世界候选' })); await screen.findByText('世界审核已更新'); await ready();
    expect(screen.getByText(/此视觉记录现已批准/)).toBeTruthy();
    expect((screen.getByRole('button', { name: '保存世界候选' }) as HTMLButtonElement).disabled).toBe(true);
    const distinguishing = screen.getByLabelText('辨识特征') as HTMLTextAreaElement;
    expect(distinguishing.disabled).toBe(true); expect(distinguishing.value).toBe('尚未保存的辨识特征');
    expect((screen.getByLabelText('世界记录标题') as HTMLInputElement).disabled).toBe(true);
    submit(); expect(writes).toEqual([{ method: 'POST', path: '/world/records/visual%2Fexact%20id/approve', body: { expected_version: 7 } }]);
    expect((screen.getByRole('button', { name: '世界记录历史' }) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('button', { name: '取消编辑世界记录' })); expect(screen.queryByText(/此视觉记录现已批准/)).toBeNull();
    expect(writes).toHaveLength(1);
  });

  it('makes approved visual records visibly immutable while keeping history available', async () => {
    fixture([record('CHARACTER_VISUAL', 'APPROVED')]); await ready();
    expect((screen.getByRole('button', { name: '编辑世界记录' }) as HTMLButtonElement).disabled).toBe(true);
    expect((screen.getByRole('button', { name: '世界记录历史' }) as HTMLButtonElement).disabled).toBe(false);
  });
});
