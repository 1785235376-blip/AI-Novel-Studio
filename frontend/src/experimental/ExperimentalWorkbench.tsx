import { useEffect, useMemo, useState } from 'react';
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
import { WorkspaceToolsPanel } from './WorkspaceToolsPanel';
import { WorkflowInspectionPanel } from './WorkflowInspectionPanel';
import { StoryGraphPanel } from './StoryGraphPanel';
import { ModelBrokerPanel } from './ModelBrokerPanel';
import { ProductionLineagePanel } from './ProductionLineagePanel';
import { StyleAnalysisPanel } from './StyleAnalysisPanel';
import { NarrativeJudgePanel } from './NarrativeJudgePanel';
import { ChangeImpactPanel } from './ChangeImpactPanel';
import { StorySimulatorPanel } from './StorySimulatorPanel';
import { ResearchLibraryPanel } from './ResearchLibraryPanel';
import { RevisionIntelligencePanel, type RevisionGenerationOptions } from './RevisionIntelligencePanel';
import { WritingFocusPanel, type WritingFocusPreferences } from './WritingFocusPanel';
import type { WorkspaceAnchor, WorkspaceNavigation } from './uxClient';
import './experimental.css';

export const EXPERIMENTAL_GROUPS: readonly FeatureGroupDefinition[] = [{ id: 'experimental', label: 'Experimental', icon: <FlaskConical aria-hidden="true" />, items: [{ id: 'experimental', label: '实验工作台', icon: <FlaskConical aria-hidden="true" /> }] }];
export const EXPERIMENTAL_TABS = [
  ['workspace_tools_v2', '工作现场'], ['local_ai_workflow_inspector_v2', '工作流检查'], ['writing_focus_v2', '专注与灵感'], ['temporal_story_graph_v2', '故事图谱'],
  ['model_broker_v2', '模型路由与评测'], ['asset_lineage_v2', '资产来源与复现'], ['style_dna_v2', '风格档案'], ['narrative_quality_judge_v2', '作品审稿'], ['change_impact_v2', '修改影响与更新'], ['story_simulator_v2', '剧情推演'], ['research_library_v2', '创作资料库'], ['revision_intelligence_v2', '选区修订与保护'],
  ['advanced_planning_v2', '分层规划'], ['semantic_import_v2', '长篇导入'], ['world_character_engines_v2', '世界与人物'], ['unified_review_inbox', '统一审核'], ['agent_team_recipes', '创作团队'], ['media_adapter_registry', '媒体 Adapter'], ['cover_storyboard_generation', '封面与分镜'], ['visual_embeddings', '视觉 Embedding'], ['audiobook_v2', '有声书 V2'],
] as const;
export function ExperimentalWorkbench({ novelId, chapter, context, flags, onNavigate, currentAnchor, requestedTab, workspaceSection, focusActive, onFocusChange, onPreferencesChange, onReferencesChange, onUseCharacter, onExitCharacter, activeCharacterId, onOpenGeneration, onUseStyle, currentSelection, saved, onChapterSaved, revisionGeneration }: { novelId: string; chapter?: Chapter; context: CollaborationContext; flags?: ExperimentalFlags; onNavigate?: (target: WorkspaceNavigation) => void; currentAnchor?: WorkspaceAnchor; requestedTab?: string; workspaceSection?: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; focusActive?: boolean; onFocusChange?: (active: boolean) => void; onPreferencesChange?: (preferences: WritingFocusPreferences) => void; onReferencesChange?: () => void; onUseCharacter?: (characterId: string, chapterId: string) => void; onExitCharacter?: () => void; activeCharacterId?: string; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void>; onUseStyle?: (id: string) => void; currentSelection?: { from: number; to: number; text: string }; saved?: boolean; onChapterSaved?: (chapter: Chapter) => void; revisionGeneration?: RevisionGenerationOptions }) {
  const client = useMemo(() => experimentalClient(novelId, context), [novelId, context.sessionToken, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId]);
  const [selected, setSelected] = useState(requestedTab || 'advanced_planning_v2');
  useEffect(() => { if (requestedTab) setSelected(requestedTab); }, [requestedTab]);
  const tabs = EXPERIMENTAL_TABS.filter(([key]) => enabled(flags, key));
  const active = tabs.some(([key]) => key === selected) ? selected : tabs[0]?.[0];
  if (!tabs.length) return <EmptyState title="Experimental 未启用" detail="这些功能默认关闭，V1.0 验收模式保持关闭。" />;
  if (!novelId) return <EmptyState title="先选择作品" detail="实验记录仍受作品、分支和审核权限约束。" />;
  return <section className="experimental-workbench" aria-label="Experimental 工作台">
    <div className="experimental-actions"><h2>Experimental 工作台</h2><Badge tone="warning">默认关闭 · V1.1 预览</Badge></div>
    <nav className="experimental-tabs" aria-label="实验功能">{tabs.map(([key, label]) => <Button key={key} aria-pressed={active === key} onClick={() => setSelected(key)}>{label}</Button>)}</nav>
    {active === 'temporal_story_graph_v2' && <StoryGraphPanel client={client} chapter={chapter} mindEnabled={enabled(flags, 'character_mind_v2')} onNavigate={onNavigate} onUseCharacter={onUseCharacter} onExitCharacter={onExitCharacter} activeCharacterId={activeCharacterId} />}
    {active === 'model_broker_v2' && <ModelBrokerPanel client={client} novelId={novelId} context={context} chapter={chapter} benchmarkEnabled={enabled(flags, 'model_benchmark_v2')} onOpenGeneration={onOpenGeneration} />}
    {active === 'asset_lineage_v2' && <ProductionLineagePanel client={client} manifestsEnabled={enabled(flags, 'production_manifest_v2')} onNavigate={onNavigate} />}
    {active === 'style_dna_v2' && <StyleAnalysisPanel client={client} chapter={chapter} onNavigate={onNavigate} onUseStyle={onUseStyle} />}
    {active === 'narrative_quality_judge_v2' && <NarrativeJudgePanel client={client} chapter={chapter} onNavigate={onNavigate} />}
    {active === 'change_impact_v2' && <ChangeImpactPanel client={client} onNavigate={onNavigate} />}
    {active === 'story_simulator_v2' && <StorySimulatorPanel client={client} chapter={chapter} onNavigate={onNavigate} />}
    {active === 'research_library_v2' && <ResearchLibraryPanel client={client} />}
    {active === 'revision_intelligence_v2' && <RevisionIntelligencePanel client={client} chapter={chapter} selection={currentSelection} saved={saved} onChapterSaved={onChapterSaved} generation={revisionGeneration} onHistory={() => onNavigate?.({ kind: 'feature', id: 'history', feature: 'history' })} />}
    {active === 'writing_focus_v2' && <WritingFocusPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} focusActive={focusActive} onFocusChange={onFocusChange} onPreferencesChange={onPreferencesChange} onReferencesChange={onReferencesChange} />}
    {active === 'local_ai_workflow_inspector_v2' && <WorkflowInspectionPanel client={client} />}
    {active === 'workspace_tools_v2' && <WorkspaceToolsPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} currentAnchor={currentAnchor} initialSection={workspaceSection} />}
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
