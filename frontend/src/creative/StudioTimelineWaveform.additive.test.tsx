// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, renderHook, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import type { StudioProductionClient } from './studioProductionClient';
import { StudioTimelineEditor } from './StudioTimelineEditor';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { useStudioTimelineWaveform, type TimelineWaveformOptions } from './useStudioTimelineWaveform';
import type { StudioTimelineRow } from './studioTimelineTypes';
import type { TimelineWaveform } from './studioTimelineWaveformTypes';
import { waveformAssets, waveformDto, waveformRow } from './studioTimelineWaveform.testFixtures';

const deferred = <T,>() => { let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject }; };
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
function setup() {
  let revision = 1, generation = 1, ready = true, current = true;
  const client = { timelineWaveformPreview: vi.fn(async (_source: StudioTimelineRow, _clipId: string, _signal?: AbortSignal) => waveformDto()), timelineSave: vi.fn(), timelineRender: vi.fn(), timelineEdit: vi.fn() };
  const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: waveformAssets(), projectId: 'project-waveform',
    canMutate: true, busy: false, isCurrent: () => current, read: async work => work(), mutate: vi.fn(async work => work()),
    onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onJob: vi.fn() };
  let options: TimelineWaveformOptions = { props, source: waveformRow(), selectedClipIds: ['audio-clip'],
    getRevision: () => String(revision), getSelectionGeneration: () => generation, isReady: () => ready };
  const hook = renderHook((next: TimelineWaveformOptions) => useStudioTimelineWaveform(next), { initialProps: options });
  const rerender = (change: Partial<TimelineWaveformOptions> = {}) => { options = { ...options, ...change }; hook.rerender(options); };
  return { hook, props, client, rerender, options: () => options, edit: () => { revision++; }, select: () => { generation++; },
    readiness: (value: boolean) => { ready = value; }, authority: (value: boolean) => { current = value; } };
}
describe('ephemeral selected source envelope controller', () => {
  it('does no implicit request, keeps one in flight, and never invokes mutation/history callbacks', async () => {
    const s = setup(), pending = deferred<TimelineWaveform>(); s.client.timelineWaveformPreview.mockReturnValueOnce(pending.promise);
    s.rerender(); expect(s.client.timelineWaveformPreview).not.toHaveBeenCalled();
    const retained = s.hook.result.current.request; let work!: Promise<void>;
    act(() => { work = retained(); void retained(); }); expect(s.client.timelineWaveformPreview).toHaveBeenCalledTimes(1);
    await act(async () => { pending.resolve(waveformDto()); await work; }); expect(s.hook.result.current.preview).toEqual(waveformDto());
    expect(s.props.mutate).not.toHaveBeenCalled(); expect(s.props.onDirtyChange).not.toHaveBeenCalled();
    expect(s.client.timelineSave).not.toHaveBeenCalled(); expect(s.client.timelineRender).not.toHaveBeenCalled(); expect(s.client.timelineEdit).not.toHaveBeenCalled();
    expect(s.options().source).toEqual(waveformRow());
  });
  it.each(['dirty', 'busy', 'permission', 'authority', 'client', 'project', 'source', 'selection', 'unmount'] as const)('aborts and drops late response on %s', async fault => {
    const s = setup(), pending = deferred<TimelineWaveform>(); s.client.timelineWaveformPreview.mockReturnValueOnce(pending.promise);
    let work!: Promise<void>; act(() => { work = s.hook.result.current.request(); });
    const signal = s.client.timelineWaveformPreview.mock.calls[0][2] as AbortSignal;
    if (fault === 'unmount') s.hook.unmount();
    else if (fault === 'dirty') { s.edit(); s.readiness(false); s.rerender(); }
    else if (fault === 'authority') { s.authority(false); s.rerender(); }
    else if (fault === 'selection') { s.select(); s.rerender({ selectedClipIds: ['still'] }); }
    else if (fault === 'source') s.rerender({ props: { ...s.props, assets: waveformAssets().map(asset => asset.kind === 'audio' ? { ...asset, version: 3 } : asset) } });
    else s.rerender({ props: { ...s.props, ...(fault === 'busy' ? { busy: true } : fault === 'permission' ? { canMutate: false }
      : fault === 'project' ? { projectId: 'other' } : { client: { ...s.client } as unknown as StudioProductionClient }) } });
    expect(signal.aborted).toBe(true);
    await act(async () => { pending.resolve(waveformDto()); await work; });
    if (fault !== 'unmount') expect(s.hook.result.current.preview).toBeUndefined();
    expect(s.client.timelineWaveformPreview).toHaveBeenCalledTimes(1);
  });
  it.each(['dirty-undo', 'selection'] as const)('fences retained action and response on %s ABA even before React rerenders', async fault => {
    const s = setup(), pending = deferred<TimelineWaveform>(); s.client.timelineWaveformPreview.mockReturnValueOnce(pending.promise);
    const retained = s.hook.result.current.request; let work!: Promise<void>; act(() => { work = retained(); });
    if (fault === 'dirty-undo') { s.edit(); s.edit(); } else { s.select(); s.select(); }
    await act(async () => { pending.resolve(waveformDto()); await work; await retained(); });
    expect(s.hook.result.current.preview).toBeUndefined(); expect(s.client.timelineWaveformPreview).toHaveBeenCalledTimes(1);
    s.rerender(); await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.preview).toEqual(waveformDto());
  });
  it('clears already visible peaks on input generation and never revives them after undo', async () => {
    const s = setup(); await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.preview).toBeTruthy();
    s.edit(); s.readiness(false); s.rerender(); expect(s.hook.result.current.preview).toBeUndefined();
    s.edit(); s.readiness(true); s.rerender(); expect(s.hook.result.current.preview).toBeUndefined(); expect(s.client.timelineWaveformPreview).toHaveBeenCalledTimes(1);
  });
  it.each([401, 403])('propagates current %s through the original guard and revokes authority', async status => {
    const s = setup(), reason = new ApiError({ status, code: 'DENIED', message: 'Denied' }), observed = vi.fn();
    s.client.timelineWaveformPreview.mockRejectedValueOnce(reason);
    s.rerender({ props: { ...s.props, read: async work => { try { return await work(); } catch (error) {
      observed(error); if (error instanceof ApiError && [401, 403].includes(error.status)) { s.props.onUnavailable(); s.authority(false); } throw error;
    } } } });
    await act(async () => s.hook.result.current.request()); expect(observed).toHaveBeenCalledWith(reason);
    expect(s.props.onUnavailable).toHaveBeenCalledTimes(1); expect(s.hook.result.current.preview).toBeUndefined();
  });
  it.each(['selection', 'dirty-undo'] as const)('converts stale 403 inside the read callback after %s ABA without revoking the newer workspace', async fault => {
    const s = setup(), pending = deferred<TimelineWaveform>(), observed = vi.fn(); s.client.timelineWaveformPreview.mockReturnValueOnce(pending.promise);
    s.rerender({ props: { ...s.props, read: async work => { try { return await work(); } catch (error) {
      observed(error); if (error instanceof ApiError && [401, 403].includes(error.status)) s.props.onUnavailable(); throw error;
    } } } });
    let work!: Promise<void>; act(() => { work = s.hook.result.current.request(); });
    if (fault === 'selection') { s.select(); s.select(); } else { s.edit(); s.edit(); }
    await act(async () => { pending.reject(new ApiError({ status: 403, code: 'DENIED', message: 'Denied' })); await work; });
    expect(observed).toHaveBeenCalledTimes(1); expect(observed.mock.calls[0][0].name).toBe('AbortError');
    expect(s.props.onUnavailable).not.toHaveBeenCalled(); expect(s.hook.result.current.preview).toBeUndefined();
    s.rerender(); await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.preview).toBeTruthy();
  });
  it.each(['STUDIO_WAVEFORM_PCM16_REQUIRED', 'STUDIO_WAVEFORM_LIMIT', 'STUDIO_WAVEFORM_PLATFORM_UNSUPPORTED', 'STUDIO_WAVEFORM_INVALID', 'STUDIO_WAVEFORM_CLIP_RANGE_INVALID'])('shows honest explicit %s without fallback calls', async code => {
    const s = setup(); s.client.timelineWaveformPreview.mockRejectedValueOnce(new ApiError({ status: 422, code: 'EXPERIMENTAL_INVALID', message: code }));
    await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.error).not.toBe(''); expect(s.hook.result.current.error).not.toContain(code);
    expect(s.hook.result.current.preview).toBeUndefined(); expect(s.client.timelineWaveformPreview).toHaveBeenCalledTimes(1); expect(s.props.mutate).not.toHaveBeenCalled();
  });
  it('sanitizes unknown errors and discards malformed results instead of drawing them', async () => {
    const s = setup(); s.client.timelineWaveformPreview.mockRejectedValueOnce(new Error('private /home/path/token'));
    await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.error).not.toContain('/home');
    s.client.timelineWaveformPreview.mockResolvedValueOnce({ ...waveformDto(), peaks: Array(513).fill(1) });
    await act(async () => s.hook.result.current.request()); expect(s.hook.result.current.preview).toBeUndefined(); expect(s.hook.result.current.error).not.toBe('');
  });
  it.each([[], ['still'], ['missing'], ['audio-clip', 'still']].map(ids => ({ ids })))('never reads an unsupported selection $ids', async ({ ids }) => {
    const s = setup(); s.rerender({ selectedClipIds: ids }); await act(async () => s.hook.result.current.request()); expect(s.client.timelineWaveformPreview).not.toHaveBeenCalled();
  });
  it('does not expose a method absent from legacy clients or unsaved/UNKNOWN readiness', async () => {
    const s = setup(); s.rerender({ props: { ...s.props, client: {} as StudioProductionClient } });
    expect(s.hook.result.current.available).toBe(false); await act(async () => s.hook.result.current.request());
    s.rerender({ props: s.props, source: undefined }); await act(async () => s.hook.result.current.request());
    s.readiness(false); s.rerender({ source: waveformRow() }); await act(async () => s.hook.result.current.request()); expect(s.client.timelineWaveformPreview).not.toHaveBeenCalled();
  });
});

describe('original mounted timeline integration', () => {
  it('requires saved clean single selection and preserves local history and saved payload', async () => {
    const source = waveformRow(), before = JSON.stringify(source), client = { timelineList: vi.fn(async () => ({ items: [source] })), timelineGet: vi.fn(async () => source),
      timelineWaveformPreview: vi.fn(async (_source: StudioTimelineRow, _clipId: string, _signal?: AbortSignal) => waveformDto()), timelineSave: vi.fn(), timelineRender: vi.fn(), timelineEdit: vi.fn(), list: vi.fn() };
    const props: StudioTimelineEditorProps = { client: client as unknown as StudioProductionClient, assets: waveformAssets(), projectId: 'project-waveform', canMutate: true, busy: false,
      isCurrent: () => true, read: async work => work(), mutate: async work => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn(), onJob: vi.fn() };
    render(<StudioTimelineEditor {...props} />);
    await screen.findByRole('option', { name: 'Waveform fixture · v1' }); expect(client.timelineWaveformPreview).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('读取已保存时间线'), { target: { value: source.id } });
    await screen.findByRole('heading', { name: 'Waveform fixture · v1' });
    fireEvent.click(screen.getByLabelText('已核对服务端内容与本地输入，确认以下选择')); fireEvent.click(screen.getByRole('button', { name: '采用服务端时间线' }));
    expect((screen.getByRole('button', { name: '读取所选源波形' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button', { name: 'audio-clip' })); expect(client.timelineWaveformPreview).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', { name: '读取所选源波形' }));
    await screen.findByRole('img', { name: '已测量的所选片段源采样包络' });
    expect(client.timelineWaveformPreview).toHaveBeenCalledTimes(1); expect(JSON.stringify(source)).toBe(before);
    expect((screen.getByRole('button', { name: '撤销本地编辑' }) as HTMLButtonElement).disabled).toBe(true);
    expect(client.timelineSave).not.toHaveBeenCalled(); expect(client.timelineRender).not.toHaveBeenCalled(); expect(client.timelineEdit).not.toHaveBeenCalled();
    fireEvent.change(screen.getByLabelText('名称'), { target: { value: 'Changed title' } });
    await waitFor(() => expect(screen.queryByRole('img', { name: '已测量的所选片段源采样包络' })).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: '撤销本地编辑' }));
    expect((screen.getByLabelText('名称') as HTMLInputElement).value).toBe('Waveform fixture');
    expect(screen.queryByRole('img', { name: '已测量的所选片段源采样包络' })).toBeNull(); expect(client.timelineWaveformPreview).toHaveBeenCalledTimes(1);
  });
});
