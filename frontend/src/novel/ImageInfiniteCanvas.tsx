import { useMemo, useRef, useState } from "react";
import {
  BringToFront,
  Eye,
  EyeOff,
  Group,
  Lock,
  Redo2,
  SendToBack,
  Ungroup,
  Unlock,
  Undo2,
  ZoomIn,
  ZoomOut,
} from "lucide-react";
import { Button } from "../ui/primitives";
import type {
  CanvasViewport,
  RefNode,
} from "./useMultimodalWorkspacePersistence";

type Props = {
  nodes: RefNode[];
  onChange: (value: React.SetStateAction<RefNode[]>, record?: boolean) => void;
  viewport: CanvasViewport;
  onViewportChange: (value: CanvasViewport) => void;
  undo: () => void;
  redo: () => void;
  canUndo: boolean;
  canRedo: boolean;
};
const clampZoom = (value: number) => Math.min(2.5, Math.max(0.35, value));

export function ImageInfiniteCanvas({
  nodes,
  onChange,
  viewport,
  onViewportChange,
  undo,
  redo,
  canUndo,
  canRedo,
}: Props) {
  const [selected, setSelected] = useState<string[]>([]);
  const [marquee, setMarquee] = useState<{
    x: number;
    y: number;
    width: number;
    height: number;
  }>();
  const drag = useRef<{
    startX: number;
    startY: number;
    before: RefNode[];
    ids: string[];
  } | null>(null);
  const pan = useRef<{
    startX: number;
    startY: number;
    x: number;
    y: number;
  } | null>(null);
  const box = useRef<{ x: number; y: number } | null>(null);
  const visible = useMemo(
    () => nodes.filter((node) => !node.hidden).sort((a, b) => a.z - b.z),
    [nodes],
  );
  const patchSelected = (patch: Partial<RefNode>) =>
    onChange((items) =>
      items.map((item) =>
        selected.includes(item.id) ? { ...item, ...patch } : item,
      ),
    );
  const zoomBy = (amount: number) =>
    onViewportChange({ ...viewport, zoom: clampZoom(viewport.zoom + amount) });
  const removeSelected = () => {
    onChange((items) =>
      items.filter((item) => !selected.includes(item.id) || item.locked),
    );
    setSelected((ids) =>
      ids.filter((id) => nodes.find((node) => node.id === id)?.locked),
    );
  };
  const alignTop = () => {
    const active = nodes.filter(
      (node) => selected.includes(node.id) && !node.locked,
    );
    if (active.length < 2) return;
    const y = Math.min(...active.map((node) => node.y));
    onChange((items) =>
      items.map((item) =>
        selected.includes(item.id) && !item.locked ? { ...item, y } : item,
      ),
    );
  };
  const reorder = (front: boolean) =>
    patchSelected({
      z: front
        ? Math.max(0, ...nodes.map((n) => n.z)) + 1
        : Math.min(0, ...nodes.map((n) => n.z)) - 1,
    });
  return (
    <section
      className="image-canvas"
      aria-label="图片无限画布"
      tabIndex={0}
      onKeyDown={(event) => {
        if (
          (event.key === "Delete" || event.key === "Backspace") &&
          !(event.target instanceof HTMLInputElement)
        ) {
          event.preventDefault();
          removeSelected();
        }
        if (
          (event.ctrlKey || event.metaKey) &&
          event.key.toLowerCase() === "z"
        ) {
          event.preventDefault();
          event.shiftKey ? redo() : undo();
        }
      }}
    >
      <header className="image-canvas__toolbar">
        <span>
          {selected.length
            ? `已选 ${selected.length}`
            : `${nodes.length} 个节点`}
        </span>
        <Button
          variant="ghost"
          aria-label="撤销画布操作"
          disabled={!canUndo}
          onClick={undo}
        >
          <Undo2 size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="重做画布操作"
          disabled={!canRedo}
          onClick={redo}
        >
          <Redo2 size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="缩小画布"
          onClick={() => zoomBy(-0.15)}
        >
          <ZoomOut size={15} />
        </Button>
        <output aria-label="画布缩放">
          {Math.round(viewport.zoom * 100)}%
        </output>
        <Button
          variant="ghost"
          aria-label="放大画布"
          onClick={() => zoomBy(0.15)}
        >
          <ZoomIn size={15} />
        </Button>
        <span className="image-canvas__divider" />
        <Button
          variant="ghost"
          aria-label="对齐顶部"
          disabled={selected.length < 2}
          onClick={alignTop}
        >
          对齐
        </Button>
        <Button
          variant="ghost"
          aria-label="组合节点"
          disabled={selected.length < 2}
          onClick={() =>
            patchSelected({ groupId: `group-${Date.now().toString(36)}` })
          }
        >
          <Group size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="取消组合"
          disabled={!selected.length}
          onClick={() => patchSelected({ groupId: undefined })}
        >
          <Ungroup size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="移到顶层"
          disabled={!selected.length}
          onClick={() => reorder(true)}
        >
          <BringToFront size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="移到底层"
          disabled={!selected.length}
          onClick={() => reorder(false)}
        >
          <SendToBack size={15} />
        </Button>
        <Button
          variant="ghost"
          aria-label="锁定或解锁节点"
          disabled={!selected.length}
          onClick={() =>
            patchSelected({
              locked: !selected.every(
                (id) => nodes.find((node) => node.id === id)?.locked,
              ),
            })
          }
        >
          {selected.every(
            (id) => nodes.find((node) => node.id === id)?.locked,
          ) ? (
            <Unlock size={15} />
          ) : (
            <Lock size={15} />
          )}
        </Button>
      </header>
      <div
        className="image-canvas__viewport"
        onWheel={(event) => {
          if (event.ctrlKey) {
            event.preventDefault();
            zoomBy(event.deltaY > 0 ? -0.1 : 0.1);
          }
        }}
        onPointerDown={(event) => {
          if (event.altKey || event.button === 1) {
            pan.current = {
              startX: event.clientX,
              startY: event.clientY,
              x: viewport.x,
              y: viewport.y,
            };
            event.currentTarget.setPointerCapture(event.pointerId);
            return;
          }
          if (event.target === event.currentTarget) {
            const rect = event.currentTarget.getBoundingClientRect();
            box.current = {
              x: event.clientX - rect.left,
              y: event.clientY - rect.top,
            };
            setMarquee({
              x: box.current.x,
              y: box.current.y,
              width: 0,
              height: 0,
            });
            if (!event.shiftKey) setSelected([]);
            event.currentTarget.setPointerCapture(event.pointerId);
          }
        }}
        onPointerMove={(event) => {
          if (pan.current) {
            onViewportChange({
              ...viewport,
              x: pan.current.x + event.clientX - pan.current.startX,
              y: pan.current.y + event.clientY - pan.current.startY,
            });
          } else if (box.current) {
            const rect = event.currentTarget.getBoundingClientRect(),
              x = event.clientX - rect.left,
              y = event.clientY - rect.top;
            setMarquee({
              x: Math.min(x, box.current.x),
              y: Math.min(y, box.current.y),
              width: Math.abs(x - box.current.x),
              height: Math.abs(y - box.current.y),
            });
          }
        }}
        onPointerUp={() => {
          if (marquee) {
            const x1 = (marquee.x - viewport.x) / viewport.zoom,
              y1 = (marquee.y - viewport.y) / viewport.zoom,
              x2 = x1 + marquee.width / viewport.zoom,
              y2 = y1 + marquee.height / viewport.zoom;
            setSelected((ids) =>
              Array.from(
                new Set([
                  ...ids,
                  ...visible
                    .filter(
                      (n) =>
                        n.x + 260 >= x1 &&
                        n.x <= x2 &&
                        n.y + 58 >= y1 &&
                        n.y <= y2,
                    )
                    .map((n) => n.id),
                ]),
              ),
            );
          }
          pan.current = null;
          box.current = null;
          setMarquee(undefined);
        }}
      >
        <div
          className="image-canvas__world"
          style={{
            transform: `translate(${viewport.x}px,${viewport.y}px) scale(${viewport.zoom})`,
          }}
        >
          {visible.map((node) => (
            <article
              key={node.id}
              data-node-id={node.id}
              className={selected.includes(node.id) ? "is-selected" : ""}
              style={{ left: node.x, top: node.y, zIndex: node.z }}
              onPointerDown={(event) => {
                event.stopPropagation();
                const groupIds = node.groupId
                  ? nodes
                      .filter((item) => item.groupId === node.groupId)
                      .map((item) => item.id)
                  : [node.id];
                const ids = event.shiftKey
                  ? Array.from(new Set([...selected, ...groupIds]))
                  : selected.includes(node.id)
                    ? selected
                    : groupIds;
                setSelected(ids);
                drag.current = {
                  startX: event.clientX,
                  startY: event.clientY,
                  before: nodes,
                  ids,
                };
                event.currentTarget.setPointerCapture(event.pointerId);
              }}
              onPointerMove={(event) => {
                if (!drag.current) return;
                const dx =
                    (event.clientX - drag.current.startX) / viewport.zoom,
                  dy = (event.clientY - drag.current.startY) / viewport.zoom;
                onChange(
                  drag.current.before.map((item) =>
                    drag.current!.ids.includes(item.id) && !item.locked
                      ? {
                          ...item,
                          x: Math.round(item.x + dx),
                          y: Math.round(item.y + dy),
                        }
                      : item,
                  ),
                  false,
                );
              }}
              onPointerUp={() => {
                if (!drag.current) return;
                const before = drag.current.before,
                  after = nodes;
                onChange(before, false);
                onChange(after, true);
                drag.current = null;
              }}
            >
              <span>{node.role}</span>
              <strong>{node.uri}</strong>
              {node.locked && <Lock size={13} aria-label="已锁定" />}
            </article>
          ))}
        </div>
        {marquee && <div className="image-canvas__marquee" style={marquee} />}{" "}
        {!nodes.length && (
          <p className="image-canvas__empty">
            从下方添加参考图，或选择资产开始编排。
          </p>
        )}
      </div>
      <aside className="image-canvas__layers" aria-label="画布图层">
        <strong>图层</strong>
        {[...nodes]
          .sort((a, b) => b.z - a.z)
          .map((node) => (
            <div key={node.id}>
              <button
                type="button"
                className={selected.includes(node.id) ? "is-selected" : ""}
                onClick={() => setSelected([node.id])}
              >
                {node.role} · {node.uri}
              </button>
              <Button
                variant="ghost"
                aria-label={`${node.hidden ? "显示" : "隐藏"} ${node.uri}`}
                onClick={() =>
                  onChange((items) =>
                    items.map((item) =>
                      item.id === node.id
                        ? { ...item, hidden: !item.hidden }
                        : item,
                    ),
                  )
                }
              >
                {node.hidden ? <EyeOff size={14} /> : <Eye size={14} />}
              </Button>
            </div>
          ))}
      </aside>
    </section>
  );
}
