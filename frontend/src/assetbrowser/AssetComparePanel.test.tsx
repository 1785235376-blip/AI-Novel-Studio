// @vitest-environment jsdom
import { useState } from 'react';
import { Blob as NodeBlob } from 'node:buffer';
import { act, cleanup, fireEvent, render, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { AssetComparePanel, type AssetMediaSlot } from './AssetComparePanel';
import type { AssetComparisonDownload } from './assetComparisonPreview';
import { decodeRow } from './assetBrowserFixtures';
import type { AssetBrowserAsset } from './assetBrowserTypes';

const left = decodeRow({ id: 'asset-left' }), right = decodeRow({ id: 'asset-right', version: 2 });
const payload = new NodeBlob(['fixture'], { type: 'image/png' }) as Blob;
const createUrl = vi.fn(() => `blob:comparison-${Math.random()}`), revokeUrl = vi.fn();
function props(download: AssetComparisonDownload) {
  return { current: left, other: right, candidates: [{ id: right.id, version: right.version, digest: right.digest, label: right.filename }],
    otherId: right.id, download, onPick: vi.fn(), onZoom: vi.fn(), onStartPlayback: vi.fn(), onStopPlayback: vi.fn(),
    activeSlot: null as AssetMediaSlot | null, zoom: 1 };
}
function side(container: HTMLElement, slot: 'LEFT' | 'RIGHT') { return within(container.querySelector(`[data-slot="${slot}"]`) as HTMLElement); }
beforeEach(() => {
  createUrl.mockClear(); revokeUrl.mockClear();
  vi.stubGlobal('URL', Object.assign(URL, { createObjectURL: createUrl, revokeObjectURL: revokeUrl }));
  vi.spyOn(HTMLMediaElement.prototype, 'pause').mockImplementation(() => {});
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

describe('two original-asset comparison media slots', () => {
  it('reads each side explicitly, synchronizes zoom and revokes both URLs', async () => {
    const download = vi.fn<AssetComparisonDownload>(async () => payload), base = props(download);
    const view = render(<AssetComparePanel {...base}/>);
    expect(download).not.toHaveBeenCalled();
    fireEvent.click(side(view.container, 'LEFT').getByRole('button', { name: '读取图片预览' }));
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' }));
    await waitFor(() => expect(view.container.querySelectorAll('img')).toHaveLength(2));
    expect(download.mock.calls.map(call => call[0].id)).toEqual(['asset-left', 'asset-right']);
    view.rerender(<AssetComparePanel {...base} zoom={2}/>);
    expect([...view.container.querySelectorAll('img')].map(node => node.style.transform)).toEqual(['scale(2)', 'scale(2)']);
    expect(download).toHaveBeenCalledTimes(2);
    view.unmount(); expect(revokeUrl).toHaveBeenCalledTimes(2);
  });
  it.each(['version', 'reader', 'unmount'] as const)('drops late bytes after %s change and suppresses duplicate clicks', async change => {
    let finish!: (blob: Blob) => void;
    const download = vi.fn<AssetComparisonDownload>(() => new Promise(resolve => { finish = resolve; }));
    const base = props(download), view = render(<AssetComparePanel {...base}/>);
    const button = side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' });
    fireEvent.click(button); fireEvent.click(button); expect(download).toHaveBeenCalledTimes(1);
    if (change === 'unmount') view.unmount();
    else view.rerender(<AssetComparePanel {...base} {...(change === 'version'
      ? { other: { ...right, version: 3, digest: 'd'.repeat(64) } }
      : { download: vi.fn(async () => payload) })}/>);
    await act(async () => { finish(payload); });
    expect(createUrl).not.toHaveBeenCalled();
  });
  it('keeps a newer successful read when an invalidated older read settles last', async () => {
    const finishes: ((blob: Blob) => void)[] = [];
    const download = vi.fn<AssetComparisonDownload>(() => new Promise(resolve => { finishes.push(resolve); }));
    const base = props(download), view = render(<AssetComparePanel {...base}/>);
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' }));
    view.rerender(<AssetComparePanel {...base} other={{ ...right, version: 4 }}/>);
    view.rerender(<AssetComparePanel {...base}/>);
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' }));
    await act(async () => { finishes[1](payload); });
    expect(createUrl).toHaveBeenCalledTimes(1);
    const shown = view.container.querySelector('img')?.getAttribute('src');
    await act(async () => { finishes[0](payload); });
    expect(createUrl).toHaveBeenCalledTimes(1); expect(view.container.querySelector('img')?.getAttribute('src')).toBe(shown);
  });
  it('clears previous bytes on failed re-read and permits explicit retry', async () => {
    const download = vi.fn<AssetComparisonDownload>().mockResolvedValueOnce(payload)
      .mockRejectedValueOnce(new Error('server secret')).mockResolvedValueOnce(payload);
    const view = render(<AssetComparePanel {...props(download)}/>);
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' }));
    await waitFor(() => expect(view.container.querySelectorAll('img')).toHaveLength(1));
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '重新读取图片' }));
    await waitFor(() => expect(side(view.container, 'RIGHT').getByRole('alert')).toBeTruthy());
    expect(view.container.querySelector('img')).toBeNull(); expect(view.container.textContent).not.toContain('server secret');
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: '读取图片预览' }));
    await waitFor(() => expect(view.container.querySelectorAll('img')).toHaveLength(1));
  });
  it.each(['image', 'audio', 'video'] as const)('reports %s decoder failure, revokes bytes and permits retry', async kind => {
    const download = vi.fn<AssetComparisonDownload>(async () => payload);
    const other = { ...right, kind, media_kind: kind };
    const view = render(<AssetComparePanel {...props(download)} other={other}/>);
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: /读取.*预览/ }));
    const selector = kind === 'image' ? 'img' : kind;
    await waitFor(() => expect(view.container.querySelector(selector)).toBeTruthy());
    fireEvent.error(view.container.querySelector(selector)!);
    expect(view.container.querySelector(selector)).toBeNull();
    expect(side(view.container, 'RIGHT').getByRole('alert')).toBeTruthy();
    expect(revokeUrl).toHaveBeenCalledTimes(1);
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: /读取.*预览/ }));
    await waitFor(() => expect(view.container.querySelector(selector)).toBeTruthy());
  });
  it.each(['audio', 'video'] as const)('never autoplays %s; playing one side stops the other and unmount stops both', async kind => {
    const download = vi.fn<AssetComparisonDownload>(async () => payload);
    const mediaAsset = (asset: AssetBrowserAsset) => ({ ...asset, kind, media_kind: kind, media_type: kind === 'audio' ? 'audio/wav' : 'video/mp4' });
    function Harness() {
      const [activeSlot, setActiveSlot] = useState<AssetMediaSlot | null>(null);
      return <AssetComparePanel {...props(download)} current={mediaAsset(left)} other={mediaAsset(right)} activeSlot={activeSlot}
        onStartPlayback={setActiveSlot} onStopPlayback={slot => setActiveSlot(active => active === slot ? null : active)}/>;
    }
    const view = render(<Harness/>);
    expect(view.container.querySelector(kind)).toBeNull();
    fireEvent.click(side(view.container, 'LEFT').getByRole('button', { name: /读取.*预览/ }));
    fireEvent.click(side(view.container, 'RIGHT').getByRole('button', { name: /读取.*预览/ }));
    await waitFor(() => expect(view.container.querySelectorAll(kind)).toHaveLength(2));
    const [a, b] = [...view.container.querySelectorAll<HTMLMediaElement>(kind)];
    expect(a.autoplay || b.autoplay).toBe(false); expect(a.preload).toBe('none');
    fireEvent.play(a); expect(view.container.querySelector('[data-slot="LEFT"]')?.getAttribute('data-active')).toBe('true');
    const pause = vi.spyOn(a, 'pause'); pause.mockClear(); a.currentTime = 5;
    fireEvent.play(b); expect(pause).toHaveBeenCalled(); expect(a.currentTime).toBe(0);
    const stopB = vi.spyOn(b, 'pause'); stopB.mockClear(); view.unmount(); expect(stopB).toHaveBeenCalled();
  });
});
