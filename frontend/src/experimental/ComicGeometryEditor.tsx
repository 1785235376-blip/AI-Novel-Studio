import { useLayoutEffect, useRef, useState } from 'react';
import type { KeyboardEvent, PointerEvent } from 'react';
import { MoveDiagonal2 } from 'lucide-react';
import { Button } from '../ui/primitives';
import type { ComicDocument, ComicPanel, ComicRect } from './comicLayoutsClient';
import { transformComicGeometry, translateComicPanels, type ComicGeometryMode, type ComicGeometryTarget } from './comicGeometry';
type Props = { document: ComicDocument; disabled: boolean; getRevision: () => number; isCurrent: () => boolean; onApply: (next: ComicDocument) => void };
type Gesture = { pointerId: number; target: ComicGeometryTarget; mode: ComicGeometryMode; x: number; y: number; scaleX: number; scaleY: number; base: ComicDocument; revision: number; token: object; next: ComicDocument };
export function ComicGeometryEditor(props: Props) {
  const [selection, setSelection] = useState<ComicGeometryTarget>();
  const [projection, setProjection] = useState<Gesture>();
  const [group, setGroup] = useState<readonly ComicPanel[]>([]), [groupStep, setGroupStep] = useState(10);
  const groupEpoch = useRef(0), renderedGroupEpoch = groupEpoch.current, renderedRevision = props.getRevision();
  const selectedGroup = group.filter(panel => props.document.panels.includes(panel));
  const gesture = useRef<Gesture>();
  const surface = useRef<HTMLDivElement>(null), alive = useRef(true);
  const values = [props.document, props.disabled, props.getRevision()];
  const owner = useRef({ values, token: {} });
  if (values.some((v, i) => v !== owner.current.values[i])) owner.current = { values, token: {} };
  const token = owner.current.token;
  useLayoutEffect(() => { gesture.current = undefined; setProjection(undefined); }, [token]);
  const live = useRef(props); live.current = props;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; gesture.current = undefined; }; }, []);
  const current = () => alive.current && !live.current.disabled && token === owner.current.token && live.current.isCurrent();
  const validGesture = (g: Gesture) => current() && g.token === token && g.base === live.current.document && g.revision === live.current.getRevision();
  const groupCurrent = () => current() && !gesture.current && renderedRevision === live.current.getRevision() && renderedGroupEpoch === groupEpoch.current;
  const cancel = () => { gesture.current = undefined; setProjection(undefined); };
  const shown = projection && validGesture(projection) ? projection.next : props.document;
  const selected = (target: ComicGeometryTarget) => selection?.panelId === target.panelId && selection?.bubbleId === target.bubbleId || !target.bubbleId && selectedGroup.some(panel => panel.id === target.panelId);
  const style = (r: ComicRect) => ({ left: `${r.x / shown.width * 100}%`, top: `${r.y / shown.height * 100}%`, width: `${r.width / shown.width * 100}%`, height: `${r.height / shown.height * 100}%` });
  function start(event: PointerEvent<HTMLButtonElement>, target: ComicGeometryTarget, mode: ComicGeometryMode) {
    if (!current() || event.button !== 0 || gesture.current) return;
    const box = surface.current?.getBoundingClientRect();
    if (!box?.width || !box.height) return;
    event.preventDefault(); event.currentTarget.focus(); setSelection(target);
    const next = { pointerId: event.pointerId, target, mode, x: event.clientX, y: event.clientY, scaleX: props.document.width / box.width, scaleY: props.document.height / box.height, base: props.document, revision: props.getRevision(), token, next: props.document };
    gesture.current = next; setProjection(next);
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function move(event: PointerEvent<HTMLButtonElement>, finish = false) {
    const g = gesture.current;
    if (!g || g.pointerId !== event.pointerId) return;
    if (!validGesture(g)) { cancel(); return; }
    const next = transformComicGeometry(g.base, g.target, g.mode, (event.clientX - g.x) * g.scaleX, (event.clientY - g.y) * g.scaleY);
    if (finish) { cancel(); if (next !== g.base) props.onApply(next); }
    else { const updated = { ...g, next }; gesture.current = updated; setProjection(updated); }
  }
  function key(event: KeyboardEvent<HTMLButtonElement>, target: ComicGeometryTarget, mode: ComicGeometryMode) {
    if (event.key === 'Escape') { cancel(); return; }
    if (event.nativeEvent.isComposing || event.altKey || event.ctrlKey || event.metaKey || !current() || gesture.current) return;
    const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key];
    if (!delta) return;
    event.preventDefault(); setSelection(target);
    const step = event.shiftKey ? 10 : 1;
    const next = transformComicGeometry(props.document, target, mode, delta[0] * step, delta[1] * step);
    if (next !== props.document) props.onApply(next);
  }
  function controls(target: ComicGeometryTarget, rect: ComicRect, label: string) {
    return <div key={`${target.panelId}/${target.bubbleId || ''}`} className={`comic-geometry-object ${target.bubbleId ? 'comic-geometry-bubble' : ''} ${selected(target) ? 'is-selected' : ''}`} style={style(rect)}>
      <Button className="comic-geometry-move" disabled={props.disabled} aria-label={`移动${label}`} aria-pressed={selected(target)} onClick={() => { if (current()) setSelection(target); }} onFocus={() => { if (current()) setSelection(target); }} onPointerDown={e => start(e, target, 'move')} onPointerMove={e => move(e)} onPointerUp={e => move(e, true)} onPointerCancel={cancel} onLostPointerCapture={cancel} onKeyDown={e => key(e, target, 'move')}>{label}</Button>
      <Button className="comic-geometry-resize" disabled={props.disabled} aria-label={`调整${label}大小`} onPointerDown={e => start(e, target, 'resize')} onPointerMove={e => move(e)} onPointerUp={e => move(e, true)} onPointerCancel={cancel} onLostPointerCapture={cancel} onKeyDown={e => key(e, target, 'resize')}><MoveDiagonal2 size={16} aria-hidden="true" /></Button>
    </div>;
  }
  function moveGroup(dx: number, dy: number) {
    if (!groupCurrent()) return;
    const ids = selectedGroup.map(panel => panel.id), next = translateComicPanels(props.document, ids, dx * groupStep, dy * groupStep);
    if (next === props.document) return;
    groupEpoch.current++;
    setGroup(next.panels.filter(panel => ids.includes(panel.id)));
    props.onApply(next);
  }
  return <section aria-label="漫画几何示意编辑器">
    <h4>格框与气泡位置示意</h4>
    <p>仅示意几何范围，不显示图片像素、字体排版或图层效果。拖动名称移动，拖动右下角调整大小；聚焦相应按钮后用方向键微调 1 px，Shift 加速至 10 px。Esc 取消拖动。松开后计为一次可撤销修改。</p>
    <p>移动格框会连同气泡平移；缩小格框会保留气泡范围。坐标限制在页面安全区或所属格框的 8 px 内边距内。无效数值草稿请先用下方数值输入修正。重叠和文字溢出仍须保存后通过原预检核对。</p>
    <div ref={surface} className="comic-geometry-surface" style={{ aspectRatio: `${props.document.width} / ${props.document.height}` }}>
      {shown.panels.map((panel, i) => controls({ panelId: panel.id }, panel, `示意格框 ${i + 1}`))}
      {shown.panels.flatMap((panel, i) => panel.bubbles.map((bubble, j) => controls({ panelId: panel.id, bubbleId: bubble.id }, bubble, `示意格框 ${i + 1} 气泡 ${j + 1}`)))}
    </div>
    <details aria-label="漫画格框整体平移">
      <summary>多选格框整体平移</summary>
      <p>选中格框按同一位移移动，气泡随格框平移，间距、阅读顺序和图片引用保持原样。触及安全区时整组一起停止；每次移动只计一次可撤销修改。新页面或所选格框被其他编辑替换后须重新选择。</p>
      <fieldset disabled={props.disabled || !!projection}>
        <legend>选择整体移动的格框</legend>
        {props.document.panels.map((panel, index) => <label className="experimental-check" key={panel.id}><input type="checkbox" checked={selectedGroup.includes(panel)} onChange={event => {
          if (!groupCurrent()) return;
          groupEpoch.current++;
          setGroup(event.target.checked ? [...selectedGroup, panel] : selectedGroup.filter(value => value !== panel));
        }} />整体移动格框 {index + 1}</label>)}
        <label>整体平移步长<select value={groupStep} onChange={event => {
          if (!groupCurrent() || !['1', '10', '100'].includes(event.target.value)) return;
          groupEpoch.current++; setGroupStep(Number(event.target.value));
        }}><option value="1">1 px</option><option value="10">10 px</option><option value="100">100 px</option></select></label>
        <p aria-live="polite">已选 {selectedGroup.length} 个格框</p>
        <div className="experimental-actions">{([['左', -1, 0], ['右', 1, 0], ['上', 0, -1], ['下', 0, 1]] as const).map(([label, dx, dy]) => <Button key={label}
          disabled={!selectedGroup.length || translateComicPanels(props.document, selectedGroup.map(panel => panel.id), dx * groupStep, dy * groupStep) === props.document}
          onClick={() => moveGroup(dx, dy)}>所选格框{label}移</Button>)}</div>
      </fieldset>
    </details>
  </section>;
}
