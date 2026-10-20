import type { CollaborationContext } from '../api';
import { checkedStudioGraphDraft } from './studioGraphClient';
import type { StudioGraphDefinition, StudioGraphRecord } from './studioGraphTypes';

/** A browser recovery hint; no token, capability, review receipt or execution state. */
export type StudioGraphDraftOwner = {
  projectId: string; incarnation: string; actorId: string; actorWorkspaceId: string;
  mode: 'local' | 'collaboration'; workspaceId: string; storylineId: string; branchId: string;
};
export type StudioGraphLocalDraft = {
  schema_version: 1; owner: StudioGraphDraftOwner; saved_at: string; request_id: string;
  base: Pick<StudioGraphRecord, 'id' | 'version' | 'definition_digest' | 'execution_digest'> | null;
  definition: StudioGraphDefinition; uncertain: boolean;
};
const safeId = (value: unknown): value is string => typeof value === 'string' && value.length > 0 && value.length <= 240 && !/[\u0000-\u001f\u007f]/.test(value);
export const graphDraftIncarnation = (value: unknown): value is string => safeId(value) && /^(file|postgres):[A-Za-z0-9._-]+$/.test(value);

/** Public IDs alone cannot distinguish a deleted project from its replacement. */
export function studioGraphDraftOwner(projectId: string, incarnation: unknown, context: CollaborationContext,
  host: { token: string; actorId: string }): StudioGraphDraftOwner | undefined {
  if (!safeId(projectId) || !graphDraftIncarnation(incarnation)) return;
  if (context.sessionToken || context.actor || context.scope) {
    const { actor, scope } = context;
    if (!context.sessionToken || !actor || !scope || !safeId(actor.id) || !safeId(actor.workspaceId)
      || scope.projectId !== projectId || scope.workspaceId !== actor.workspaceId
      || ![scope.workspaceId, scope.storylineId, scope.branchId].every(safeId)) return;
    return { projectId, incarnation, actorId: actor.id, actorWorkspaceId: actor.workspaceId,
      mode: 'collaboration', workspaceId: scope.workspaceId, storylineId: scope.storylineId, branchId: scope.branchId };
  }
  if (!host.token || !safeId(host.actorId)) return;
  return { projectId, incarnation, actorId: host.actorId, actorWorkspaceId: '', mode: 'local', workspaceId: '', storylineId: '', branchId: '' };
}
export const studioGraphDraftKey = (owner: StudioGraphDraftOwner) => `studio-graph-draft:v1:${JSON.stringify([
  owner.actorId, owner.actorWorkspaceId, owner.projectId, owner.incarnation, owner.mode, owner.workspaceId, owner.storylineId, owner.branchId,
])}`;

/** Recovery contains authoring only: legacy text graphs and the existing closed local condition graph. */
export function checkedLocalGraphDefinition(value: unknown): StudioGraphDefinition {
  const definition = checkedStudioGraphDraft(value);
  if (definition.schema_version > 2 && definition.schema_version !== 7 || definition.nodes.some(node => node.definition_id === 'asset_reference')) throw new Error('GRAPH_DRAFT_TEXT_ONLY');
  return definition;
}
export function graphDraftRecoverable(value: StudioGraphDefinition): boolean {
  try { checkedLocalGraphDefinition(value); return true; } catch { return false; }
}
export function readStudioGraphLocalDraft(raw: string, owner: StudioGraphDraftOwner): StudioGraphLocalDraft {
  if (raw.length > 110_000) throw new Error('GRAPH_DRAFT_TOO_LARGE');
  const value = JSON.parse(raw) as StudioGraphLocalDraft;
  if (!value || value.schema_version !== 1 || !value.owner || studioGraphDraftKey(value.owner) !== studioGraphDraftKey(owner)
    || !safeId(value.request_id) || !/^graph_[a-f0-9]{32}$/.test(value.request_id)
    || typeof value.uncertain !== 'boolean' || typeof value.saved_at !== 'string' || !Number.isFinite(Date.parse(value.saved_at))) throw new Error('GRAPH_DRAFT_INVALID');
  const base = value.base;
  if (base !== null && (!base || !safeId(base.id) || !Number.isSafeInteger(base.version) || base.version < 1
    || !/^[a-f0-9]{64}$/.test(base.definition_digest) || !/^[a-f0-9]{64}$/.test(base.execution_digest))) throw new Error('GRAPH_DRAFT_BASE_INVALID');
  return { schema_version: 1, owner: { ...owner }, saved_at: value.saved_at, request_id: value.request_id,
    base: base === null ? null : { id: base.id, version: base.version, definition_digest: base.definition_digest, execution_digest: base.execution_digest },
    definition: checkedLocalGraphDefinition(value.definition), uncertain: value.uncertain };
}
export const graphDraftBaselineMatches = (draft: StudioGraphLocalDraft, record: StudioGraphRecord) => !!draft.base
  && record.can_edit && draft.base.id === record.id && draft.base.version === record.version
  && draft.base.definition_digest === record.definition_digest && draft.base.execution_digest === record.execution_digest;
