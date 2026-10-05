import { useEffect, useMemo, useState } from 'react';
import { FlaskConical } from 'lucide-react';
import type { Chapter, CollaborationContext } from '../api';
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
import { VoiceDirectionPanel } from './VoiceDirectionPanel';
import { SubtitleTimelinePanel } from './SubtitleTimelinePanel';
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
import { ReaderPreflightPanel } from './ReaderPreflightPanel';
import { DirectorPanel } from './DirectorPanel';
import { TimelineExchangePanel } from './TimelineExchangePanel';
import { PortableProjectsPanel } from './PortableProjectsPanel';
import { SafeBatchesPanel } from './SafeBatchesPanel';
import { MultilingualEditionsPanel } from './MultilingualEditionsPanel';
import { TemplateLibraryPanel } from './TemplateLibraryPanel';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import { WritingSessionPanel } from './WritingSessionPanel';
import type { DraftStatus } from './readerPreflightClient';
import { RevisionIntelligencePanel, type RevisionGenerationOptions } from './RevisionIntelligencePanel';
import { WritingFocusPanel, type WritingFocusPreferences } from './WritingFocusPanel';
import type { WorkspaceAnchor, WorkspaceNavigation } from './uxClient';
import './experimental.css';

export { EXPERIMENTAL_GROUPS, EXPERIMENTAL_TABS } from './experimentalNavigation';
import { EXPERIMENTAL_TABS } from './experimentalNavigation';
export function ExperimentalWorkbench({ novelId, chapter, context, flags, onNavigate, currentAnchor, requestedTab, workspaceSection, focusActive, onFocusChange, onPreferencesChange, onReferencesChange, onUseCharacter, onExitCharacter, activeCharacterId, onOpenGeneration, onUseStyle, currentSelection, saved, onChapterSaved, revisionGeneration, localDraftState, saveFailure }: { novelId: string; chapter?: Chapter; context: CollaborationContext; flags?: ExperimentalFlags; onNavigate?: (target: WorkspaceNavigation) => void; currentAnchor?: WorkspaceAnchor; requestedTab?: string; workspaceSection?: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; focusActive?: boolean; onFocusChange?: (active: boolean) => void; onPreferencesChange?: (preferences: WritingFocusPreferences) => void; onReferencesChange?: () => void; onUseCharacter?: (characterId: string, chapterId: string) => void; onExitCharacter?: () => void; activeCharacterId?: string; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void>; onUseStyle?: (id: string) => void; currentSelection?: { from: number; to: number; text: string }; saved?: boolean; onChapterSaved?: (chapter: Chapter) => void; revisionGeneration?: RevisionGenerationOptions; localDraftState?: DraftStatus[]; saveFailure?: boolean }) {
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
    {active === 'reader_preflight_v2' && <ReaderPreflightPanel client={client} localDraftState={localDraftState} onNavigate={onNavigate} />}
    {active === 'writing_sessions_v2' && <WritingSessionPanel client={client} onNavigate={onNavigate} />}
    {active === 'template_library_v2' && <TemplateLibraryPanel client={client} onNavigate={onNavigate} />}
    {active === 'declarative_agents_v2' && <DeclarativeAgentsPanel client={client} />}
    {active === 'multilingual_editions_v2' && <MultilingualEditionsPanel client={client} />}
    {active === 'portable_projects_v2' && <PortableProjectsPanel client={client} />}
    {active === 'safe_batches_v2' && <SafeBatchesPanel client={client} />}
    {active === 'ai_director_v2' && <DirectorPanel client={client} />}
    {active === 'timeline_exchange_v2' && <TimelineExchangePanel client={client} />}
    {active === 'revision_intelligence_v2' && <RevisionIntelligencePanel client={client} chapter={chapter} selection={currentSelection} saved={saved} onChapterSaved={onChapterSaved} generation={revisionGeneration} onHistory={() => onNavigate?.({ kind: 'feature', id: 'history', feature: 'history' })} />}
    {active === 'writing_focus_v2' && <WritingFocusPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} focusActive={focusActive} onFocusChange={onFocusChange} onPreferencesChange={onPreferencesChange} onReferencesChange={onReferencesChange} />}
    {active === 'local_ai_workflow_inspector_v2' && <WorkflowInspectionPanel client={client} />}
    {active === 'workspace_tools_v2' && <WorkspaceToolsPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} currentAnchor={currentAnchor} initialSection={workspaceSection} focusActive={focusActive} saveFailure={saveFailure} />}
    {active === 'advanced_planning_v2' && <PlanningPanel client={client} chapter={chapter} />}
    {active === 'semantic_import_v2' && <ImportPanel client={client} chapter={chapter} />}
    {active === 'world_character_engines_v2' && <WorldPanel client={client} chapter={chapter} />}
    {active === 'unified_review_inbox' && <InboxPanel client={client} />}
    {active === 'agent_team_recipes' && <TeamsPanel client={client} chapter={chapter} />}
    {active === 'media_adapter_registry' && <RegistryPanel client={client} />}
    {active === 'cover_storyboard_generation' && <MediaPanel client={client} chapter={chapter} />}
    {active === 'visual_embeddings' && <EmbeddingPanel client={client} />}
    {active === 'voice_direction_v2' && <VoiceDirectionPanel client={client} onOpenAudiobook={() => setSelected('audiobook_v2')} />}
    {active === 'subtitle_timeline_v2' && <SubtitleTimelinePanel client={client} onOpenAudiobook={() => setSelected('audiobook_v2')} />}
    {active === 'audiobook_v2' && <AudiobookPanel client={client} chapter={chapter} />}
  </section>;
}
