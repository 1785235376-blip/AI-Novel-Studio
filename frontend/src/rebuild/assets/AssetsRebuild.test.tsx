// @vitest-environment jsdom
// [HERMIA-FE-20261022 R6] 资产页按原型重做：真实接口、诚实空态、送到模块需确认、无内部编号
import {describe, it, expect, vi, afterEach, beforeEach} from 'vitest';
import {render, screen, fireEvent, cleanup, waitFor} from '@testing-library/react';
import {AssetsRebuild, assetKind, integrityLabel} from './AssetsRebuild';
const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
let assets: any[] = []; let trash: any[] = []; const calls: string[] = [];
beforeEach(() => { vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
  calls.push(`${init?.method || 'GET'} ${url}`);
  if (url.includes('/references')) return json({asset_id: 'a1', items: [{collection: 'chapters', id: 'ch-9f3', field: 'x', version: 2, status: 'ACTIVE'}], total: 1, coverage: [], other_project_references_scanned: false, deletion_policy: 'x'});
  if (url.includes('asset-trash')) return json({items: trash, total: trash.length});
  if (url.includes('/assets')) return json(assets);
  return json({});
})); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); assets = []; trash = []; calls.length = 0; });
const A = {id: 'a1-77ab', novel_id: 'n1', filename: '雾港参考.jpg', kind: 'image', media_type: 'image/jpeg', size: 2048, sha256: 'deadbeefcafe', created_at: '', updated_at: '', version: 3, provenance: {origin: 'upload', integrity: 'partial'}};
describe('AssetsRebuild', () => {
  // [HERMIA-FE-20261025 DUI P0-3] Repro: a failed read must show ONE error state with retry, never the empty-library copy too.
  it('read failure: single error state + 重试, no empty-library copy, no raw HTTP text', async () => {
    vi.stubGlobal('fetch', vi.fn((url: string) => url.includes('asset-trash') ? json({items: []}) : Promise.resolve(new Response('{"detail":"Not Found"}', {status: 404, headers: {'Content-Type': 'application/json'}}))));
    render(<AssetsRebuild novelId="n1" />);
    const alert = await screen.findByRole('alert');
    expect(alert.textContent).toContain('资产库暂时读不到');
    expect(screen.queryByText('库里还没有资产')).toBeNull();
    expect(document.body.textContent).not.toMatch(/404|Not Found/);
    expect(screen.getByRole('button', {name: '重试'})).toBeTruthy();
  });
  it('empty library: honest empty copy, 导入… is the page primary, no fake lineage', async () => {
    render(<AssetsRebuild novelId="n1" />);
    await screen.findByText('库里还没有资产');
    const p = document.querySelectorAll('.ast-ws .mw-head .nv-btn--primary');
    expect(p).toHaveLength(1); expect(p[0].textContent).toBe('导入…');
    expect(screen.getByText('尚未选中内容')).toBeTruthy();
    expect(document.body.textContent).not.toMatch(/已校验|AssetInspector|W-UX|n1/);
  });
  it('select: lineage facts in Chinese, used-in from references, no ids/hashes on screen', async () => {
    assets = [A];
    render(<AssetsRebuild novelId="n1" shellMode="pro" />);
    fireEvent.click(await screen.findByText('雾港参考.jpg'));
    expect(screen.getByText('部分')).toBeTruthy();
    expect(screen.getByText('本地导入')).toBeTruthy();
    await waitFor(() => expect(document.querySelector('[data-ast-used]')?.textContent).toBe('小说章节'));
    expect(document.body.textContent).not.toMatch(/a1-77ab|deadbeef|ch-9f3|partial|upload/);
  });
  it('send to module requires pick + confirm; no write calls', async () => {
    assets = [A]; const onSend = vi.fn();
    render(<AssetsRebuild novelId="n1" onSendToModule={onSend} />);
    fireEvent.click(await screen.findByText('雾港参考.jpg'));
    fireEvent.click(document.querySelector('#astSend')!);
    fireEvent.click(document.querySelector('[data-ast-send-target="EDIT"]')!);
    expect(onSend).not.toHaveBeenCalled();
    fireEvent.click(document.querySelector('[data-ast-send-confirm]')!);
    expect(onSend).toHaveBeenCalledWith('EDIT');
    expect(calls.filter(c => !c.startsWith('GET'))).toEqual([]);
  });
  it('filter empty + trash restore uses real endpoint', async () => {
    assets = [A]; trash = [{...A, id: 't1', filename: '旧图.png'}];
    render(<AssetsRebuild novelId="n1" shellMode="pro" />);
    await screen.findByText('雾港参考.jpg');
    fireEvent.click(document.querySelector('.ast-filters [data-astf="音频"]')!);
    expect(screen.getByText('这个类型下还没有资产。')).toBeTruthy();
    fireEvent.click(document.querySelector('[data-astf="trash"]')!);
    fireEvent.click(await screen.findByRole('button', {name: '恢复'}));
    await waitFor(() => expect(calls).toContain('POST /api/novels/n1/assets/t1/restore'));
  });
  it('helpers', () => {
    expect(assetKind({kind: 'file', media_type: 'audio/flac'})).toBe('音频');
    expect([integrityLabel('ok'), integrityLabel('partial'), integrityLabel(undefined)]).toEqual(['已校验', '部分', '未核实']);
  });
  it('[U4] mode gating: normal hides 引用关系/回收站/血缘; pro shows them; pro→normal falls back to 资产库 keeping selection', async () => {
    assets = [A];
    const {rerender} = render(<AssetsRebuild novelId="n1" shellMode="basic" />);
    fireEvent.click(await screen.findByText('雾港参考.jpg'));
    expect(screen.queryByRole('button', {name: '引用关系'})).toBeNull();
    expect(document.querySelector('[data-astf="trash"]')).toBeNull();
    expect(document.querySelector('[data-pro-only="lineage"]')).toBeNull();
    expect(screen.getByText('资产信息')).toBeTruthy();
    expect(document.querySelector('#astSend')).toBeTruthy();
    rerender(<AssetsRebuild novelId="n1" shellMode="pro" />);
    expect(document.querySelector('[data-pro-only="lineage"]')).toBeTruthy();
    fireEvent.click(document.querySelector('[data-astf="trash"]')!);
    expect(document.querySelector('.ast-ws')?.getAttribute('data-ast-view')).toBe('trash');
    rerender(<AssetsRebuild novelId="n1" shellMode="basic" />);
    await waitFor(() => expect(document.querySelector('.ast-ws')?.getAttribute('data-ast-view')).toBe('lib'));
    expect(document.querySelector('.ast-tile[aria-selected="true"]')).toBeTruthy();
  });
});
