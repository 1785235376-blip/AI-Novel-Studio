// [HERMIA-FE-20261022 REBUILD] Header slot for prototype-style tools (导出 / 资料 / 任务).
import { useState } from 'react';
import { useStudio } from '../store';
import { ExportMenu } from './ExportMenu';
import { ResearchDrawer } from './ResearchDrawer';
import { TasksMenu } from './TasksMenu';
import { Popover } from './primitives';
import { CredentialsPanel } from './CredentialsPanel';
import { useT } from '../i18n'; // [HERMIA-FE-20261025 I18N P0]

export function RebuildHeaderTools({ module, activeTaskCount }: { module: string; activeTaskCount?: number }) {
  const t = useT();
  const novelId = useStudio(s => s.novelId);
  const [research, setResearch] = useState(false);
  return <div className="rb-header-tools" style={{ display: 'inline-flex', gap: 6, alignItems: 'center' }} data-rebuild="header-tools">
    {/* [HERMIA-FE-20261022 R1] 小说的导出 / 资料不再占顶栏按钮，改由左栏「小说面板」进入；顶栏补原型「能力状态」 */}
    <Popover label={t('header.capability')} testId="rb-capability">{() => <CredentialsPanel />}</Popover>
    {module === 'EDIT' || module === 'VIDEO' ? <ExportMenu novelId={novelId} initialTab="render" /> : null}
    <TasksMenu novelId={novelId} count={activeTaskCount} />
    {research && module === 'NOVEL' ? <ResearchDrawer novelId={novelId} onClose={() => setResearch(false)} /> : null}
  </div>;
}
