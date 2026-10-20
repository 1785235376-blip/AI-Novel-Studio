// @vitest-environment jsdom
import { Blob as NodeBlob } from 'node:buffer';
import { createHash, webcrypto } from 'node:crypto';
import { act, cleanup, fireEvent, render, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssetBrowserPanel, type AssetBrowserPanelProps } from './AssetBrowserPanel';
import { assetRow, FIXTURE_PROJECT } from './assetBrowserFixtures';

const bytes = 'original audio fixture', digest = createHash('sha256').update(bytes).digest('hex');
const payload = new NodeBlob([bytes], { type: 'audio/wav' }) as Blob;
const createUrl = vi.fn(() => 'blob:comparison'), revokeUrl = vi.fn();
function fixture() {
  const rows = ['asset-left', 'asset-right'].map((id, index) => assetRow({ id, filename: 'compare.wav', kind: 'audio',
    media_type: 'audio/wav', size: bytes.length, sha256: digest, version: index + 1, provenance: null }));
  const readRight = vi.fn(async () => rows[1]);
  const blob = vi.fn(async () => payload);
  const json = vi.fn(async (url: string, method?: string): Promise<unknown> => {
    expect(method).toBe('GET');
    if (url.endsWith('/assets')) return { items: rows };
    return url.endsWith('/asset-left') ? rows[0] : readRight();
  });
  const props: AssetBrowserPanelProps = { projectId: FIXTURE_PROJECT, identity: 'comparison-scope', active: true,
    denied: false, busy: false, isCurrent: () => true, read: work => work(), mutate: vi.fn(),
    transport: { json: <T,>(url: string, method?: string) => json(url, method) as Promise<T>, blob } };
  return { props, rows, readRight, blob, json };
}
async function open(props: AssetBrowserPanelProps) {
  const view = render(<AssetBrowserPanel {...props}/>), ui = within(view.container);
  await waitFor(() => expect(ui.getAllByRole('button', { name: '选择素材 compare.wav' })).toHaveLength(2));
  fireEvent.click(ui.getAllByRole('button', { name: '选择素材 compare.wav' })[0]);
  await waitFor(() => expect((ui.getByRole('button', { name: '打开版本对比' }) as HTMLButtonElement).disabled).toBe(false));
  fireEvent.click(ui.getByRole('button', { name: '打开版本对比' }));
  fireEvent.change(ui.getByRole('combobox', { name: '选择对比版本' }), { target: { value: 'asset-right' } });
  return { ...view, ui };
}
async function right(view: { container: HTMLElement }) {
  await waitFor(() => expect(view.container.querySelector('[data-slot="RIGHT"]')).toBeTruthy());
  return within(view.container.querySelector('[data-slot="RIGHT"]') as HTMLElement);
}
beforeEach(() => {
  createUrl.mockClear(); revokeUrl.mockClear(); vi.stubGlobal('crypto', webcrypto);
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }));
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('asset browser comparison owner wiring', () => {
  it('shows the selected owner on the right and downloads only after explicit action through read', async () => {
    const f = fixture(); f.props.read = vi.fn(work => work()); const view = await open(f.props);
    const target = await right(view); expect(f.blob).not.toHaveBeenCalled();
    const readsBefore = vi.mocked(f.props.read).mock.calls.length;
    fireEvent.click(target.getByRole('button', { name: /读取音频预览/ }));
    await waitFor(() => expect(target.getByLabelText('compare.wav 音频预览')).toBeTruthy());
    expect(f.blob).toHaveBeenCalledTimes(1);
    expect(f.blob).toHaveBeenCalledWith(`/api/projects/${FIXTURE_PROJECT}/studio/assets/asset-right/download`);
    expect(vi.mocked(f.props.read).mock.calls.length).toBe(readsBefore + 1);
    expect(f.props.mutate).not.toHaveBeenCalled();
  });
  it.each([{ version: 9 }, { sha256: 'c'.repeat(64) }, { branch_id: 'foreign-branch' }, { novel_id: 'foreign-project' }, { id: 'wrong-id' }])(
    'rejects a target that no longer matches its disclosed candidate: %j', async patch => {
      const f = fixture(); f.readRight.mockResolvedValue({ ...f.rows[1], ...patch });
      const view = await open(f.props);
      await waitFor(() => expect(view.container.textContent).toContain('对比版本读取失败或已变化'));
      expect(view.container.querySelector('[data-slot="RIGHT"]')).toBeNull(); expect(f.blob).not.toHaveBeenCalled();
    });
  it.each(['active', 'denied', 'identity', 'authority'] as const)('discards late bytes across %s changes, including return to old scope', async change => {
    const f = fixture(); let finish!: (value: Blob) => void;
    f.blob.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const view = await open(f.props), target = await right(view);
    fireEvent.click(target.getByRole('button', { name: /读取音频预览/ }));
    await waitFor(() => expect(f.blob).toHaveBeenCalledTimes(1));
    const changed = change === 'active' ? { active: false } : change === 'denied' ? { denied: true }
      : change === 'identity' ? { identity: 'another-owner' } : { isCurrent: () => false };
    view.rerender(<AssetBrowserPanel {...f.props} {...changed}/>);
    view.rerender(<AssetBrowserPanel {...f.props}/>);
    await act(async () => { finish(payload); });
    expect(createUrl).not.toHaveBeenCalled(); expect(view.container.querySelector('audio')).toBeNull();
  });
  it.each(['active', 'denied', 'identity', 'authority'] as const)('retires already-visible media after %s changes', async change => {
    const f = fixture(), view = await open(f.props), target = await right(view);
    fireEvent.click(target.getByRole('button', { name: /读取音频预览/ }));
    await waitFor(() => expect(view.container.querySelector('audio')).toBeTruthy());
    const node = view.container.querySelector('audio')!;
    fireEvent.play(node); const pause = vi.spyOn(node, 'pause'); pause.mockClear();
    const changed = change === 'active' ? { active: false } : change === 'denied' ? { denied: true }
      : change === 'identity' ? { identity: 'another-owner' } : { isCurrent: () => false };
    view.rerender(<AssetBrowserPanel {...f.props} {...changed}/>);
    expect(view.container.querySelector('audio')).toBeNull(); expect(revokeUrl).toHaveBeenCalledWith('blob:comparison');
    expect(pause).toHaveBeenCalled(); expect(f.blob).toHaveBeenCalledTimes(1);
  });
  it('drops a late target metadata response after selection is cleared', async () => {
    const f = fixture(); let finish!: (value: Record<string, unknown>) => void;
    f.readRight.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    const view = await open(f.props);
    await waitFor(() => expect(f.readRight).toHaveBeenCalledTimes(1));
    fireEvent.change(view.ui.getByRole('combobox', { name: '选择对比版本' }), { target: { value: '' } });
    await act(async () => { finish(f.rows[1]); });
    expect(view.container.querySelector('[data-slot="RIGHT"]')).toBeNull(); expect(f.blob).not.toHaveBeenCalled();
  });
});
