import { removeCanvasCard } from '../mediaCanvasGroups';
import { alignCanvasCards } from '../mediaCanvasSelection';
import { graphDraftIncarnation, type StudioGraphDraftOwner } from '../studioGraphLocalDraft';
import { checkedCanvasDefinition, type CanvasCard, type CanvasDefinition, type CanvasReferenceState, type CanvasViewRecord } from '../studioCanvasViewClient';
import type { StudioGraphScope } from '../studioGraphTypes';

export type CanvasBulkOperation = 'REMOVE_CARDS' | 'ALIGN_LEFT' | 'ALIGN_TOP';
export type CanvasBulkActionInput = {
  definition: CanvasDefinition; base?: CanvasViewRecord; selectedIds: string[];
  operation: CanvasBulkOperation; owner?: StudioGraphDraftOwner; current: boolean;
};
export type CanvasBulkActionItem = {
  cardId: string; before: CanvasCard; after?: CanvasCard; changed: boolean;
  beforeGroupId: string | null; afterGroupId: string | null;
  referenceState: CanvasReferenceState['state'] | 'UNVERIFIED'; filename?: string;
};
export type CanvasBulkActionPlan = {
  state: 'ready' | 'stale' | 'invalid' | 'missing'; message: string; binding: string | null;
  operation: CanvasBulkOperation | null; items: CanvasBulkActionItem[]; definition?: CanvasDefinition; notes: string[];
};
export const CANVAS_BULK_SELECTION_LIMIT = 24;
const operations: CanvasBulkOperation[] = ['REMOVE_CARDS', 'ALIGN_LEFT', 'ALIGN_TOP'];
const notes = [
  '本次只改当前画布草稿；需通过原 Save 保存后才持久化。不会生成或删除素材文件。',
  '仅核对画布元数据与已记录的资产 pin；不验证二进制内容或模型质量，不刷新或替换来源。',
  '移除只解除当前画布引用和对应分组成员关系；对齐沿用原画布位置语义。',
];
function unavailable(state: Exclude<CanvasBulkActionPlan['state'], 'ready'>, message: string): CanvasBulkActionPlan {
  return { state, message, binding: null, operation: null, items: [], notes: [...notes] };
}
function reject(): never { throw new Error('Invalid canvas bulk metadata'); }
function row(value: unknown, allowed: string[], required = allowed): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) reject();
  const result = value as Record<string, unknown>;
  if (Object.keys(result).some(key => !allowed.includes(key)) || required.some(key => !Object.hasOwn(result, key))) reject();
  return result;
}
function text(value: unknown, max = 240, empty = false): string {
  if (typeof value !== 'string' || (!empty && !value.trim()) || [...value].length > max || /[\u0000-\u001f\u007f]/.test(value)) reject();
  return value;
}
function integer(value: unknown, min: number, max = Number.MAX_SAFE_INTEGER): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < min || value > max) reject();
  return value;
}
/** Only validated projections enter this serializer; no input toJSON is invoked. */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    const source = value as Record<string, unknown>;
    return `{${Object.keys(source).filter(key => source[key] !== undefined).sort().map(key => `${JSON.stringify(key)}:${canonical(source[key])}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}
function ownerProjection(value: StudioGraphDraftOwner) {
  const source = row(value, ['projectId', 'incarnation', 'actorId', 'actorWorkspaceId', 'mode', 'workspaceId', 'storylineId', 'branchId']);
  const projectId = text(source.projectId), incarnation = text(source.incarnation), actorId = text(source.actorId);
  if (!graphDraftIncarnation(incarnation)) reject();
  const mode = source.mode, actorWorkspaceId = text(source.actorWorkspaceId, 240, true), workspaceId = text(source.workspaceId, 240, true);
  const storylineId = text(source.storylineId, 240, true), branchId = text(source.branchId, 240, true);
  if (mode !== 'local' && mode !== 'collaboration') reject();
  if (mode === 'local' && [actorWorkspaceId, workspaceId, storylineId, branchId].some(Boolean)
    || mode === 'collaboration' && (!workspaceId || !storylineId || !branchId || actorWorkspaceId !== workspaceId)) reject();
  const scope: StudioGraphScope = mode === 'local' ? { mode, novel_id: projectId }
    : { mode, novel_id: projectId, workspace_id: workspaceId, storyline_id: storylineId, branch_id: branchId };
  return { owner: { projectId, incarnation, actorId, actorWorkspaceId, mode, workspaceId, storylineId, branchId }, scope };
}
function scopeProjection(value: unknown): StudioGraphScope {
  const source = row(value, ['mode', 'novel_id', 'workspace_id', 'storyline_id', 'branch_id'], ['mode', 'novel_id']);
  if (source.mode === 'local') { row(value, ['mode', 'novel_id']); return { mode: 'local', novel_id: text(source.novel_id) }; }
  if (source.mode !== 'collaboration') reject();
  return { mode: 'collaboration', novel_id: text(source.novel_id), workspace_id: text(source.workspace_id), storyline_id: text(source.storyline_id), branch_id: text(source.branch_id) };
}
function baseProjection(source: Record<string, unknown>, scope: StudioGraphScope) {
  if (source.execution_authority !== false || source.binary_content_verified !== false) reject();
  const definition = checkedCanvasDefinition(source.definition), version = integer(source.version, 1, 21);
  const id = text(source.id), digest = text(source.definition_digest, 64);
  if (!/^[a-f0-9]{64}$/.test(digest)) reject();
  text(source.created_at, 128); text(source.updated_at, 128);
  const capacity = row(source.capacity, ['history_used', 'record_bytes']);
  integer(capacity.history_used, 0, 20); integer(capacity.record_bytes, 1, 2_000_000);
  if (!Array.isArray(source.reference_states) || source.reference_states.length !== definition.cards.length) reject();
  const reference_states = source.reference_states.map((entry, index): CanvasReferenceState => {
    const state = row(entry, ['card_id', 'state', 'filename'], ['card_id', 'state']), card = definition.cards[index];
    if (state.card_id !== card.id || !['CURRENT_METADATA', 'STALE', 'UNAVAILABLE'].includes(state.state as string)
      || (state.state === 'UNAVAILABLE') !== (card.asset === undefined)
      || (state.state === 'CURRENT_METADATA') !== (state.filename !== undefined)) reject();
    return { card_id: card.id, state: state.state as CanvasReferenceState['state'], ...(state.filename === undefined ? {} : { filename: text(state.filename, 1024) }) };
  });
  return { project_id: text(source.project_id), scope, id, version, definition_digest: digest, definition, reference_states };
}

/** Pure metadata projection. Ready grants no save, transport, execution, or binary verification authority. */
export function planCanvasBulkAction(input: CanvasBulkActionInput): CanvasBulkActionPlan {
  // Retirement is checked before touching any stale content getters, including operation.
  if (input.current !== true) return unavailable('stale', '当前画布上下文已失效，旧操作预览已隐藏；请重新选择。');
  try {
    if (!input.owner) return unavailable('missing', '缺少当前项目、作者或 incarnation，无法绑定操作；请从原画布上下文重新读取。');
    const ownership = ownerProjection(input.owner);
    let base: ReturnType<typeof baseProjection> | null = null;
    if (input.base !== undefined) {
      const source = row(input.base, ['project_id', 'scope', 'id', 'version', 'definition', 'definition_digest', 'created_at', 'updated_at', 'reference_states', 'execution_authority', 'binary_content_verified', 'capacity']);
      const scope = scopeProjection(source.scope);
      if (text(source.project_id) !== ownership.owner.projectId || canonical(scope) !== canonical(ownership.scope)) {
        return unavailable('stale', '原画布项目或协作范围已变化；旧选择不会用于其他画布。');
      }
      base = baseProjection(source, scope);
    }
    const operation = input.operation;
    if (!operations.includes(operation)) return unavailable('invalid', '此操作不受支持；仅支持移除引用、左对齐或顶端对齐。');
    const selected = input.selectedIds;
    if (!Array.isArray(selected) || !selected.length || selected.length > CANVAS_BULK_SELECTION_LIMIT
      || selected.some(id => typeof id !== 'string' || !/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id)) || new Set(selected).size !== selected.length) {
      return unavailable('invalid', `请选择 1–${CANVAS_BULK_SELECTION_LIMIT} 张不重复的原画布卡片；不会截断或猜测目标。`);
    }
    const selection = [...selected], definition = checkedCanvasDefinition(input.definition);
    const cards = new Map(definition.cards.map(card => [card.id, card]));
    if (selection.some(id => !cards.has(id))) return unavailable('missing', '所选卡片已缺失；未对其余卡片执行部分操作，请重新选择。');
    if (operation !== 'REMOVE_CARDS' && selection.length < 2) return unavailable('invalid', '对齐至少需要两张卡片；请重新选择。');
    const next = checkedCanvasDefinition(operation === 'REMOVE_CARDS'
      ? selection.reduce(removeCanvasCard, definition)
      : alignCanvasCards(definition, selection, operation === 'ALIGN_LEFT' ? 'left' : 'top'));
    const after = new Map(next.cards.map(card => [card.id, card]));
    const oldCards = new Map(base?.definition.cards.map(card => [card.id, card]) ?? []);
    const states = new Map(base?.reference_states.map(state => [state.card_id, state]) ?? []);
    const items = selection.map((cardId): CanvasBulkActionItem => {
      const before = cards.get(cardId)!, result = after.get(cardId), prior = oldCards.get(cardId);
      const recorded = prior && canonical(prior.asset) === canonical(before.asset) ? states.get(cardId) : undefined;
      return { cardId, before, ...(result ? { after: result } : {}), changed: canonical(before) !== canonical(result),
        beforeGroupId: definition.groups?.find(group => group.card_ids.includes(cardId))?.id ?? null,
        afterGroupId: next.groups?.find(group => group.card_ids.includes(cardId))?.id ?? null,
        referenceState: !before.asset ? 'UNAVAILABLE' : recorded?.state ?? 'UNVERIFIED',
        ...(recorded?.filename === undefined ? {} : { filename: recorded.filename }) };
    });
    if (!items.some(item => item.changed)) return unavailable('invalid', '所选卡片已经对齐，没有待应用的元数据变化。');
    return { state: 'ready', message: `已预览 ${items.length} 张卡片，${items.filter(item => item.changed).length} 张有变化；请逐项确认。`,
      binding: canonical({ contract: 'studio-canvas-bulk-action/1', ...ownership, base, definition, selection, operation }),
      operation, items, definition: next, notes: [...notes] };
  } catch {
    return unavailable('invalid', '画布、归属或引用状态无法核验；已隐藏操作预览，请重新读取。');
  }
}
