import { useEffect, useId, useMemo, useRef, useState } from 'react';
import { FlaskConical } from 'lucide-react';
import type { Chapter, CollaborationContext } from '../api';
import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { enabled, experimentalClient, type ExperimentalFlags } from './api';
import { Field } from './shared';
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
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { InteractiveStoryPanel } from './InteractiveStoryPanel';
import { WriterRoomPanel } from './WriterRoomPanel';
import { ProjectForksPanel } from './ProjectForksPanel';
import { BranchManuscriptPanel } from './BranchManuscriptPanel';
import { OfflineSyncPanel } from './OfflineSyncPanel';
import { WritingSessionPanel } from './WritingSessionPanel';
import type { DraftStatus } from './readerPreflightClient';
import { RevisionIntelligencePanel, type RevisionGenerationOptions } from './RevisionIntelligencePanel';
import { WritingFocusPanel, type WritingFocusPreferences } from './WritingFocusPanel';
import type { WorkspaceAnchor, WorkspaceNavigation, WorkspaceView } from './uxClient';
import './experimental.css';

export { EXPERIMENTAL_GROUPS, EXPERIMENTAL_TABS } from './experimentalNavigation';
import { EXPERIMENTAL_TABS } from './experimentalNavigation';
export function ExperimentalWorkbench({ novelId, chapter, context, flags, onNavigate, currentAnchor, requestedTab, workspaceSection, focusActive, onFocusChange, onPreferencesChange, onReferencesChange, onUseCharacter, onExitCharacter, activeCharacterId, onOpenGeneration, onUseStyle, currentSelection, saved, onChapterSaved, revisionGeneration, localDraftState, saveFailure, workspaceView, onWorkspaceViewChange, onWorkspaceSaved, requestedTask }: { novelId: string; chapter?: Chapter; context: CollaborationContext; flags?: ExperimentalFlags; onNavigate?: (target: WorkspaceNavigation) => void; currentAnchor?: WorkspaceAnchor; requestedTab?: string; workspaceSection?: 'resume' | 'search' | 'tasks' | 'diagnostics' | 'guide'; focusActive?: boolean; onFocusChange?: (active: boolean) => void; onPreferencesChange?: (preferences: WritingFocusPreferences) => void; onReferencesChange?: () => void; onUseCharacter?: (characterId: string, chapterId: string, sceneId?: string) => void; onExitCharacter?: () => void; activeCharacterId?: string; onOpenGeneration?: (jobId: string, chapterId: string) => Promise<void>; onUseStyle?: (id: string) => void; currentSelection?: { from: number; to: number; text: string }; saved?: boolean; onChapterSaved?: (chapter: Chapter) => void; revisionGeneration?: RevisionGenerationOptions; localDraftState?: DraftStatus[]; saveFailure?: boolean; workspaceView?: WorkspaceView; onWorkspaceViewChange?: (view: WorkspaceView) => void; onWorkspaceSaved?: () => void; requestedTask?: { id: string; authority?: string; parent_id?: string } }) {
  const client = useMemo(() => experimentalClient(novelId, context), [novelId, context.sessionToken, context.scope?.workspaceId, context.scope?.projectId, context.scope?.storylineId, context.scope?.branchId, context.actor?.id]);
  const [selected, setSelected] = useState(requestedTab || 'advanced_planning_v2');
  const [toolQuery, setToolQuery] = useState('');
  const filterInput = useRef<HTMLInputElement>(null);
  const filterHintId = useId(), toolNavigationId = useId();
  useEffect(() => { if (requestedTab) { setSelected(requestedTab); setToolQuery(''); } }, [requestedTab]);
  const tabs = EXPERIMENTAL_TABS.filter(([key]) => enabled(flags, key));
  const queryTerms = toolQuery.normalize('NFKC').trim().toLowerCase().split(/\s+/).filter(Boolean);
  const visibleTabs = tabs.filter(([key, label]) => queryTerms.every(term => `${label} experimental.${key}`.normalize('NFKC').toLowerCase().includes(term)));
  // Filter navigation only. Keep the active panel and its draft state mounted.
  const active = tabs.some(([key]) => key === selected) ? selected : tabs[0]?.[0];
  const activeLabel = tabs.find(([key]) => key === active)?.[1];
  if (!tabs.length) return <EmptyState title="Experimental 未启用" detail="这些功能默认关闭，V1.0 验收模式保持关闭。" />;
  if (!novelId) return <EmptyState title="先选择作品" detail="实验记录仍受作品、分支和审核权限约束。" />;
  return <section className="experimental-workbench" aria-label="Experimental 工作台">
    <div className="experimental-actions"><h2>Experimental 工作台</h2><Badge tone="warning">默认关闭 · V1.1 预览</Badge></div>
    <div className="experimental-actions">
      <Field label="查找已启用工具"><input ref={filterInput} type="search" value={toolQuery} autoComplete="off" placeholder="工具名称或标识" aria-describedby={filterHintId} aria-controls={toolNavigationId} onChange={event => setToolQuery(event.target.value)} /></Field>
      <Button type="button" disabled={!toolQuery} onClick={() => { setToolQuery(''); filterInput.current?.focus(); }}>清除筛选</Button>
      <small id={filterHintId}>仅筛选下方入口；当前工具：{activeLabel}。</small>
    </div>
    {!!queryTerms.length && <StatusMessage>{visibleTabs.length ? `找到 ${visibleTabs.length} / ${tabs.length} 个已启用工具。` : '没有匹配的已启用工具。请更换关键词或清除筛选。'}</StatusMessage>}
    <nav id={toolNavigationId} className="experimental-tabs" aria-label="实验功能">{visibleTabs.map(([key, label]) => <Button key={key} type="button" aria-pressed={active === key} onClick={() => { setSelected(key); setToolQuery(''); }}>{label}</Button>)}</nav>
    {active === 'temporal_story_graph_v2' && <StoryGraphPanel client={client} chapter={chapter} requestedRecordId={requestedTask?.authority === 'graph_record' ? requestedTask.id : undefined} mindEnabled={enabled(flags, 'character_mind_v2')} onNavigate={onNavigate} onUseCharacter={onUseCharacter} onExitCharacter={onExitCharacter} activeCharacterId={activeCharacterId} />}
    {active === 'model_broker_v2' && <ModelBrokerPanel client={client} novelId={novelId} context={context} chapter={chapter} benchmarkEnabled={enabled(flags, 'model_benchmark_v2')} onOpenGeneration={onOpenGeneration} />}
    {active === 'asset_lineage_v2' && <ProductionLineagePanel client={client} manifestsEnabled={enabled(flags, 'production_manifest_v2')} onNavigate={onNavigate} />}
    {active === 'style_dna_v2' && <StyleAnalysisPanel client={client} chapter={chapter} requestedJobId={requestedTask?.authority === 'style_model_job' ? requestedTask.id : undefined} onNavigate={onNavigate} onUseStyle={onUseStyle} />}
    {active === 'narrative_quality_judge_v2' && <NarrativeJudgePanel client={client} requestedJobId={requestedTask?.authority === 'judge_model_job' ? requestedTask.id : undefined} chapter={chapter} onNavigate={onNavigate} />}
    {active === 'change_impact_v2' && <ChangeImpactPanel client={client} onNavigate={onNavigate} />}
    {active === 'story_simulator_v2' && <StorySimulatorPanel client={client} requestedJobId={requestedTask?.authority === 'simulator_model_job' ? requestedTask.id : undefined} chapter={chapter} onNavigate={onNavigate} />}
    {active === 'research_library_v2' && <ResearchLibraryPanel client={client} />}
    {active === 'reader_preflight_v2' && <ReaderPreflightPanel client={client} localDraftState={localDraftState} onNavigate={onNavigate} />}
    {active === 'writing_sessions_v2' && <WritingSessionPanel client={client} onNavigate={onNavigate} />}
    {active === 'branch_manuscript_v1' && <BranchManuscriptPanel client={client} onNavigate={onNavigate} />}
    {active === 'project_forks_v2' && <ProjectForksPanel client={client} />}
    {active === 'offline_sync_v2' && <OfflineSyncPanel client={client} />}
    {active === 'writer_room_v2' && <WriterRoomPanel client={client} onNavigate={onNavigate} />}
    {active === 'comic_layouts_v2' && <ComicLayoutsPanel client={client} />}
    {active === 'interactive_story_v2' && <InteractiveStoryPanel client={client} />}
    {active === 'template_library_v2' && <TemplateLibraryPanel client={client} onNavigate={onNavigate} />}
    {active === 'declarative_agents_v2' && <DeclarativeAgentsPanel client={client} requestedJobId={requestedTask?.authority === 'declarative_model_job' ? requestedTask.id : undefined} />}
    {active === 'multilingual_editions_v2' && <MultilingualEditionsPanel client={client} requestedJobId={requestedTask?.authority === 'translation_model_job' ? requestedTask.id : undefined} />}
    {active === 'portable_projects_v2' && <PortableProjectsPanel client={client} />}
    {active === 'safe_batches_v2' && <SafeBatchesPanel client={client} />}
    {active === 'ai_director_v2' && <DirectorPanel client={client} />}
    {active === 'timeline_exchange_v2' && <TimelineExchangePanel client={client} />}
    {active === 'revision_intelligence_v2' && <RevisionIntelligencePanel client={client} chapter={chapter} requestedJobId={requestedTask?.authority === 'revision_model_job' ? requestedTask.id : undefined} selection={currentSelection} saved={saved} onChapterSaved={onChapterSaved} generation={revisionGeneration} onHistory={() => onNavigate?.({ kind: 'feature', id: 'history', feature: 'history' })} />}
    {active === 'writing_focus_v2' && <WritingFocusPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} focusActive={focusActive} onFocusChange={onFocusChange} onPreferencesChange={onPreferencesChange} onReferencesChange={onReferencesChange} />}
    {active === 'local_ai_workflow_inspector_v2' && <WorkflowInspectionPanel client={client} />}
    {active === 'workspace_tools_v2' && <WorkspaceToolsPanel client={client} chapter={chapter} flags={flags} onNavigate={onNavigate} currentAnchor={currentAnchor} initialSection={workspaceSection} focusActive={focusActive} saveFailure={saveFailure} workspaceView={workspaceView} onWorkspaceViewChange={onWorkspaceViewChange} onWorkspaceSaved={onWorkspaceSaved} />}
    {active === 'advanced_planning_v2' && <PlanningPanel client={client} chapter={chapter} />}
    {active === 'semantic_import_v2' && <ImportPanel client={client} chapter={chapter} requestedTaskId={requestedTask?.authority === 'semantic_import' ? requestedTask.id : undefined} />}
    {active === 'world_character_engines_v2' && <WorldPanel client={client} chapter={chapter} requestedRecordId={requestedTask?.authority === 'world_record' ? requestedTask.id : undefined} />}
    {active === 'unified_review_inbox' && <InboxPanel client={client} requestedItemId={requestedTask?.authority === 'review_inbox' ? requestedTask.id : undefined} requestedDomain={requestedTask?.authority === 'review_inbox' ? requestedTask.parent_id : undefined} />}
    {active === 'agent_team_recipes' && <TeamsPanel client={client} chapter={chapter} requestedTaskId={requestedTask?.authority === 'agent_team' ? requestedTask.id : undefined} />}
    {active === 'media_adapter_registry' && <RegistryPanel client={client} />}
    {active === 'cover_storyboard_generation' && <MediaPanel client={client} chapter={chapter} requestedTaskId={requestedTask?.authority === 'media' ? requestedTask.id : undefined} />}
    {active === 'visual_embeddings' && <EmbeddingPanel client={client} />}
    {active === 'voice_direction_v2' && <VoiceDirectionPanel client={client} requestedTaskId={requestedTask?.authority === 'voice_direction' ? requestedTask.id : undefined} onOpenAudiobook={() => setSelected('audiobook_v2')} />}
    {active === 'subtitle_timeline_v2' && <SubtitleTimelinePanel client={client} onOpenAudiobook={() => setSelected('audiobook_v2')} />}
    {active === 'audiobook_v2' && <AudiobookPanel client={client} chapter={chapter} requestedPlanId={requestedTask?.authority === 'audiobook' ? requestedTask.id : undefined} />}
  </section>;
}
