import { useEffect, useId, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from '../experimental/shared';
import { BINARY_MASK_MAX_RADIUS, BINARY_MASK_MAX_SIZE, BinaryMaskDraft } from './studioBinaryMask';

export type StudioBinaryMaskCanvasProps = {
  mask: BinaryMaskDraft;
  sourceUrl: string;
  readOnly: boolean;
  isCurrent: () => boolean;
  onChange: () => void;
};
type Gesture = { pointerId: number; mask: BinaryMaskDraft; sourceUrl: string };
type Point = { x: number; y: number };
const integer = (value: string, name: string) => {
  // Four digits cover every admitted coordinate and dimension. Reject, never truncate.
  if (value.length > 4 || !/^\d+$/.test(value) || !Number.isSafeInteger(Number(value))) throw new Error(`${name}必须是最多 4 位的非负整数。`);
  return Number(value);
};

/** The source stays in a separate blob-only image. Canvas RGBA is a disposable preview. */
export function StudioBinaryMaskCanvas({ mask, sourceUrl, readOnly, isCurrent, onChange }: StudioBinaryMaskCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null), gesture = useRef<Gesture | null>(null);
  const [radius, setRadius] = useState('8'), [keep, setKeep] = useState(false);
  const [cursor, setCursor] = useState<Point>({ x: 0, y: 0 });
  const [rectangle, setRectangle] = useState({ x: '0', y: '0', width: '1', height: '1' });
  const [error, setError] = useState(''), [displayError, setDisplayError] = useState('');
  const [sourceFailed, setSourceFailed] = useState(false), [previewRevision, setPreviewRevision] = useState(0);
  const [focused, setFocused] = useState(false);
  const instructionsId = useId();
  const safeSource = sourceUrl.startsWith('blob:');
  const latest = useRef({ mask, sourceUrl, readOnly, isCurrent, onChange, sourceFailed, safeSource });
  latest.current = { mask, sourceUrl, readOnly, isCurrent, onChange, sourceFailed, safeSource };
  const refresh = () => setPreviewRevision(value => value + 1);
  const owns = (owner: Gesture) => {
    const current = latest.current;
    return current.mask === owner.mask && current.sourceUrl === owner.sourceUrl && current.isCurrent();
  };
  const editable = () => {
    const current = latest.current;
    return !current.readOnly && current.safeSource && !current.sourceFailed && current.isCurrent();
  };
  const release = (pointerId: number) => {
    try { canvasRef.current?.releasePointerCapture?.(pointerId); } catch { /* Already released by the browser. */ }
  };
  const cancelGesture = (notify = true, repaint = true) => {
    const owner = gesture.current; if (!owner) return;
    gesture.current = null;
    // The owning controller may have already disposed the old draft on a source switch.
    try { owner.mask.cancelStroke(); } catch { /* A released draft cannot be reused. */ }
    release(owner.pointerId);
    if (repaint) refresh();
    if (notify && owns(owner)) latest.current.onChange();
  };

  useEffect(() => {
    setCursor({ x: 0, y: 0 }); setRectangle({ x: '0', y: '0', width: '1', height: '1' });
    setSourceFailed(false); setError('');
    return () => cancelGesture(false, false);
  }, [mask, sourceUrl]);
  useEffect(() => { if (!editable()) cancelGesture(); });
  useEffect(() => {
    const blur = () => cancelGesture();
    window.addEventListener('blur', blur);
    return () => { window.removeEventListener('blur', blur); };
  }, []);

  useEffect(() => {
    const canvas = canvasRef.current; if (!canvas) return;
    try {
      const context = canvas.getContext('2d');
      if (!context) { setDisplayError('当前环境无法显示蒙版画布，请使用精确矩形控件编辑。'); return; }
      const bits = mask.snapshot(), image = context.createImageData(mask.width, mask.height);
      for (let pixel = 0; pixel < mask.width * mask.height; pixel++) {
        const value = bits[pixel >>> 3] & (1 << (7 - (pixel & 7))) ? 255 : 0, offset = pixel * 4;
        image.data[offset] = value; image.data[offset + 1] = value; image.data[offset + 2] = value;
        image.data[offset + 3] = 144;
      }
      context.putImageData(image, 0, 0); setDisplayError('');
    } catch { setDisplayError('蒙版预览不可用，请重新读取当前来源。'); }
  }, [mask, mask.revision, previewRevision]);

  const point = (event: PointerEvent<HTMLCanvasElement>): Point | null => {
    const bounds = event.currentTarget.getBoundingClientRect();
    if (!Number.isFinite(event.clientX) || !Number.isFinite(event.clientY)
      || !Number.isFinite(bounds.width) || !Number.isFinite(bounds.height) || bounds.width <= 0 || bounds.height <= 0) return null;
    return {
      x: Math.max(0, Math.min(mask.width - 1, Math.floor((event.clientX - bounds.left) * mask.width / bounds.width))),
      y: Math.max(0, Math.min(mask.height - 1, Math.floor((event.clientY - bounds.top) * mask.height / bounds.height))),
    };
  };
  const fail = (value: unknown) => setError(value instanceof Error ? value.message : '蒙版操作失败，请重新读取来源。');
  const run = (action: () => boolean) => {
    if (!editable() || gesture.current || mask.activeStroke) return;
    try { const changed = action(); setError(''); refresh(); if (changed && editable()) latest.current.onChange(); }
    catch (value) { fail(value); }
  };
  const begin = (event: PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 || gesture.current || mask.activeStroke || !editable()) return;
    const location = point(event); if (!location) return;
    event.preventDefault(); event.currentTarget.focus();
    try {
      const brushRadius = integer(radius, '笔刷半径');
      event.currentTarget.setPointerCapture?.(event.pointerId);
      mask.beginStroke(location.x, location.y, brushRadius, keep);
      gesture.current = { pointerId: event.pointerId, mask, sourceUrl };
      setCursor(location); setError(''); refresh();
      if (editable()) latest.current.onChange(); else cancelGesture(false);
    } catch (value) { release(event.pointerId); fail(value); }
  };
  const move = (event: PointerEvent<HTMLCanvasElement>) => {
    const owner = gesture.current;
    if (!owner || owner.pointerId !== event.pointerId) return;
    if (!owns(owner) || !editable()) { cancelGesture(false); return; }
    const location = point(event); if (!location) return;
    try { owner.mask.moveStroke(location.x, location.y); setCursor(location); refresh(); }
    catch (value) { cancelGesture(); fail(value); }
  };
  const finish = (event: PointerEvent<HTMLCanvasElement>) => {
    const owner = gesture.current;
    if (!owner || owner.pointerId !== event.pointerId) return;
    if (!owns(owner) || !editable()) { cancelGesture(false); return; }
    try {
      const location = point(event);
      if (location) { owner.mask.moveStroke(location.x, location.y); setCursor(location); }
      owner.mask.commitStroke(); gesture.current = null; release(owner.pointerId); refresh(); setError('');
      if (owns(owner)) latest.current.onChange();
    } catch (value) { cancelGesture(); fail(value); }
  };
  const cancelPointer = (event: PointerEvent<HTMLCanvasElement>) => {
    if (gesture.current?.pointerId === event.pointerId) cancelGesture();
  };
  const key = (event: KeyboardEvent<HTMLCanvasElement>) => {
    if (event.nativeEvent.isComposing || event.altKey || event.ctrlKey || event.metaKey) return;
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ', 'Spacebar', 'Escape'].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    if (!editable()) { cancelGesture(false); return; }
    if (event.key === 'Escape') {
      if (gesture.current) cancelGesture(); else run(() => mask.undo());
      return;
    }
    if (gesture.current || mask.activeStroke) return;
    if (event.key === ' ' || event.key === 'Spacebar') { run(() => mask.paint(cursor.x, cursor.y, integer(radius, '笔刷半径'), keep)); return; }
    const step = event.shiftKey ? 8 : 1;
    setCursor(current => ({
      x: Math.max(0, Math.min(mask.width - 1, current.x + (event.key === 'ArrowRight' ? step : event.key === 'ArrowLeft' ? -step : 0))),
      y: Math.max(0, Math.min(mask.height - 1, current.y + (event.key === 'ArrowDown' ? step : event.key === 'ArrowUp' ? -step : 0))),
    }));
  };

  const authorized = isCurrent();
  const disabled = readOnly || !safeSource || sourceFailed || !authorized;
  const controlsDisabled = disabled || mask.activeStroke;
  const cursorRadius = radius.length <= 4 && /^\d+$/.test(radius) && Number(radius) <= BINARY_MASK_MAX_RADIUS ? Math.max(0.5, Number(radius)) : 0.5;
  return <section aria-label="二值蒙版编辑" className="experimental-form">
    <div className="creative-actions" role="group" aria-label="蒙版笔刷工具">
      <Button type="button" disabled={controlsDisabled} aria-pressed={!keep} onClick={() => setKeep(false)}>黑色 REMOVE · 移除</Button>
      <Button type="button" disabled={controlsDisabled} aria-pressed={keep} onClick={() => setKeep(true)}>白色 KEEP · 保留</Button>
      <Button type="button" disabled={controlsDisabled || !mask.canUndo} onClick={() => run(() => mask.undo())}>撤销蒙版编辑</Button>
    </div>
    <Field label="笔刷半径（像素）"><input type="number" min="0" max={BINARY_MASK_MAX_RADIUS} step="1" value={radius}
      disabled={controlsDisabled} onChange={event => setRadius(event.target.value)} /></Field>
    <p id={instructionsId}>白色 KEEP 保留，黑色 REMOVE 移除。方向键移动光标，Shift + 方向键移动 8 像素，空格绘制，Escape 取消当前笔画或撤销。保存前须同时包含两种颜色。</p>
    {!safeSource && <StatusMessage tone="warning">请先读取并核对来源图片；只接受当前来源的本地 blob 预览。</StatusMessage>}
    {sourceFailed && <StatusMessage tone="error">来源预览加载失败，请重新读取并核对来源图片。</StatusMessage>}
    {!!displayError && <StatusMessage tone="warning">{displayError}</StatusMessage>}
    {!!error && <StatusMessage tone="error">{error}</StatusMessage>}
    <div style={{ position: 'relative', width: '100%', maxWidth: BINARY_MASK_MAX_SIZE, boxSizing: 'border-box', border: 'var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
      {safeSource && authorized && <img src={sourceUrl} alt="蒙版来源预览" draggable={false}
        onError={() => { setSourceFailed(true); cancelGesture(); }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', pointerEvents: 'none' }} />}
      <canvas ref={canvasRef} width={mask.width} height={mask.height} role="application" aria-label="二值蒙版绘图区"
        aria-describedby={instructionsId} aria-disabled={disabled} aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Space Escape" tabIndex={0}
        onPointerDown={begin} onPointerMove={move} onPointerUp={finish} onPointerCancel={cancelPointer} onLostPointerCapture={cancelPointer}
        onKeyDown={key} onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); cancelGesture(); }}
        style={{ position: 'relative', display: 'block', width: '100%', height: 'auto', touchAction: 'none', imageRendering: 'pixelated', cursor: disabled ? 'default' : 'crosshair',
          outline: focused ? 'var(--border-strong)' : undefined, boxShadow: focused ? 'var(--focus-ring)' : undefined, outlineOffset: 'var(--space-1)' }} />
      <svg aria-hidden="true" viewBox={`0 0 ${mask.width} ${mask.height}`}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', overflow: 'hidden' }}>
        <circle cx={cursor.x + 0.5} cy={cursor.y + 0.5} r={cursorRadius} fill="none" stroke="var(--color-accent-primary)" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
    <output aria-live="polite">{mask.width} × {mask.height} 像素 · 光标 X {cursor.x}，Y {cursor.y} · {keep ? '白色 KEEP' : '黑色 REMOVE'}</output>
    <div className="creative-actions" role="group" aria-label="精确矩形坐标">
      {([['x', '矩形 X', 0, mask.width - 1], ['y', '矩形 Y', 0, mask.height - 1], ['width', '矩形宽度', 1, mask.width], ['height', '矩形高度', 1, mask.height]] as const).map(([name, label, min, max]) =>
        <Field key={name} label={label}><input type="number" min={min} max={max} step="1" value={rectangle[name]} disabled={controlsDisabled}
          onChange={event => setRectangle(current => ({ ...current, [name]: event.target.value }))} /></Field>)}
    </div>
    <Button type="button" disabled={controlsDisabled} onClick={() => run(() => mask.rectangle(
      integer(rectangle.x, '矩形 X'), integer(rectangle.y, '矩形 Y'), integer(rectangle.width, '矩形宽度'), integer(rectangle.height, '矩形高度'), keep,
    ))}>应用精确矩形</Button>
    <div className="creative-actions" role="group" aria-label="整幅蒙版操作">
      <Button type="button" disabled={controlsDisabled} onClick={() => run(() => mask.clear(true))}>全部设为白色 KEEP</Button>
      <Button type="button" disabled={controlsDisabled} onClick={() => run(() => mask.clear(false))}>全部设为黑色 REMOVE</Button>
    </div>
  </section>;
}
