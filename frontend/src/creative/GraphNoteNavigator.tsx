import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { Button } from '../ui/primitives';
import type { StudioGraphCanvasNote } from './studioGraphTypes';

export const GRAPH_NOTE_PAGE_SIZE = 20;
/** Display text directory only. Searching never edits a note, graph or execution. */
export function GraphNoteNavigator({ notes, owner, blocked, onSelect }: {
  notes: readonly StudioGraphCanvasNote[]; owner?: string | number; blocked: boolean; onSelect: (id: string) => void;
}) {
  const [query, setQuery] = useState(''), [active, setActive] = useState(0);
  const id = useId(), input = useRef<HTMLInputElement>(null);
  const matches = useMemo(() => {
    const words = query.trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
    return notes.filter(note => words.every(word => `${note.id} ${note.text}`.toLocaleLowerCase().includes(word)));
  }, [notes, query]);
  const index = Math.min(active, Math.max(0, matches.length - 1));
  const start = Math.floor(index / GRAPH_NOTE_PAGE_SIZE) * GRAPH_NOTE_PAGE_SIZE;
  const page = matches.slice(start, start + GRAPH_NOTE_PAGE_SIZE);
  useEffect(() => { setQuery(''); setActive(0); }, [owner]);
  useEffect(() => { setActive(0); }, [notes]);
  const choose = (noteId: string) => { if (!blocked) onSelect(noteId); };
  return <section aria-label="空间便笺搜索目录" onKeyDown={event => event.stopPropagation()}>
    <label htmlFor={`${id}-query`}>查找空间便笺</label>
    <input id={`${id}-query`} ref={input} role="combobox" aria-label="查找空间便笺" aria-expanded="true"
      aria-autocomplete="list" aria-controls={`${id}-results`} aria-activedescendant={matches.length ? `${id}-note-${index}` : undefined}
      maxLength={200} value={query} disabled={blocked} onChange={event => { setQuery(event.target.value); setActive(0); }}
      onKeyDown={event => {
        if (blocked || event.nativeEvent.isComposing || event.keyCode === 229 || event.altKey || event.ctrlKey || event.metaKey) return;
        if (event.key === 'Enter') { event.preventDefault(); if (matches[index]) choose(matches[index].id); }
        if (event.key === 'Escape') { event.preventDefault(); setQuery(''); setActive(0); }
        const step = event.key === 'ArrowDown' ? 1 : event.key === 'ArrowUp' ? -1
          : event.key === 'PageDown' ? GRAPH_NOTE_PAGE_SIZE : event.key === 'PageUp' ? -GRAPH_NOTE_PAGE_SIZE : 0;
        if (step) { event.preventDefault(); setActive(Math.max(0, Math.min(matches.length - 1, index + step))); }
      }} />
    <p role="status">共 {notes.length} 张便笺，匹配 {matches.length} 张；显示 {matches.length ? start + 1 : 0}–{start + page.length}。方向键选择，翻页键换页，Enter 确认。查找不修改画布。</p>
    <div role="listbox" id={`${id}-results`} aria-label="匹配的空间便笺" className="graph-canvas__navigation-results">
      {page.map((note, offset) => <Button key={note.id} id={`${id}-note-${start + offset}`} type="button" variant="ghost" role="option"
        aria-selected={index === start + offset} aria-posinset={start + offset + 1} aria-setsize={matches.length} disabled={blocked}
        onClick={() => choose(note.id)}>{note.id} · {Array.from(note.text).slice(0, 48).join('') || '空便笺'}</Button>)}
    </div>
    <Button type="button" disabled={blocked || !start} onClick={() => { setActive(Math.max(0, start - GRAPH_NOTE_PAGE_SIZE)); input.current?.focus(); }}>上一页便笺</Button>
    <Button type="button" disabled={blocked || start + page.length >= matches.length} onClick={() => { setActive(start + GRAPH_NOTE_PAGE_SIZE); input.current?.focus(); }}>下一页便笺</Button>
  </section>;
}
