// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ClipInspectorPanel } from './ClipInspectorPanel';
import { checkedTimeline } from '../creative/studioTimelineTypes';
const retained = vi.hoisted(() => ({ generate: [] as Array<() => void> }));
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (p: React.ComponentProps<typeof actual.Button>) => {
    if (p.children === '整体复制所选片段') retained.generate.push(p.onClick as () => void);
    return <actual.Button {...p} />;
  } };
});
const timeline = checkedTimeline({ schema_version: 2, duration_ms: 8000, width: 64, height: 64, fps: 25, captions: [], tracks: [
  { id: 'visual', kind: 'VIDEO', order: 0, muted: false, gain_db: 0, clips: [{ id: 'still', source_snapshot: { id: 'asset-image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: 'a'.repeat(64) }, start_ms: 0, in_ms: 0, out_ms: 8000, x: 0, y: 0, width: 64, height: 64 }] },
  { id: 'sound', kind: 'AUDIO', order: 1, muted: false, gain_db: 0, clips: ['a', 'b'].map((id, i) => ({ id,
    source_snapshot: { id: 'asset-audio', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: 'a'.repeat(64) },
    start_ms: 1000 + i * 3000, in_ms: 600, out_ms: 3600, speed_num: 3, speed_den: 2 })) },
] });
const set = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const props = () => ({ timeline, selectedClipIds: ['a'], playheadMs: 0, marks: { inMs: 1000, outMs: 2000 }, editable: true, onEdit: vi.fn() });
afterEach(() => { cleanup(); retained.generate.length = 0; });

const offsetLabel = '整体复制增量（毫秒，可为负或零）';
const duplicate = () => fireEvent.click(screen.getByRole('button', { name: '整体复制所选片段' }));
describe('selection duplicate inspector', () => {
  it('allocates once per explicit action, emits exact IDs, and suppresses repeated clicks', () => {
    const p = { ...props(), selectedClipIds: ['a', 'b'], newId: vi.fn().mockReturnValueOnce('new-a').mockReturnValueOnce('new-b') };
    render(<ClipInspectorPanel {...p} />); set(offsetLabel, '0'); const old = retained.generate.at(-1)!;
    act(() => { old(); old(); }); duplicate();
    expect(p.newId).toHaveBeenCalledTimes(2); expect(p.onEdit).toHaveBeenCalledTimes(1);
    expect(p.onEdit).toHaveBeenCalledWith({ kind: 'clip.duplicate', payload: [
      { op: 'clip.duplicate', clip_id: 'a', new_clip_id: 'new-a', track_id: 'sound', start_ms: 1000 },
      { op: 'clip.duplicate', clip_id: 'b', new_clip_id: 'new-b', track_id: 'sound', start_ms: 4000 },
    ] });
    expect(screen.getByText(/不复制通向未选片段的转场/)).toBeTruthy();
  });
  it('consumes failed identity allocation without hidden retry; authored correction permits a new action', () => {
    const p = { ...props(), newId: vi.fn().mockReturnValueOnce('a').mockReturnValueOnce('new-a') };
    render(<ClipInspectorPanel {...p} />); set(offsetLabel, '0'); duplicate(); duplicate();
    expect(p.newId).toHaveBeenCalledTimes(1); expect(p.onEdit).not.toHaveBeenCalled();
    set(offsetLabel, '1'); duplicate(); expect(p.newId).toHaveBeenCalledTimes(2); expect(p.onEdit).toHaveBeenCalledTimes(1);
  });
  it('preflights invalid selection and offset before allocating identities', () => {
    const p = { ...props(), newId: vi.fn(() => 'new') }; render(<ClipInspectorPanel {...p} />);
    duplicate(); duplicate(); expect(p.newId).not.toHaveBeenCalled();
    set(offsetLabel, '-1001'); duplicate(); expect(p.newId).not.toHaveBeenCalled(); expect(p.onEdit).not.toHaveBeenCalled();
  });
  it('preserves authored offset on unrelated renders but clears it on context change', () => {
    const p = props(), view = render(<ClipInspectorPanel {...p} />); set(offsetLabel, '500');
    view.rerender(<ClipInspectorPanel {...p} timeline={structuredClone(timeline)} playheadMs={10} />);
    expect((screen.getByLabelText(offsetLabel) as HTMLInputElement).value).toBe('500');
    view.rerender(<ClipInspectorPanel {...p} selectedClipIds={['b']} />);
    expect((screen.getByLabelText(offsetLabel) as HTMLInputElement).value).toBe('');
  });
  it.each(['input', 'selection', 'context', 'permission', 'unmount'] as const)('rejects retained callbacks after %s before generating identities', fault => {
    const p = { ...props(), newId: vi.fn(() => 'new') }, view = render(<ClipInspectorPanel {...p} />);
    set(offsetLabel, '500'); const old = retained.generate.at(-1)!;
    if (fault === 'input') { set(offsetLabel, '100'); set(offsetLabel, '500'); }
    if (fault === 'selection') { view.rerender(<ClipInspectorPanel {...p} selectedClipIds={['b']} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'context') { view.rerender(<ClipInspectorPanel {...p} timeline={{ ...timeline, duration_ms: 9000 }} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'permission') { view.rerender(<ClipInspectorPanel {...p} editable={false} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'unmount') view.unmount();
    act(() => old()); expect(p.onEdit).not.toHaveBeenCalled(); expect(p.newId).not.toHaveBeenCalled();
  });
});
