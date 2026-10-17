// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ClipInspectorPanel } from './ClipInspectorPanel';
import { editCommand } from './timelineOps';
import { checkedTimeline } from '../creative/studioTimelineTypes';
const retained = vi.hoisted(() => ({ generate: [] as Array<() => void> }));
vi.mock('../ui/primitives', async importOriginal => {
  const actual = await importOriginal<typeof import('../ui/primitives')>();
  return { ...actual, Button: (p: React.ComponentProps<typeof actual.Button>) => {
    if (p.children === '生成编辑指令') retained.generate.push(p.onClick as () => void);
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
const generate = () => fireEvent.click(screen.getByRole('button', { name: '生成编辑指令' }));
const props = () => ({ timeline, selectedClipIds: ['a'], playheadMs: 0, marks: { inMs: 1000, outMs: 2000 }, editable: true, onEdit: vi.fn() });
afterEach(() => { cleanup(); retained.generate.length = 0; });
describe('inspector slip bounds and current delete consent', () => {
  it('does not confuse ruler marks with source bounds, retaining optional verified mapper bounds', () => {
    const p = props(); render(<ClipInspectorPanel {...p} />); set('请求的动作', 'slip'); set('滑移增量（毫秒）', '500'); generate();
    expect(p.onEdit).toHaveBeenCalledWith({ kind: 'clip.slip', payload: { op: 'clip.slip', clip_id: 'a', offset_ms: 500 } });
    expect(editCommand('slip', { timeline, clipId: 'a', offsetMs: 500, sourceRange: { inMs: 0, outMs: 4000 } }).ok).toBe(false);
    expect(screen.getByText(/尚未生成编辑指令的输入不会成为时间线草稿/)).toBeTruthy();
  });
  it('preserves authored slip across unrelated rerenders and resets on actual target change', () => {
    const p = props(), view = render(<ClipInspectorPanel {...p} />); set('请求的动作', 'slip'); set('滑移增量（毫秒）', '-600');
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); view.rerender(<ClipInspectorPanel {...p} timeline={structuredClone(timeline)} playheadMs={10} />);
    expect((screen.getByLabelText('滑移增量（毫秒）') as HTMLInputElement).value).toBe('-600');
    expect((screen.getByLabelText('波纹闭合间隙') as HTMLInputElement).checked).toBe(true);
    view.rerender(<ClipInspectorPanel {...p} selectedClipIds={['b']} />);
    expect((screen.getByLabelText('滑移增量（毫秒）') as HTMLInputElement).value).toBe('');
    expect((screen.getByLabelText('波纹闭合间隙') as HTMLInputElement).checked).toBe(false); generate(); expect(p.onEdit).not.toHaveBeenCalled();
  });
  it('invalidates retained consent callbacks immediately and through checkbox ABA', () => {
    const p = props(); render(<ClipInspectorPanel {...p} />); set('请求的动作', 'ripple');
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); const old = retained.generate.at(-1)!;
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); act(() => old()); expect(p.onEdit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); act(() => old()); expect(p.onEdit).not.toHaveBeenCalled();
    generate(); expect(p.onEdit).toHaveBeenCalledTimes(1);
  });
  it('requires explicit current consent for ripple delete', () => {
    const p = props(); render(<ClipInspectorPanel {...p} />); set('请求的动作', 'ripple'); generate(); expect(p.onEdit).not.toHaveBeenCalled();
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); generate();
    expect(p.onEdit).toHaveBeenCalledWith({ kind: 'clip.remove', payload: { op: 'clip.remove', clip_id: 'a', ripple: true } });
    fireEvent.click(screen.getByLabelText('波纹闭合间隙')); generate(); expect(p.onEdit).toHaveBeenCalledTimes(1);
  });
});
