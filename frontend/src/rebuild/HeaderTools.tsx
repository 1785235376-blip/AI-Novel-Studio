// [HERMIA-FE-20261022 REBUILD] Header slot for prototype-style tools (导出 / 资料 / 任务).
import { useState } from 'react';
import { useStudio } from '../store';
import { ExportMenu } from './ExportMenu';
import { ResearchDrawer } from './ResearchDrawer';

export function RebuildHeaderTools({ module }: { module: string }) {
  const novelId = useStudio(s => s.novelId);
  const [research, setResearch] = useState(false);
  return <div className="rb-header-tools" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }} data-rebuild="header-tools">
    {module === 'NOVEL' ? <ExportMenu novelId={novelId} initialTab="novel" /> : null}
    {module === 'EDIT' || module === 'VIDEO' ? <ExportMenu novelId={novelId} initialTab="render" /> : null}
    {module === 'NOVEL' ? <button type="button" className="rb-trigger" aria-expanded={research} onClick={() => setResearch(v => !v)}>资料</button> : null}
    {research && module === 'NOVEL' ? <ResearchDrawer novelId={novelId} onClose={() => setResearch(false)} /> : null}
  </div>;
}
