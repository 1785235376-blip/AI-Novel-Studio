import { useLayoutEffect, useRef } from 'react';
import { clampGraphPosition } from './graphCanvasGeometry';
import { MEDIA_CARD_HEIGHT, MEDIA_CARD_WIDTH, mediaOverview } from './mediaCanvasGeometry';
import type { CanvasDefinition } from './studioCanvasViewClient';
type Props = { definition: CanvasDefinition; size: { width: number; height: number }; owner: object; disabled: boolean; isCurrent: () => boolean; onChange: (value: CanvasDefinition) => void };
/** One bitmap node draws all bounded card locations without a second DOM card tree. */
export function MediaCanvasMiniMap(props: Props) {
  const canvas = useRef<HTMLCanvasElement>(null), alive = useRef(true), live = useRef(props); live.current = props;
  const overview = mediaOverview(props.definition, props.size.width, props.size.height);
  const values = [props.definition, props.owner, props.disabled, props.size.width, props.size.height];
  const fence = useRef({ values, token: {} }); if (values.some((v, i) => !Object.is(v, fence.current.values[i]))) fence.current = { values, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && !live.current.disabled && live.current.isCurrent();
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => {
    const node = canvas.current; if (!node) return; const ctx = node.getContext('2d'); if (!ctx) return;
    const style = getComputedStyle(node), color = (name: string) => style.getPropertyValue(name).trim();
    ctx.clearRect(0, 0, 200, 120); ctx.fillStyle = color('--color-bg-subtle'); ctx.fillRect(0, 0, 200, 120);
    const x = (value: number) => overview.offsetX + (value - overview.left) * overview.scale, y = (value: number) => overview.offsetY + (value - overview.top) * overview.scale;
    ctx.fillStyle = color('--color-text-muted');
    for (const card of props.definition.cards) ctx.fillRect(x(card.position.x), y(card.position.y), Math.max(1, MEDIA_CARD_WIDTH * overview.scale), Math.max(1, MEDIA_CARD_HEIGHT * overview.scale));
    ctx.strokeStyle = color('--color-accent-primary'); ctx.lineWidth = 1;
    ctx.strokeRect(x(overview.camera.x), y(overview.camera.y), overview.camera.width * overview.scale, overview.camera.height * overview.scale);
  }, [token]);
  function center(worldX: number, worldY: number) { if (!current()) return; props.onChange({ ...props.definition, viewport: { ...props.definition.viewport,
    x: clampGraphPosition(props.size.width / 2 - worldX * props.definition.viewport.zoom), y: clampGraphPosition(props.size.height / 2 - worldY * props.definition.viewport.zoom) } }); }
  return <div className="media-canvas__minimap"><canvas ref={canvas} width={200} height={120} role="button" tabIndex={props.disabled ? -1 : 0} aria-disabled={props.disabled} aria-label="媒体画布缩略导航"
    onClick={event => { const rect = event.currentTarget.getBoundingClientRect(); if (!rect.width || !rect.height) return;
      const x = (event.clientX - rect.left) * 200 / rect.width, y = (event.clientY - rect.top) * 120 / rect.height;
      center(overview.left + (x - overview.offsetX) / overview.scale, overview.top + (y - overview.offsetY) / overview.scale);
    }} onKeyDown={event => { if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); center((overview.left + overview.right) / 2, (overview.top + overview.bottom) / 2); } }} />
    <p>缩略导航显示全部 {props.definition.cards.length} 张卡片位置与当前视口。点击定位；键盘 Enter 或空格回到整体中心。</p></div>;
}
