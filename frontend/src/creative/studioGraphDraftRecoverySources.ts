import type { StudioClient } from './studioClient';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord, StudioGraphScope } from './studioGraphTypes';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { PlanningDocument, PlanningSnapshot } from './studioProductionGraphContract';
import type { StudioTimelineSource } from './studioTimelineTypes';
import type { StoryboardReceipt } from './studioStoryboardContract';
import { inspectLocalSubgraphSource } from './graphLocalSubgraph';
import { GRAPH_LOCAL_SUBGRAPH_CONTRACT } from './studioGraphTypes';
import { productionGraphDefinitions } from './studioProductionGraphContract';
function fail(): never { throw new Error('缓存来源、版本或读取权限未能确认；草稿保留，未替换 pin 或恢复为当前图。'); }
const live = (current: () => boolean) => { if (!current()) throw new Error('草稿恢复上下文已改变，缓存保持。'); };
const pinMatches = (a: PlanningSnapshot, b?: PlanningSnapshot) => !!b && a.id === b.id && a.version === b.version && a.digest === b.digest;
export function recoveryScopeMatches(scope: StudioGraphScope, owner: StudioGraphDraftOwner) {
  return scope.novel_id === owner.projectId && scope.mode === owner.mode && (scope.mode === 'local' || scope.workspace_id === owner.workspaceId && scope.storyline_id === owner.storylineId && scope.branch_id === owner.branchId);
}
/** Original catalog reads only; this never enables a flag or obtains execution authority. */
export async function readBoundDraftCatalog(client: StudioClient, definition: StudioGraphDefinition, current: () => boolean): Promise<StudioGraphCatalog> {
  live(current); const schema = definition.schema_version, graphs = client.graphs;
  const production = schema === 4 && definition.nodes.some(n => productionGraphDefinitions.some(id => id === n.definition_id));
  const read = schema === 6 ? graphs.localSubgraphCatalog : schema === 5 ? graphs.videoCatalog : schema === 4 ? production ? graphs.productionCatalog : graphs.imageCatalog : schema === 3 ? graphs.catalog : undefined;
  if (typeof read !== 'function') fail(); const catalog = await read(); live(current); const c = catalog.capabilities;
  if (schema === 6 ? c.local_subgraph_contract !== GRAPH_LOCAL_SUBGRAPH_CONTRACT || c.local_subgraph_schema_version !== 6
    : c.media_execution !== true || c.media_execution_contract !== 'creative-graph-media/1'
      || schema === 4 && (c.image_graph !== true || c.image_graph_schema_version !== 4 || production && c.production_graph !== true)
      || schema === 5 && (c.video_graph !== true || c.video_graph_schema_version !== 5)) fail();
  if (definition.nodes.some(n => !catalog.definitions.some(d => d.id === n.definition_id))) fail();
  return catalog;
}
type AssetPin = { id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' };
/** Verify explicit cached pins through existing readonly owners twice. No operation,
 * model, preview, workflow, Save, approval or timeline edit is executed here. */
export async function verifyBoundDraftSources(client: StudioClient, definition: StudioGraphDefinition, catalog: StudioGraphCatalog, owner: StudioGraphDraftOwner, current: () => boolean, saved?: StudioGraphRecord): Promise<void> {
  const graphs = client.graphs;
  if (saved && (saved.project_id !== owner.projectId || !recoveryScopeMatches(saved.scope, owner) || [6, 7].includes(saved.definition.schema_version) && saved.definition.schema_version !== definition.schema_version)) fail();
  for (let pass = 0; pass < 2; pass++) {
    live(current); const assets = new Map<string, AssetPin>();
    const asset = (pin: AssetPin) => { const previous = assets.get(pin.id); if (previous && !pinMatches(pin, previous) || previous && previous.kind !== pin.kind) fail(); assets.set(pin.id, pin); };
    const timelineAsset = (source: StudioTimelineSource) => asset({ id: source.id, version: source.version, digest: source.digest, kind: source.asset_kind });
    const read = async <T,>(work: () => Promise<T>): Promise<T> => { live(current); const value = await work(); live(current); return value; };
    for (const n of definition.nodes) if (n.definition_id === 'asset_reference') asset({ id: n.parameters.asset_id!, version: n.parameters.version!, digest: n.parameters.digest!, kind: n.parameters.kind! });
    const plans = definition.nodes.filter(n => n.parameters.document_snapshot);
    let documents: PlanningDocument[] = [];
    if (plans.length) {
      if (typeof graphs.planningDocuments !== 'function') fail(); documents = (await read(() => graphs.planningDocuments!())).documents;
      for (const n of plans) { const p = n.parameters.document_snapshot!, actual = documents.find(d => d.id === p.id); if (!pinMatches(p, actual) || actual!.mode !== (n.definition_id === 'director_plan' ? 'DIRECTOR' : 'STORYBOARD')) fail(); }
    }
    const boards = new Map<string, StoryboardReceipt>();
    for (const n of plans.filter(n => n.definition_id === 'storyboard_plan')) {
      const p = n.parameters.document_snapshot!; if (boards.has(p.id)) continue;
      if (typeof graphs.videoStoryboard !== 'function') fail(); const board = await read(() => graphs.videoStoryboard!(p.id));
      if (!pinMatches(p, board.document_snapshot) || board.director_sources.some(p => !pinMatches(p, documents.find(d => d.id === p.id && d.mode === 'DIRECTOR')))) fail(); boards.set(p.id, board);
    }
    for (const n of definition.nodes.filter(n => n.definition_id === 'storyboard_shot' || n.definition_id === 'storyboard_prompt' && n.parameters.shot_id !== '')) {
      const edge = definition.edges.find(e => e.target_node_id === n.id && e.target_port === 'storyboard'), parent = definition.nodes.find(p => p.id === edge?.source_node_id && p.definition_id === 'storyboard_plan');
      const board = parent?.parameters.document_snapshot && boards.get(parent.parameters.document_snapshot.id), shot = board && board.shots.find(s => s.shot_id === n.parameters.shot_id);
      if (!shot || n.definition_id === 'storyboard_shot' && (shot.shot_version !== n.parameters.shot_version || shot.shot_digest !== n.parameters.shot_digest)) fail();
      // Only an I2V consumer references the shot image. Approval is never restored.
      const imageUsed = definition.edges.some(e => e.source_node_id === n.id && definition.nodes.some(v => v.id === e.target_node_id && v.definition_id === 'video_generate' && v.parameters.operation_id === 'm7.video.i2v'));
      if (imageUsed && shot.image_asset) asset({ id: shot.image_asset.asset_id, version: shot.image_asset.version, digest: shot.image_asset.digest, kind: 'image' });
    }
    for (const n of definition.nodes.filter(n => n.definition_id === 'timeline_export')) {
      const p = n.parameters.timeline_snapshot!; if (typeof graphs.graphTimelineGet !== 'function') fail(); const row = await read(() => graphs.graphTimelineGet!(p.id));
      if (!pinMatches(p, { id: row.id, version: row.version, digest: row.timeline_digest })) fail();
      // Conservative boundary: every snapshot reference, including one later removed
      // by an unapplied edit, must still be readable/current. We do not replay edits.
      for (const track of row.timeline.tracks) for (const clip of track.clips) timelineAsset(clip.source_snapshot);
      for (const op of n.parameters.edit_operations || []) {
        if (op.op === 'track.insert') for (const clip of op.track.clips) timelineAsset(clip.source_snapshot);
        else if (op.op === 'clip.insert') timelineAsset(op.clip.source_snapshot);
        else if (op.op === 'clip.update' && op.changes.source_snapshot) timelineAsset(op.changes.source_snapshot);
      }
    }
    for (const n of definition.nodes.filter(n => n.definition_id === 'local_subgraph')) {
      const p = n.parameters, child = await read(() => graphs.get(p.graph_id!));
      if (child.project_id !== owner.projectId || !recoveryScopeMatches(child.scope, owner) || child.id !== p.graph_id || child.version !== p.expected_version || child.definition_digest !== p.definition_digest || child.execution_digest !== p.execution_digest) fail();
      const checked = inspectLocalSubgraphSource(child, catalog);
      if (p.input_node_id !== checked.input || p.input_port !== 'text' || p.output_node_id !== checked.output || p.output_port !== 'draft' || definition.nodes.length + checked.childNodes > 24) fail();
      if (!saved) {
        const source = definition.nodes.find(s => s.definition_id === 'text_input'), review = definition.nodes.find(s => s.definition_id === 'human_review');
        if (definition.nodes.length !== 3 || definition.edges.length !== 2 || !source || !review || definition.nodes.some(s => !s.enabled)
          || !definition.edges.some(e => e.source_node_id === source.id && e.source_port === 'text' && e.target_node_id === n.id && e.target_port === 'text')
          || !definition.edges.some(e => e.source_node_id === n.id && e.source_port === 'draft' && e.target_node_id === review.id && e.target_port === 'draft')) fail();
      }
    }
    for (const p of assets.values()) {
      const value = await read(() => client.asset(p.id));
      if (value.novel_id !== owner.projectId || (value.branch_id ?? '') !== (owner.mode === 'collaboration' ? owner.branchId : '') || value.id !== p.id || value.deleted_at || value.version !== p.version || value.sha256 !== p.digest || value.kind !== p.kind) fail();
    }
  }
}
