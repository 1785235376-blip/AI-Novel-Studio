import { useLayoutEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { apiErrorView } from '../api';
import type { ComicAsset, ComicPanel, comicLayoutsClient } from './comicLayoutsClient';
import { panComicFraming, readComicFramingImage, type ComicFramingPosition } from './comicImageFraming';

type Props = { panel: ComicPanel; asset?: ComicAsset; api: Pick<ReturnType<typeof comicLayoutsClient>, 'catalog' | 'image'>; disabled: boolean;
  getRevision: () => number; isCurrent: () => boolean; onApply: (patch: Pick<Partial<ComicPanel>, 'cover_x_percent' | 'cover_y_percent'>) => void };
type Thumbnail = { token: object; url: string; width: number; height: number };
type Drag = { token: object; panel: ComicPanel; revision: number; pointerId: number; x: number; y: number; width: number; height: number; start: ComicFramingPosition };
export function ComicImageFramingEditor(props: Props) {
  const [thumbnail, setThumbnail] = useState<Thumbnail>(), [pending, setPending] = useState<object>(), [error, setError] = useState(''), [loaded, setLoaded] = useState(false);
  const [projection, setProjection] = useState<ComicFramingPosition>();
  const alive = useRef(true), live = useRef(props); live.current = props;
  const owned = useRef<Thumbnail>(), flight = useRef<object>(), drag = useRef<Drag>(), image = useRef<HTMLImageElement>(null);
  const frameValid = Number.isSafeInteger(props.panel.width) && Number.isSafeInteger(props.panel.height) && props.panel.width >= 16 && props.panel.width <= 1600 && props.panel.height >= 16 && props.panel.height <= 12000;
  const values = [props.api, props.disabled, frameValid, props.panel.id, props.panel.fit, props.panel.asset_id, props.panel.expected_asset_version, props.asset?.id, props.asset?.version, props.asset?.approved];
  const source = useRef({ values, token: {} }); if (values.some((value, index) => value !== source.current.values[index])) source.current = { values, token: {} };
  const sourceToken = source.current.token, revision = props.getRevision();
  const editValues = [sourceToken, props.panel, revision], editor = useRef({ values: editValues, token: {} });
  if (editValues.some((value, index) => value !== editor.current.values[index])) editor.current = { values: editValues, token: {} };
  const editToken = editor.current.token;
  const current = () => alive.current && source.current.token === sourceToken && !live.current.disabled && live.current.isCurrent();
  const editable = () => current() && editor.current.token === editToken && revision === live.current.getRevision();
  const cancel = () => { drag.current = undefined; setProjection(undefined); };
  const release = () => { if (owned.current) URL.revokeObjectURL(owned.current.url); owned.current = undefined; };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; flight.current = undefined; drag.current = undefined; release(); }; }, []);
  useLayoutEffect(() => { release(); setThumbnail(undefined); setLoaded(false); setError(''); setPending(undefined); }, [sourceToken]);
  useLayoutEffect(cancel, [editToken]);
  const admitted = frameValid && props.asset?.approved === true && props.asset.id === props.panel.asset_id && props.asset.version === props.panel.expected_asset_version && props.panel.fit === 'COVER';
  const visible = thumbnail?.token === sourceToken && owned.current === thumbnail && current() ? thumbnail : undefined;
  const start = { x: props.panel.cover_x_percent ?? 50, y: props.panel.cover_y_percent ?? 50 };
  const validDrag = (value: Drag) => editable() && value.token === editToken && value.panel === live.current.panel && value.revision === live.current.getRevision();
  const shown = projection && drag.current && validDrag(drag.current) ? projection : start;
  function apply(next: ComicFramingPosition) {
    if (!editable() || !visible || owned.current !== visible || !loaded) return;
    const patch = { ...(next.x !== start.x ? { cover_x_percent: next.x } : {}), ...(next.y !== start.y ? { cover_y_percent: next.y } : {}) };
    if (Object.keys(patch).length) { editor.current = { ...editor.current, token: {} }; props.onApply(patch); }
  }
  async function load() {
    if (!current() || !admitted || !props.asset || flight.current === sourceToken) return;
    flight.current = sourceToken; cancel(); setPending(sourceToken); setError(''); release(); setThumbnail(undefined); setLoaded(false);
    const expectedRevision = props.getRevision(), stillCurrent = () => current() && expectedRevision === live.current.getRevision();
    try {
      const result = await readComicFramingImage(props.api, { ...props.asset }, stillCurrent);
      if (!stillCurrent()) return;
      const next = { token: sourceToken, url: URL.createObjectURL(result.blob), width: result.width, height: result.height };
      owned.current = next; setThumbnail(next);
    } catch (reason) { if (stillCurrent()) setError(apiErrorView(reason, '取景缩略图读取失败。').message); }
    finally { if (flight.current === sourceToken) flight.current = undefined; if (current()) setPending(undefined); }
  }
  function begin(event: PointerEvent<HTMLButtonElement>) {
    if (!editable() || !visible || owned.current !== visible || !loaded || drag.current || event.button !== 0) return;
    const rect = image.current?.getBoundingClientRect(); if (!rect?.width || !rect.height) return;
    event.preventDefault(); event.currentTarget.focus();
    drag.current = { token: editToken, panel: props.panel, revision, pointerId: event.pointerId, x: event.clientX, y: event.clientY, width: rect.width, height: rect.height, start };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  }
  function move(event: PointerEvent<HTMLButtonElement>, finish = false) {
    const value = drag.current; if (!value || value.pointerId !== event.pointerId) return;
    if (!validDrag(value) || !visible || owned.current !== visible) { cancel(); return; }
    const next = panComicFraming(visible, value, value.start, event.clientX - value.x, event.clientY - value.y);
    if (finish) { cancel(); apply(next); } else setProjection(next);
  }
  function key(event: KeyboardEvent<HTMLButtonElement>) {
    if (event.key === 'Escape') { cancel(); return; }
    if (!editable() || !visible || !loaded || drag.current || event.nativeEvent.isComposing || event.altKey || event.ctrlKey || event.metaKey) return;
    const delta = { ArrowLeft: [-1, 0], ArrowRight: [1, 0], ArrowUp: [0, -1], ArrowDown: [0, 1] }[event.key]; if (!delta) return;
    event.preventDefault(); const step = event.shiftKey ? 10 : 1;
    apply({ x: visible.width * props.panel.height > visible.height * props.panel.width ? Math.max(0, Math.min(100, start.x - delta[0] * step)) : start.x,
      y: visible.height * props.panel.width > visible.width * props.panel.height ? Math.max(0, Math.min(100, start.y - delta[1] * step)) : start.y });
  }
  const scale = frameValid ? Math.min(480 / props.panel.width, 320 / props.panel.height, 1) : 1;
  return <details aria-label="格内图片取景编辑"><summary>在图片上调整取景</summary>
    <p>按需读取原漫画缩略图，读取前后核对图片版本与批准状态。拖动画面，松开后作为一次可撤销修改；方向键平移 1%，Shift 平移 10%，Esc 取消拖动。这里只示意图片裁切，不含气泡、边框或图层效果；最终以保存后的原像素预检为准。</p>
    {!admitted && <StatusMessage>请先绑定版本一致的已批准图片，并使用裁切填满模式。</StatusMessage>}
    <Button disabled={props.disabled || !admitted || pending === sourceToken} onClick={() => void load()}>读取并核对取景图片</Button>
    {pending === sourceToken && <StatusMessage>正在读取原漫画缩略图…</StatusMessage>}{error && <StatusMessage tone="warning">{error}</StatusMessage>}
    {visible && <>
      <Button className="comic-framing-surface" aria-label="拖动格内图片取景" disabled={props.disabled || !loaded} style={{ width: props.panel.width * scale, height: props.panel.height * scale }}
        onPointerDown={begin} onPointerMove={event => move(event)} onPointerUp={event => move(event, true)} onPointerCancel={cancel} onLostPointerCapture={cancel} onKeyDown={key}>
        <img ref={image} src={visible.url} draggable={false} alt="当前格框图片取景示意" style={{ objectPosition: `${shown.x}% ${shown.y}%` }} onLoad={event => {
          if (!current() || owned.current !== visible) return;
          if (event.currentTarget.naturalWidth !== visible.width || event.currentTarget.naturalHeight !== visible.height) { release(); setThumbnail(undefined); setLoaded(false); setError('缩略图解码尺寸不一致，未启用取景编辑。'); }
          else setLoaded(true);
        }} onError={() => { if (current() && owned.current === visible) { release(); setThumbnail(undefined); setLoaded(false); setError('缩略图无法解码，请重新读取。'); } }} />
      </Button>
      <p aria-live="polite">取景位置：水平 {shown.x}% · 垂直 {shown.y}%</p>
      <Button disabled={props.disabled || !loaded || start.x === 50 && start.y === 50} onClick={() => apply({ x: 50, y: 50 })}>恢复居中取景</Button>
      <Button onClick={() => { if (!current()) return; cancel(); release(); setThumbnail(undefined); setLoaded(false); }}>关闭取景图片</Button>
    </>}
  </details>;
}
