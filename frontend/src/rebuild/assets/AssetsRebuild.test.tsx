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
    render(<AssetsRebuild novelId="n1" />);
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
    render(<AssetsRebuild novelId="n1" />);
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
});
