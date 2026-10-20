// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { ScreenplayExportPanel } from './ScreenplayExportPanel';
import type { CreativeClient, ScreenplayDownload } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';
const doc = { ...newDocument('SCREENPLAY'), id: 'saved-doc', version: 3, scenes: [newScene(1)] } as CreativeDocument;
const receipt = (): ScreenplayDownload => ({ blob: new Blob(['original bytes']), filename: 'creative-screenplay-v3.fountain', documentVersion: 3, documentDigest: '1'.repeat(64), sha256: '2'.repeat(64) });
let download: ReturnType<typeof vi.fn>, click: ReturnType<typeof vi.spyOn>, makeURL: ReturnType<typeof vi.fn>, revokeURL: ReturnType<typeof vi.fn>;
function setup(available = true) { const onDenied = vi.fn(); const client = { screenplayExport: download } as unknown as CreativeClient; const props = { client, document: doc, available, onDenied }; return { ...render(<ScreenplayExportPanel {...props} />), props, onDenied }; }
beforeEach(() => { download = vi.fn(async () => receipt()); click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {}); makeURL = vi.fn(() => 'blob:synthetic'); revokeURL = vi.fn(); vi.stubGlobal('URL', class extends URL { static createObjectURL = makeURL; static revokeObjectURL = revokeURL; }); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
describe('saved screenplay download boundaries', () => {
  it('selects a real format, pins the saved version and releases its object URL', async () => {
    setup(); fireEvent.change(screen.getByLabelText('剧本导出格式'), { target: { value: 'docx' } }); fireEvent.click(screen.getByRole('button', { name: '导出剧本文本' }));
    await screen.findByText('已导出已保存的 v3，文件摘要校验通过。');
    expect(download).toHaveBeenCalledWith(doc, 'docx', expect.any(AbortSignal)); expect(click).toHaveBeenCalledOnce(); expect(revokeURL).toHaveBeenCalledWith('blob:synthetic');
  });
  it('blocks dirty or uncertain saved state without invoking download', () => { setup(false); expect(screen.getByRole('button', { name: '导出剧本文本' }).hasAttribute('disabled')).toBe(true); expect(download).not.toHaveBeenCalled(); });
  it('deduplicates repeated clicks and suppresses a late download after draft editing', async () => {
    let resolve!: (r: ScreenplayDownload) => void; download.mockImplementation(() => new Promise(done => { resolve = done; }));
    const view = setup(); const button = screen.getByRole('button', { name: '导出剧本文本' }); fireEvent.click(button); fireEvent.click(button); expect(download).toHaveBeenCalledOnce();
    view.rerender(<ScreenplayExportPanel {...view.props} available={false} />); await act(async () => resolve(receipt()));
    expect(download.mock.calls[0][2].aborted).toBe(true); expect(click).not.toHaveBeenCalled(); expect(makeURL).not.toHaveBeenCalled();
  });
  it('aborts and drops the late result after its originating document unmounts', async () => {
    let resolve!: (r: ScreenplayDownload) => void; download.mockImplementation(() => new Promise(done => { resolve = done; }));
    const view = setup(); fireEvent.click(screen.getByRole('button', { name: '导出剧本文本' })); view.unmount(); await act(async () => resolve(receipt()));
    expect(download.mock.calls[0][2].aborted).toBe(true); expect(click).not.toHaveBeenCalled();
  });
  it.each([401, 403])('purges the parent surface on authority denial %i', async status => {
    download.mockRejectedValue(new ApiError({ status, code: 'DENIED', message: '权限已撤销' })); const view = setup(); fireEvent.click(screen.getByRole('button', { name: '导出剧本文本' }));
    await waitFor(() => expect(view.onDenied).toHaveBeenCalledOnce()); expect(click).not.toHaveBeenCalled();
  });
  it('keeps a recoverable format error without showing private response details', async () => {
    download.mockRejectedValue(new Error('private host path')); setup(); fireEvent.click(screen.getByRole('button', { name: '导出剧本文本' }));
    await screen.findByText(/导出未完成/); expect(screen.queryByText('private host path')).toBeNull(); expect(click).not.toHaveBeenCalled();
  });
});
