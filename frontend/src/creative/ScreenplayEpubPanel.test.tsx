// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { ScreenplayExportPanel } from './ScreenplayExportPanel';
import type { CreativeClient, ScreenplayDownload } from './client';
import { newDocument, newScene, type CreativeDocument } from './types';
const document = { ...newDocument('SCREENPLAY'), id: 'saved', version: 3, scenes: [newScene(1)] } as CreativeDocument;
const receipt = (): ScreenplayDownload => ({ blob: new Blob(['synthetic receipt bytes']), filename: 'creative-screenplay-v3.epub', documentVersion: 3, documentDigest: 'a'.repeat(64), sha256: 'b'.repeat(64) });
let download: ReturnType<typeof vi.fn>, click: ReturnType<typeof vi.spyOn>, make: ReturnType<typeof vi.fn>, revoke: ReturnType<typeof vi.fn>;
beforeEach(() => { download = vi.fn(async () => receipt()); click = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {}); make = vi.fn(() => 'blob:synthetic'); revoke = vi.fn(); vi.stubGlobal('URL', class extends URL { static createObjectURL = make; static revokeObjectURL = revoke; }); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
const props = () => ({ client: { screenplayExport: download } as unknown as CreativeClient, document, available: true, onDenied: vi.fn() });
it('offers EPUB in the original saved screenplay selector and explains reflowed layout', async () => {
  render(<ScreenplayExportPanel {...props()} />);
  fireEvent.change(screen.getByLabelText('剧本导出格式'), { target: { value: 'epub' } });
  expect(screen.getByText(/EPUB 是可导航的重排阅读版/)).toBeTruthy();
  fireEvent.click(screen.getByRole('button', { name: '导出剧本文本' }));
  await screen.findByText('已导出已保存的 v3，文件摘要校验通过。');
  expect(download).toHaveBeenCalledWith(document, 'epub', expect.any(AbortSignal)); expect(click).toHaveBeenCalledOnce(); expect(revoke).toHaveBeenCalledWith('blob:synthetic');
});
it('uses the existing document-key remount boundary to discard a late EPUB', async () => {
  let resolve!: (result: ScreenplayDownload) => void; download.mockImplementation(() => new Promise(done => { resolve = done; }));
  const p = props(), view = render(<ScreenplayExportPanel key="saved:3" {...p} />);
  fireEvent.change(screen.getByLabelText('剧本导出格式'), { target: { value: 'epub' } });
  const button = screen.getByRole('button', { name: '导出剧本文本' }); fireEvent.click(button); fireEvent.click(button);
  expect(download).toHaveBeenCalledOnce();
  view.rerender(<ScreenplayExportPanel key="other:1" {...p} document={{ ...document, id: 'other', version: 1 }} />);
  await act(async () => resolve(receipt()));
  expect(download.mock.calls[0][2].aborted).toBe(true); expect(click).not.toHaveBeenCalled(); expect(make).not.toHaveBeenCalled();
});
it('keeps unsupported EPUB absent from generic Script and dirty screenplay controls disabled', () => {
  const p = props(), view = render(<ScreenplayExportPanel {...p} document={{ ...document, mode: 'SCRIPT', script: { purpose: 'PODCAST', body: 'Saved script' } }} />);
  expect(screen.queryByRole('option', { name: 'EPUB 电子书' })).toBeNull();
  view.rerender(<ScreenplayExportPanel key="screenplay" {...p} available={false} />);
  expect(screen.getByRole('button', { name: '导出剧本文本' }).hasAttribute('disabled')).toBe(true);
  expect(download).not.toHaveBeenCalled();
});
