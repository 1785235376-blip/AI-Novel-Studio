import { useEffect, useId, useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { Field } from '../experimental/shared';
import { BINARY_MASK_MAX_RADIUS, BINARY_MASK_MAX_SIZE, BINARY_MASK_POLYGON_MAX_VERTICES, BinaryMaskDraft, type BinaryMaskPoint, type BinaryMaskPolygonPreview } from './studioBinaryMask';

export type StudioBinaryMaskCanvasProps = {
  mask: BinaryMaskDraft;
  sourceUrl: string;
  readOnly: boolean;
  isCurrent: () => boolean;
  onChange: () => void;
};
type Gesture = { pointerId: number; mask: BinaryMaskDraft; sourceUrl: string };
type Point = { x: number; y: number };
type PolygonProof = { token: object; epoch: number; revision: number; selection: BinaryMaskPolygonPreview };
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
  const [tool, setTool] = useState<'BRUSH' | 'POLYGON'>('BRUSH'), [vertices, setVertices] = useState<readonly BinaryMaskPoint[]>([]);
  const [vertexInput, setVertexInput] = useState({ x: '0', y: '0' }), [polygonPreview, setPolygonPreview] = useState<PolygonProof>();
  const alive = useRef(true), points = useRef<readonly BinaryMaskPoint[]>([]), polygonEpoch = useRef(0), proof = useRef<PolygonProof>();
  const instructionsId = useId();
  const safeSource = sourceUrl.startsWith('blob:');
  const latest = useRef({ mask, sourceUrl, readOnly, isCurrent, onChange, sourceFailed, safeSource, tool });
  latest.current = { mask, sourceUrl, readOnly, isCurrent, onChange, sourceFailed, safeSource, tool };
  const authorized = isCurrent();
  const scopeValues = [mask, sourceUrl, readOnly, sourceFailed, safeSource, authorized, tool, mask.revision];
  const polygonScope = useRef({ values: scopeValues, token: {} });
  if (scopeValues.some((value, index) => value !== polygonScope.current.values[index])) polygonScope.current = { values: scopeValues, token: {} };
  const polygonToken = polygonScope.current.token, renderedPolygonEpoch = polygonEpoch.current, renderedMaskRevision = mask.revision;
  const refresh = () => setPreviewRevision(value => value + 1);
  const owns = (owner: Gesture) => {
    const current = latest.current;
    return current.mask === owner.mask && current.sourceUrl === owner.sourceUrl && current.isCurrent();
  };
  const editable = () => {
    const current = latest.current;
    return alive.current && current.mask === mask && current.sourceUrl === sourceUrl && current.tool === tool && !current.readOnly && current.safeSource && !current.sourceFailed && current.isCurrent();
  };
  const clearPolygon = () => {
    polygonEpoch.current++; points.current = []; proof.current = undefined;
    setVertices([]); setPolygonPreview(undefined);
  };
  const polygonCurrent = () => {
    if (!alive.current || polygonScope.current.token !== polygonToken || renderedPolygonEpoch !== polygonEpoch.current || renderedMaskRevision !== mask.revision) return false;
    if (!editable()) { clearPolygon(); return false; }
    return tool === 'POLYGON';
  };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; proof.current = undefined; points.current = []; }; }, []);
  useLayoutEffect(() => { clearPolygon(); setVertexInput({ x: '0', y: '0' }); }, [polygonToken]);
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
  const invalidatePolygonPreview = () => { polygonEpoch.current++; proof.current = undefined; setPolygonPreview(undefined); };
  const addVertex = (value: BinaryMaskPoint) => {
    if (!polygonCurrent() || gesture.current || mask.activeStroke) return;
    try {
      if (points.current.length >= BINARY_MASK_POLYGON_MAX_VERTICES) throw new Error('多边形最多 32 个顶点，请先移除顶点。');
      if (!Number.isInteger(value.x) || !Number.isInteger(value.y) || value.x < 0 || value.x > mask.width || value.y < 0 || value.y > mask.height) throw new Error('多边形顶点超出原图边界，不会自动裁剪。');
      invalidatePolygonPreview(); points.current = [...points.current, { ...value }]; setVertices(points.current); setError('');
    } catch (value) { fail(value); }
  };
  const previewPolygon = () => {
    if (!polygonCurrent() || gesture.current || mask.activeStroke) return;
    try {
      proof.current = undefined; setPolygonPreview(undefined);
      const selection = mask.previewPolygon(points.current), value = { token: polygonToken, epoch: polygonEpoch.current, revision: mask.revision, selection };
      proof.current = value; setPolygonPreview(value); setError('');
    } catch (value) { fail(value); }
  };
  const run = (action: () => boolean) => {
    if (!editable() || gesture.current || mask.activeStroke) return;
    clearPolygon();
    try { const changed = action(); setError(''); refresh(); if (changed && editable()) latest.current.onChange(); }
    catch (value) { fail(value); }
  };
  const begin = (event: PointerEvent<HTMLCanvasElement>) => {
    if (event.button !== 0 || gesture.current || mask.activeStroke || !editable()) return;
    if (tool === 'POLYGON') {
      if (!polygonCurrent()) return;
      const bounds = event.currentTarget.getBoundingClientRect();
      if (!Number.isFinite(bounds.width) || !Number.isFinite(bounds.height) || bounds.width <= 0 || bounds.height <= 0
        || !Number.isFinite(event.clientX) || !Number.isFinite(event.clientY)) return;
      if (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom) { fail(new Error('多边形顶点超出原图边界，不会自动裁剪。')); return; }
      event.preventDefault(); event.currentTarget.focus();
      addVertex({ x: Math.floor((event.clientX - bounds.left) * mask.width / bounds.width), y: Math.floor((event.clientY - bounds.top) * mask.height / bounds.height) });
      return;
    }
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
    if (!['ArrowLeft', 'ArrowRight', 'ArrowUp', 'ArrowDown', ' ', 'Spacebar', 'Escape', ...(tool === 'POLYGON' ? ['Enter', 'Backspace'] : [])].includes(event.key)) return;
    event.preventDefault(); event.stopPropagation();
    if (!editable()) { cancelGesture(false); return; }
    if (tool === 'POLYGON') {
      if (!polygonCurrent()) return;
      if (event.key === 'Escape') { clearPolygon(); return; }
      if (event.key === ' ' || event.key === 'Spacebar' || event.key === 'Enter') { addVertex(cursor); return; }
      if (event.key === 'Backspace') { invalidatePolygonPreview(); points.current = points.current.slice(0, -1); setVertices(points.current); return; }
    }
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

  const disabled = readOnly || !safeSource || sourceFailed || !authorized;
  const controlsDisabled = disabled || mask.activeStroke;
  const visiblePolygon = !disabled && tool === 'POLYGON' && polygonPreview && proof.current === polygonPreview && polygonPreview.token === polygonToken && polygonPreview.epoch === polygonEpoch.current && polygonPreview.revision === mask.revision ? polygonPreview : undefined;
  const applyPolygon = (keepPixels: boolean) => {
    if (!polygonCurrent() || !visiblePolygon || proof.current !== visiblePolygon || mask.activeStroke) return;
    const selected = visiblePolygon.selection; proof.current = undefined;
    run(() => mask.polygon(selected.vertices, keepPixels));
  };
  const cursorRadius = radius.length <= 4 && /^\d+$/.test(radius) && Number(radius) <= BINARY_MASK_MAX_RADIUS ? Math.max(0.5, Number(radius)) : 0.5;
  return <section aria-label="二值蒙版编辑" className="experimental-form">
    <div className="creative-actions" role="group" aria-label="蒙版编辑方式">{(['BRUSH', 'POLYGON'] as const).map(value => <Button key={value} type="button" disabled={controlsDisabled} aria-pressed={tool === value} onClick={() => {
      if (!editable() || mask.activeStroke || polygonScope.current.token !== polygonToken || polygonEpoch.current !== renderedPolygonEpoch) return;
      clearPolygon(); setTool(value); setError('');
    }}>{value === 'BRUSH' ? '笔刷编辑' : '多边形选区'}</Button>)}</div>
    <div className="creative-actions" role="group" aria-label="蒙版笔刷工具">
      <Button type="button" disabled={controlsDisabled} aria-pressed={!keep} onClick={() => setKeep(false)}>黑色 REMOVE · 移除</Button>
      <Button type="button" disabled={controlsDisabled} aria-pressed={keep} onClick={() => setKeep(true)}>白色 KEEP · 保留</Button>
      <Button type="button" disabled={controlsDisabled || !mask.canUndo} onClick={() => run(() => mask.undo())}>撤销蒙版编辑</Button>
    </div>
    <Field label="笔刷半径（像素）"><input type="number" min="0" max={BINARY_MASK_MAX_RADIUS} step="1" value={radius}
      disabled={controlsDisabled} onChange={event => setRadius(event.target.value)} /></Field>
    <p id={instructionsId}>{tool === 'POLYGON' ? '逐点点击圈选；方向键移动光标，空格或 Enter 添加顶点，Backspace 移除末点，Escape 取消选区。先明确预览，再选择 KEEP 或 REMOVE 填充；选点和预览不修改蒙版。' : '白色 KEEP 保留，黑色 REMOVE 移除。方向键移动光标，Shift + 方向键移动 8 像素，空格绘制，Escape 取消当前笔画或撤销。'}保存前须同时包含两种颜色。</p>
    {!safeSource && <StatusMessage tone="warning">请先读取并核对来源图片；只接受当前来源的本地 blob 预览。</StatusMessage>}
    {sourceFailed && <StatusMessage tone="error">来源预览加载失败，请重新读取并核对来源图片。</StatusMessage>}
    {!!displayError && <StatusMessage tone="warning">{displayError}</StatusMessage>}
    {!!error && <StatusMessage tone="error">{error}</StatusMessage>}
    <div style={{ position: 'relative', width: '100%', maxWidth: BINARY_MASK_MAX_SIZE, boxSizing: 'border-box', border: 'var(--border-default)', borderRadius: 'var(--radius-sm)' }}>
      {safeSource && authorized && <img src={sourceUrl} alt="蒙版来源预览" draggable={false}
        onError={() => { if (!alive.current || polygonScope.current.token !== polygonToken) return; clearPolygon(); setSourceFailed(true); cancelGesture(); }}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', objectFit: 'fill', pointerEvents: 'none' }} />}
      <canvas ref={canvasRef} width={mask.width} height={mask.height} role="application" aria-label="二值蒙版绘图区"
        aria-describedby={instructionsId} aria-disabled={disabled} aria-keyshortcuts="ArrowUp ArrowDown ArrowLeft ArrowRight Space Escape" tabIndex={0}
        onPointerDown={begin} onPointerMove={move} onPointerUp={finish} onPointerCancel={cancelPointer} onLostPointerCapture={cancelPointer}
        onKeyDown={key} onFocus={() => setFocused(true)} onBlur={() => { setFocused(false); cancelGesture(); }}
        style={{ position: 'relative', display: 'block', width: '100%', height: 'auto', touchAction: 'none', imageRendering: 'pixelated', cursor: disabled ? 'default' : 'crosshair',
          outline: focused ? 'var(--border-strong)' : undefined, boxShadow: focused ? 'var(--focus-ring)' : undefined, outlineOffset: 'var(--space-1)' }} />
      <svg aria-hidden="true" viewBox={`0 0 ${mask.width} ${mask.height}`}
        style={{ position: 'absolute', inset: 0, width: '100%', height: '100%', pointerEvents: 'none', overflow: 'hidden' }}>
        {tool === 'POLYGON' && vertices.length > 0 && (visiblePolygon ? <polygon points={vertices.map(point => `${point.x},${point.y}`).join(' ')} fill="var(--color-accent-subtle)" stroke="var(--color-accent-primary)" vectorEffect="non-scaling-stroke" /> : <polyline points={vertices.map(point => `${point.x},${point.y}`).join(' ')} fill="none" stroke="var(--color-accent-primary)" vectorEffect="non-scaling-stroke" />)}
        <circle cx={cursor.x + (tool === 'BRUSH' ? 0.5 : 0)} cy={cursor.y + (tool === 'BRUSH' ? 0.5 : 0)} r={tool === 'BRUSH' ? cursorRadius : 0.5} fill="none" stroke="var(--color-accent-primary)" vectorEffect="non-scaling-stroke" />
      </svg>
    </div>
    <output aria-live="polite">{mask.width} × {mask.height} 像素 · 光标 X {cursor.x}，Y {cursor.y} · {keep ? '白色 KEEP' : '黑色 REMOVE'}</output>
    {tool === 'POLYGON' && <section aria-label="多边形蒙版选区">
      <p>3–32 个整数顶点，按轮廓顺序闭合，不支持自交、相触或零面积。顶点位于像素网格角点，X 可到 {mask.width}、Y 可到 {mask.height}；超界拒绝。填充内部及边界上的像素中心（x+0.5, y+0.5），不抗锯齿；轮廓仅为示意。保留原尺寸和 16 步历史。</p>
      <div className="creative-actions">{(['x', 'y'] as const).map(axis => <Field key={axis} label={`多边形顶点 ${axis.toUpperCase()}`}><input type="number" min={0} max={axis === 'x' ? mask.width : mask.height} step={1} value={vertexInput[axis]} disabled={controlsDisabled} onChange={event => {
        if (!polygonCurrent()) return; invalidatePolygonPreview(); setVertexInput(value => ({ ...value, [axis]: event.target.value }));
      }} /></Field>)}</div>
      <Button disabled={controlsDisabled || vertices.length >= BINARY_MASK_POLYGON_MAX_VERTICES} onClick={() => { if (!polygonCurrent()) return; try { addVertex({ x: integer(vertexInput.x, '顶点 X'), y: integer(vertexInput.y, '顶点 Y') }); } catch (value) { fail(value); } }}>添加坐标顶点</Button>
      <ol aria-label="多边形顶点顺序">{vertices.map((point, index) => <li key={index}>顶点 {index + 1}：({point.x}, {point.y}) <Button disabled={controlsDisabled} onClick={() => {
        if (!polygonCurrent()) return; invalidatePolygonPreview(); points.current = points.current.filter((_, i) => i !== index); setVertices(points.current);
      }}>移除顶点 {index + 1}</Button></li>)}</ol>
      <Button disabled={controlsDisabled || vertices.length < 3} onClick={previewPolygon}>预览多边形选区</Button>
      <Button disabled={controlsDisabled || !vertices.length} onClick={() => { if (polygonCurrent()) clearPolygon(); }}>取消多边形选区</Button>
      {visiblePolygon && <StatusMessage>已预览 {visiblePolygon.selection.vertices.length} 个顶点，选中 {visiblePolygon.selection.selected_pixels} 个像素；蒙版尚未修改。</StatusMessage>}
      <div className="creative-actions"><Button disabled={controlsDisabled || !visiblePolygon} onClick={() => applyPolygon(true)}>填充选区为白色 KEEP</Button><Button disabled={controlsDisabled || !visiblePolygon} onClick={() => applyPolygon(false)}>填充选区为黑色 REMOVE</Button></div>
    </section>}
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
