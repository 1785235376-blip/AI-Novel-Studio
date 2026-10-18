import type { StudioClient } from './studioClient';
import { studioGraphDraftKey, type StudioGraphDraftOwner } from './studioGraphLocalDraft';
import { graphSelectionCopy } from './graphSelectionCopy';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';
export const PROJECT_GRAPH_TEMPLATE_BYTES = 16_000;
const contract = 'poemseed-project-graph-reference/1';
const ownerFields = ['projectId', 'incarnation', 'actorId', 'actorWorkspaceId', 'mode', 'workspaceId', 'storylineId', 'branchId'];
export type ProjectGraphTemplate = { contract: typeof contract; owner: StudioGraphDraftOwner; source: Pick<StudioGraphRecord, 'id' | 'version' | 'definition_digest' | 'execution_digest'>; selected: string[] };
function object(value: unknown, keys: string[]): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value) || Object.keys(value).some(key => !keys.includes(key))) throw new Error('引用模板格式不正确。'); return value as Record<string, unknown>; }
function ids(value: unknown): string[] { if (!Array.isArray(value) || !value.length || value.length > 24 || value.some(id => typeof id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)) || new Set(value).size !== value.length) throw new Error('引用模板节点选择无效。'); return [...value]; }
function checkSource(source: StudioGraphRecord, owner: StudioGraphDraftOwner, selected: string[]) {
  const scope = source.scope;
  if (source.project_id !== owner.projectId || scope.novel_id !== owner.projectId || scope.mode !== owner.mode || !source.can_edit
    || scope.mode === 'collaboration' && (scope.workspace_id !== owner.workspaceId || scope.storyline_id !== owner.storylineId || scope.branch_id !== owner.branchId)
    || scope.mode === 'local' && ['workspace_id', 'storyline_id', 'branch_id'].some(key => (scope as unknown as Record<string, unknown>)[key] != null)
    || selected.some(id => !source.definition.nodes.some(node => node.id === id))
    || source.reference_states.some(state => selected.includes(state.node_id) && state.state !== 'CURRENT')) throw new Error('原图当前来源或身份范围不可用于模板。');
}
export function createProjectGraphTemplate(source: StudioGraphRecord, selected: string[], owner: StudioGraphDraftOwner): string {
  const chosen = ids(selected); checkSource(source, owner, chosen);
  const value: ProjectGraphTemplate = { contract, owner: { ...owner }, source: { id: source.id, version: source.version, definition_digest: source.definition_digest, execution_digest: source.execution_digest }, selected: chosen };
  const raw = JSON.stringify(value); readProjectGraphTemplate(raw, owner); return raw;
}
export function readProjectGraphTemplate(raw: string, expected: StudioGraphDraftOwner): ProjectGraphTemplate {
  if (typeof raw !== 'string' || new TextEncoder().encode(raw).length > PROJECT_GRAPH_TEMPLATE_BYTES) throw new Error('引用模板超过大小限制。');
  const value = object(JSON.parse(raw), ['contract', 'owner', 'source', 'selected']), owner = object(value.owner, ownerFields), source = object(value.source, ['id', 'version', 'definition_digest', 'execution_digest']);
  if (value.contract !== contract || ownerFields.some(key => typeof owner[key] !== 'string') || studioGraphDraftKey(owner as StudioGraphDraftOwner) !== studioGraphDraftKey(expected)) throw new Error('引用模板不属于当前项目实例、身份或分支。');
  if (typeof source.id !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_.:-]{0,239}$/.test(source.id) || !Number.isSafeInteger(source.version) || (source.version as number) < 1
    || typeof source.definition_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.definition_digest) || typeof source.execution_digest !== 'string' || !/^[a-f0-9]{64}$/.test(source.execution_digest)) throw new Error('引用模板版本信息无效。');
  return { contract, owner: { ...expected }, source: source as ProjectGraphTemplate['source'], selected: ids(value.selected) };
}
export function planProjectGraphTemplate(template: ProjectGraphTemplate, source: StudioGraphRecord, target: StudioGraphDefinition, catalog: StudioGraphCatalog, owner: StudioGraphDraftOwner) {
  const checked = readProjectGraphTemplate(JSON.stringify(template), owner); checkSource(source, owner, checked.selected);
  if (source.id !== checked.source.id || source.version !== checked.source.version || source.definition_digest !== checked.source.definition_digest || source.execution_digest !== checked.source.execution_digest) throw new Error('原图版本已变化；不会用新内容替代模板引用。');
  return { sourceId: source.id, sourceVersion: source.version, result: graphSelectionCopy(source.definition, checked.selected, catalog, target) };
}

/** Re-read the original project generation around the original graph read. */
export async function readProjectTemplateSource(client: Pick<StudioClient, 'graphs' | 'overview'>, owner: StudioGraphDraftOwner, id: string, isCurrent: () => boolean) {
  const current = () => { if (!isCurrent()) throw new Error('项目或身份已变化。'); };
  async function generation() { current(); const overview = await client.overview(); current(); if (overview.project.id !== owner.projectId || overview.project.incarnation !== owner.incarnation) throw new Error('项目实例已变化。'); }
  await generation(); const source = await client.graphs.get(id); current(); await generation(); return source;
}
