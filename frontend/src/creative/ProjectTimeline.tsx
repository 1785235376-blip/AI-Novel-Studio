import type { KeyboardEvent } from 'react';
import { BookOpen, Clapperboard, Film, Layers, Video } from 'lucide-react';
import { Badge } from '../ui/primitives';
import { WORKSPACE_MODES, modeForDocument, type CreativeDocument, type WorkspaceMode } from './types';
const icons = [BookOpen, Clapperboard, Video, Layers, Film];
export function ProjectTimeline({ mode, onChange, documents, chapterCount, dirtyModes }: { mode: WorkspaceMode; onChange: (mode: WorkspaceMode) => void; documents: CreativeDocument[]; chapterCount: number; dirtyModes: WorkspaceMode[] }) {
  const move = (event: KeyboardEvent<HTMLButtonElement>, index: number) => {
    const delta = event.key === 'ArrowRight' ? 1 : event.key === 'ArrowLeft' ? -1 : 0;
    const next = event.key === 'Home' ? 0 : event.key === 'End' ? WORKSPACE_MODES.length - 1 : delta ? (index + delta + WORKSPACE_MODES.length) % WORKSPACE_MODES.length : -1;
    if (next < 0) return;
    event.preventDefault(); onChange(WORKSPACE_MODES[next].id);
    document.getElementById(`creative-stage-${WORKSPACE_MODES[next].id}`)?.focus();
  };
  return <nav className="creative-project-timeline" aria-label="项目创作阶段"><div className="creative-eyebrow">叙事制作 · V2 <Badge tone="warning">实验功能</Badge></div><div className="creative-stage-tabs" role="tablist" aria-label="创作模式">{WORKSPACE_MODES.map((item, index) => {
    const Icon = icons[index], count = item.id === 'NOVEL' ? chapterCount : documents.filter(row => modeForDocument(row.mode) === item.id).length;
    return <button type="button" id={`creative-stage-${item.id}`} key={item.id} role="tab" aria-controls={`creative-canvas-${item.id}`} aria-selected={mode === item.id} tabIndex={mode === item.id ? 0 : -1} onClick={() => onChange(item.id)} onKeyDown={event => move(event, index)}><Icon aria-hidden="true" /><span><strong>{item.label}</strong><small>{item.english} · {count}{dirtyModes.includes(item.id) ? ' · 未保存' : ''}</small></span></button>;
  })}</div></nav>;
}
