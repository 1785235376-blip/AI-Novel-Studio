import { useMemo, useState } from 'react';
import { FlaskConical } from 'lucide-react';
import type { Chapter, CollaborationContext } from '../api';
import type { FeatureGroupDefinition } from '../ui/FeatureLauncher';
import { Badge, Button, EmptyState } from '../ui/primitives';
import { enabled, experimentalClient, type ExperimentalFlags } from './api';
import { PlanningPanel } from './PlanningPanel';
import { ImportPanel } from './ImportPanel';
import { WorldPanel } from './WorldPanel';
import { InboxPanel } from './InboxPanel';
import { TeamsPanel } from './TeamsPanel';
import { MediaPanel, RegistryPanel } from './MediaPanel';
import { EmbeddingPanel } from './EmbeddingPanel';
import { AudiobookPanel } from './AudiobookPanel';
import './experimental.css';

export const EXPERIMENTAL_GROUPS: readonly FeatureGroupDefinition[] = [{ id: 'experimental', label: 'Experimental', icon: <FlaskConical aria-hidden="true" />, items: [{ id: 'experimental', label: '实验工作台', icon: <FlaskConical aria-hidden="true" /> }] }];
export const EXPERIMENTAL_TABS = [
  ['advanced_planning_v2', '分层规划'], ['semantic_import_v2', '长篇导入'], ['world_character_engines_v2', '世界与人物'], ['unified_review_inbox', '统一审核'], ['agent_team_recipes', '创作团队'], ['media_adapter_registry', '媒体 Adapter'], ['cover_storyboard_generation', '封面与分镜'], ['visual_embeddings', '视觉 Embedding'], ['audiobook_v2', '有声书 V2'],
] as const;
export function ExperimentalWorkbench({ novelId, chapter, context, flags }: { novelId: string; chapter?: Chapter; context: CollaborationContext; flags?: ExperimentalFlags }) {
  const client = useMemo(() => experimentalClient(novelId, context), [novelId, context.sessionToken, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const [selected, setSelected] = useState('advanced_planning_v2');
  const tabs = EXPERIMENTAL_TABS.filter(([key]) => enabled(flags, key));
  const active = tabs.some(([key]) => key === selected) ? selected : tabs[0]?.[0];
  if (!tabs.length) return <EmptyState title="Experimental 未启用" detail="这些功能默认关闭，V1.0 验收模式保持关闭。" />;
  if (!novelId) return <EmptyState title="先选择作品" detail="实验记录仍受作品、分支和审核权限约束。" />;
  return <section className="experimental-workbench" aria-label="Experimental 工作台">
    <div className="experimental-actions"><h2>Experimental 工作台</h2><Badge tone="warning">默认关闭 · V1.1 预览</Badge></div>
    <nav className="experimental-tabs" aria-label="实验功能">{tabs.map(([key, label]) => <Button key={key} aria-pressed={active === key} onClick={() => setSelected(key)}>{label}</Button>)}</nav>
    {active === 'advanced_planning_v2' && <PlanningPanel client={client} chapter={chapter} />}
    {active === 'semantic_import_v2' && <ImportPanel client={client} chapter={chapter} />}
    {active === 'world_character_engines_v2' && <WorldPanel client={client} chapter={chapter} />}
    {active === 'unified_review_inbox' && <InboxPanel client={client} />}
    {active === 'agent_team_recipes' && <TeamsPanel client={client} chapter={chapter} />}
    {active === 'media_adapter_registry' && <RegistryPanel client={client} />}
    {active === 'cover_storyboard_generation' && <MediaPanel client={client} chapter={chapter} />}
    {active === 'visual_embeddings' && <EmbeddingPanel client={client} />}
    {active === 'audiobook_v2' && <AudiobookPanel client={client} chapter={chapter} />}
  </section>;
}
