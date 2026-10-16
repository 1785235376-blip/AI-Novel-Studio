import { useEffect, useId, useRef, useState } from 'react';
import type { PointerEvent } from 'react';
import { Button } from '../ui/primitives';
import type { StudioGraphCanvasNote, StudioGraphDefinition, StudioGraphPosition } from './studioGraphTypes';
import { clampGraphPosition, graphScreenToWorld } from './graphCanvasGeometry';
import { GRAPH_NOTE_HEIGHT, GRAPH_NOTE_WIDTH, withGraphNotes, visibleGraphNotes } from './graphCanvasNotes';

type Props = { definition: StudioGraphDefinition; blocked: boolean; owner?: string | number;
  selected: string | null; onSelect: (id: string | null) => void;
  onChange: (definition: StudioGraphDefinition, record?: boolean) => void };
export function GraphNoteEditor({ definition, blocked, owner, selected, onSelect, onChange }: Props) {
  const textId = useId();
  const notes = definition.presentation?.notes || [], note = notes.find(item => item.id === selected);
  const [error, setError] = useState(false);
  const [composition, setComposition] = useState<string | null>(null);
  const composing = useRef(false);
  const compositionSource = useRef<StudioGraphDefinition | null>(null);
  const editorEpoch = useRef(0);
  // A replacement during composition remounts the DOM input. Late native events
  // from the abandoned input cannot be routed into the newly selected owner/note.
  if (composing.current && compositionSource.current !== definition) {
    composing.current = false; compositionSource.current = null; editorEpoch.current++;
  }
  const live = useRef({ definition, owner, selected, blocked }); live.current = { definition, owner, selected, blocked };
  useEffect(() => { setError(false); setComposition(null); composing.current = false; }, [definition, blocked, owner, selected]);
  function apply(value: StudioGraphCanvasNote[]) {
    if (blocked || live.current.blocked || live.current.definition !== definition || live.current.owner !== owner || live.current.selected !== selected) return false;
    const next = withGraphNotes(definition, value);
    if (!next) { setError(true); return false; }
    setError(false); onChange(next, true); return true;
  }
  return <section className="graph-canvas__groups graph-canvas__annotation" aria-label="空间便笺" onKeyDown={event => event.stopPropagation()}>
    <Button type="button" disabled={blocked || notes.length >= 128} onClick={() => {
      if (blocked) return;
      let serial = 1; while (notes.some(item => item.id === `note_${serial}`)) serial++;
      const id = `note_${serial}`, point = graphScreenToWorld({ x: 32, y: 32 }, definition.viewport);
      if (apply([...notes, { id, text: '', position: { x: clampGraphPosition(point.x), y: clampGraphPosition(point.y) } }])) onSelect(id);
    }}>在视口左上添加便笺</Button>
    <label>空间便笺目录<select value={note?.id || ''} disabled={blocked} onChange={event => onSelect(event.target.value || null)}>
      <option value="">选择便笺</option>{notes.map(item => <option key={item.id} value={item.id}>{item.id} · {Array.from(item.text).slice(0, 24).join('') || '空便笺'}</option>)}
    </select></label>
    {note && <>
      <label htmlFor={textId}>便笺文本 {note.id}</label>
      <textarea key={JSON.stringify([owner, selected, blocked, editorEpoch.current])} id={textId} aria-label="便笺文本" rows={2} value={composing.current && compositionSource.current === definition ? composition ?? note.text : note.text} disabled={blocked}
        onCompositionStart={event => { if (!blocked) { composing.current = true; compositionSource.current = definition; setComposition(event.currentTarget.value); } }}
        onCompositionEnd={event => {
          if (!composing.current) return;
          composing.current = false; setComposition(null);
          if (event.currentTarget.value !== note.text) apply(notes.map(item => item.id === note.id ? { ...item, text: event.currentTarget.value } : item));
        }}
        onKeyDown={event => { if (event.key === 'Escape' && !event.nativeEvent.isComposing) { composing.current = false; setComposition(null); } }}
        onChange={event => {
          if (composing.current) { setComposition(event.target.value); return; }
          if (event.target.value !== note.text) apply(notes.map(item => item.id === note.id ? { ...item, text: event.target.value } : item));
        }} />
      {(['x', 'y'] as const).map(axis => <label key={axis}>便笺 {axis.toUpperCase()}<input aria-label={`便笺 ${axis.toUpperCase()}`} type="number" min={-100000} max={100000} value={note.position[axis]} disabled={blocked}
        onChange={event => { if (!event.target.value) return; const value = Number(event.target.value);
          apply(notes.map(item => item.id === note.id ? { ...item, position: { ...item.position, [axis]: value } } : item)); }} /></label>)}
      <Button type="button" variant="ghost" disabled={blocked} onClick={() => {
        if (apply(notes.filter(item => item.id !== note.id))) onSelect(null);
      }}>移除所选便笺</Button>
    </>}
    <p className="graph-canvas__help">{notes.length}/128 张空间便笺；每张 256 个 Unicode 字符，合计 12000 字符，整图仍受 96000 字节限制。新增位于视口左上 32 像素处，可能重叠，可拖动标题或编辑坐标。仅纯文本展示，无端口或模型输入；使用原图保存与撤销。小地图仅显示执行节点。</p>
    {error && <p role="alert" className="graph-canvas__help">便笺、坐标或整图容量超限，本次修改未应用，原图已保留。</p>}
  </section>;
}
export function GraphNoteCards({ definition, blocked, owner, selected, onSelect, onChange, size, panMode = false, displayViewport = definition.viewport }: Props & { displayViewport?: StudioGraphDefinition['viewport']; panMode?: boolean; size: { width: number; height: number } | null }) {
  const [moveError, setMoveError] = useState<string | null>(null);
  useEffect(() => { setMoveError(null); }, [definition, blocked, owner]);
  const [drag, setDrag] = useState<{ source: StudioGraphDefinition; owner: Props['owner']; id: string; pointer: number; start: StudioGraphPosition; position: StudioGraphPosition; target: HTMLButtonElement } | null>(null);
  const active = useRef(drag); active.current = drag;
  const current = useRef({ definition, blocked, owner }); current.current = { definition, blocked, owner };
  function cancel() { const old = active.current; active.current = null; setDrag(null);
    try { if (old?.target.hasPointerCapture?.(old.pointer)) old.target.releasePointerCapture(old.pointer); } catch { /* Already released. */ } }
  useEffect(() => { cancel(); }, [definition, blocked, owner]);
  useEffect(() => { window.addEventListener('blur', cancel); return () => { window.removeEventListener('blur', cancel); cancel(); }; }, []);
  const notes = definition.presentation?.notes || [];
  const valid = drag && drag.source === definition && drag.owner === owner && !blocked ? drag : null;
  const shown = visibleGraphNotes(notes, displayViewport, size, valid?.id || selected);
  function moved(event: PointerEvent<HTMLButtonElement>) {
    const value = active.current;
    if (!value || value.pointer !== event.pointerId || current.current.blocked || value.source !== current.current.definition || value.owner !== current.current.owner) return null;
    const note = notes.find(item => item.id === value.id)!;
    return { ...value, position: { x: clampGraphPosition(note.position.x + (event.clientX - value.start.x) / definition.viewport.zoom),
      y: clampGraphPosition(note.position.y + (event.clientY - value.start.y) / definition.viewport.zoom) } };
  }
  return <>{shown.map(note => <article key={note.id} data-graph-note-id={note.id} className={`graph-canvas__note${selected === note.id ? ' is-selected' : ''}`}
    style={{ left: valid?.id === note.id ? valid.position.x : note.position.x, top: valid?.id === note.id ? valid.position.y : note.position.y, width: GRAPH_NOTE_WIDTH, height: GRAPH_NOTE_HEIGHT }}
    onKeyDown={event => { event.stopPropagation(); if (event.key === 'Escape') cancel(); }} onPointerDown={event => {
      const header = event.target instanceof Element && event.target.closest('[data-graph-note-drag]');
      if (header && (panMode || event.altKey || event.button === 1)) return;
      event.stopPropagation();
    }}>
    <Button type="button" variant="ghost" data-graph-note-drag aria-label={`选择便笺 ${note.id}`} aria-pressed={selected === note.id}
      onFocus={() => onSelect(note.id)} onClick={event => { if (event.detail === 0 && !blocked) onSelect(note.id); }}
      onPointerDown={event => {
        if (panMode || event.button !== 0 || event.altKey) return;
        event.stopPropagation(); if (blocked) return;
        event.currentTarget.focus(); onSelect(note.id);
        const next = { source: definition, owner, id: note.id, pointer: event.pointerId, start: { x: event.clientX, y: event.clientY }, position: note.position, target: event.currentTarget };
        active.current = next; setDrag(next);
        try { event.currentTarget.setPointerCapture?.(event.pointerId); } catch { cancel(); }
      }}
      onPointerMove={event => { if (!active.current) return; event.stopPropagation(); const next = moved(event); if (next) { active.current = next; setDrag(next); } }}
      onPointerUp={event => {
        if (!active.current) return;
        event.stopPropagation(); const value = moved(event); cancel(); if (!value) return;
        if (value.position.x === note.position.x && value.position.y === note.position.y) return;
        const next = withGraphNotes(definition, notes.map(item => item.id === note.id ? { ...item, position: value.position } : item));
        if (next) onChange(next, true); else setMoveError(note.id);
      }} onPointerCancel={cancel} onLostPointerCapture={cancel}>{note.id} · 便笺</Button>
    {moveError === note.id && <p role="alert">移动将超过整图容量，原位置已保留。</p>}
    <p>{note.text || '空便笺：在上方编辑文本'}</p>
  </article>)}</>;
}
