// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ClipInspectorPanel } from './ClipInspectorPanel';
import { checkedTimeline } from '../creative/studioTimelineTypes';
const retained = vi.hoisted(() => ({ generate: [] as Array<() => void> }));
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (p: React.ComponentProps<typeof actual.Button>) => {
    if (p.children === '整体移动所选片段') retained.generate.push(p.onClick as () => void);
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
describe('selection move inspector', () => {
  it('emits one original move batch for every selected clip', () => {
    const p = { ...props(), selectedClipIds: ['a', 'b'] }; render(<ClipInspectorPanel {...p} />);
    set('整体移动增量（毫秒，可为负）', '-500'); fireEvent.click(screen.getByRole('button', { name: '整体移动所选片段' }));
    expect(p.onEdit).toHaveBeenCalledWith({ kind: 'clip.move', payload: [
      { op: 'clip.move', clip_id: 'a', track_id: 'sound', start_ms: 500 },
      { op: 'clip.move', clip_id: 'b', track_id: 'sound', start_ms: 3500 },
    ] });
  });
  it('preserves input on unrelated rerender and resets on selection changes', () => {
    const p = props(), view = render(<ClipInspectorPanel {...p} />); set('整体移动增量（毫秒，可为负）', '500');
    view.rerender(<ClipInspectorPanel {...p} timeline={structuredClone(timeline)} playheadMs={10} />);
    expect((screen.getByLabelText('整体移动增量（毫秒，可为负）') as HTMLInputElement).value).toBe('500');
    view.rerender(<ClipInspectorPanel {...p} selectedClipIds={['b']} />);
    expect((screen.getByLabelText('整体移动增量（毫秒，可为负）') as HTMLInputElement).value).toBe('');
  });
  it.each(['input', 'selection', 'context', 'permission', 'unmount'] as const)('refuses retained callback after %s ABA/lifecycle', fault => {
    const p = props(), view = render(<ClipInspectorPanel {...p} />); set('整体移动增量（毫秒，可为负）', '500'); const old = retained.generate.at(-1)!;
    if (fault === 'input') { set('整体移动增量（毫秒，可为负）', '100'); set('整体移动增量（毫秒，可为负）', '500'); }
    if (fault === 'selection') { view.rerender(<ClipInspectorPanel {...p} selectedClipIds={['b']} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'context') { view.rerender(<ClipInspectorPanel {...p} timeline={{ ...timeline, duration_ms: 9000 }} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'permission') { view.rerender(<ClipInspectorPanel {...p} editable={false} />); view.rerender(<ClipInspectorPanel {...p} />); }
    if (fault === 'unmount') view.unmount();
    act(() => old()); expect(p.onEdit).not.toHaveBeenCalled();
  });
  it('rejects blank input and duplicate selection', () => {
    const p = { ...props(), selectedClipIds: ['a', 'a'] }; render(<ClipInspectorPanel {...p} />);
    fireEvent.click(screen.getByRole('button', { name: '整体移动所选片段' }));
    set('整体移动增量（毫秒，可为负）', '500'); fireEvent.click(screen.getByRole('button', { name: '整体移动所选片段' })); expect(p.onEdit).not.toHaveBeenCalled();
  });
});
