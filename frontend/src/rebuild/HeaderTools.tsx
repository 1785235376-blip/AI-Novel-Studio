// [HERMIA-FE-20261022 REBUILD] Header slot for prototype-style tools (导出 / 资料 / 任务).
import { useStudio } from '../store';
import { ExportMenu } from './ExportMenu';

export function RebuildHeaderTools({ module }: { module: string }) {
  const novelId = useStudio(s => s.novelId);
  return <div className="rb-header-tools" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }} data-rebuild="header-tools">
    {module === 'NOVEL' ? <ExportMenu novelId={novelId} initialTab="novel" /> : null}
    {module === 'EDIT' || module === 'VIDEO' ? <ExportMenu novelId={novelId} initialTab="render" /> : null}
  </div>;
}
