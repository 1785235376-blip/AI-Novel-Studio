import { checkedCanvasDefinition } from './studioCanvasViewClient';
import type { CanvasAssetReference, CanvasCard, CanvasDefinition, CanvasDisplayGroup, CanvasReferenceState, CanvasViewHistory, CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioGraphScope } from './studioGraphTypes';

export type MediaCanvasHistoryComparisonInput = {
  base: CanvasViewRecord;
  history: CanvasViewHistory;
  targetVersion: number;
  incarnation?: string;
  current: boolean;
};
export type MediaCanvasHistoryComparisonCounts = {
  cardsAdded: number; cardsRemoved: number;
  assetPinsChanged: number; assetIdsChanged: number; assetKindsChanged: number; assetVersionsChanged: number; assetDigestsChanged: number;
  positionsChanged: number; groupsAdded: number; groupsRemoved: number; groupsChanged: number; membershipsChanged: number;
  viewportChanged: number; viewOptionsChanged: number; titleChanged: number; cardOrderChanged: number; groupOrderChanged: number;
  referenceStatesChanged: number; referencesCurrent: number; referencesStale: number; referencesUnavailable: number;
  totalChanges: number;
};
type PinField = 'presence' | 'asset_id' | 'kind' | 'version' | 'digest';
export type MediaCanvasHistoryChange =
  | { kind: 'card-added'; cardId: string; after: CanvasCard; referenceState: CanvasReferenceState['state'] }
  | { kind: 'card-removed'; cardId: string; before: CanvasCard; referenceState: CanvasReferenceState['state'] }
  | { kind: 'asset-pin'; cardId: string; before?: CanvasAssetReference; after?: CanvasAssetReference; fields: PinField[] }
  | { kind: 'position'; cardId: string; before: CanvasCard['position']; after: CanvasCard['position'] }
  | { kind: 'membership'; cardId: string; before: string | null; after: string | null }
  | { kind: 'reference-state'; cardId: string; before: CanvasReferenceState['state']; after: CanvasReferenceState['state'] }
  | { kind: 'group-added'; groupId: string; after: CanvasDisplayGroup }
  | { kind: 'group-removed'; groupId: string; before: CanvasDisplayGroup }
  | { kind: 'group'; groupId: string; before: CanvasDisplayGroup; after: CanvasDisplayGroup }
  | { kind: 'viewport'; before: CanvasDefinition['viewport']; after: CanvasDefinition['viewport'] }
  | { kind: 'view-options'; before?: CanvasDefinition['view_options']; after?: CanvasDefinition['view_options'] }
  | { kind: 'title'; before: string; after: string }
  | { kind: 'card-order' | 'group-order'; before: string[]; after: string[] };
export type MediaCanvasHistoryComparison = {
  state: 'ready' | 'stale' | 'missing' | 'invalid';
  message: string;
  /** Canonical display identity only. Never an execution or restoration permission. */
  binding: string | null;
  counts: MediaCanvasHistoryComparisonCounts;
  changes: MediaCanvasHistoryChange[];
  notes: string[];
};
const notes = [
  '仅影响此画布的已记录布局与资产 pin；恢复会创建新的当前版本，并退役旧预览及回流意图。',
  '仅比较元数据；不验证二进制内容或模型质量，不回滚历史文件，也不自动替换为最新资产。',
  '服务端 can_restore 仅是读取时的可恢复提示；本对比与绑定标识均不授予恢复权限。',
];
function emptyCounts(): MediaCanvasHistoryComparisonCounts {
  return { cardsAdded: 0, cardsRemoved: 0, assetPinsChanged: 0, assetIdsChanged: 0, assetKindsChanged: 0, assetVersionsChanged: 0, assetDigestsChanged: 0,
    positionsChanged: 0, groupsAdded: 0, groupsRemoved: 0, groupsChanged: 0, membershipsChanged: 0, viewportChanged: 0, viewOptionsChanged: 0,
    titleChanged: 0, cardOrderChanged: 0, groupOrderChanged: 0, referenceStatesChanged: 0, referencesCurrent: 0, referencesStale: 0, referencesUnavailable: 0, totalChanges: 0 };
}
function unavailable(state: Exclude<MediaCanvasHistoryComparison['state'], 'ready'>, message: string): MediaCanvasHistoryComparison {
  return { state, message, binding: null, counts: emptyCounts(), changes: [], notes: [] };
}
function reject(): never { throw new Error('Invalid history comparison metadata'); }
function record(value: unknown, allowed: string[], required = allowed): Record<string, unknown> {
  if (!value || typeof value !== 'object' || Array.isArray(value)) reject();
  const row = value as Record<string, unknown>;
  if (Object.keys(row).some(key => !allowed.includes(key)) || required.some(key => !Object.hasOwn(row, key))) reject();
  return row;
}
function text(value: unknown, max = 240): string {
  if (typeof value !== 'string' || !value.trim() || [...value].length > max) reject();
  return value;
}
function version(value: unknown): number {
  if (typeof value !== 'number' || !Number.isSafeInteger(value) || value < 1 || value > 21) reject();
  return value;
}
function digest(value: unknown): string {
  if (typeof value !== 'string' || !/^[a-f0-9]{64}$/.test(value)) reject();
  return value;
}
function scope(value: unknown): StudioGraphScope {
  if (!value || typeof value !== 'object') reject();
  const mode = (value as Record<string, unknown>).mode;
  if (mode === 'local') {
    const row = record(value, ['mode', 'novel_id']);
    return { mode, novel_id: text(row.novel_id) };
  }
  if (mode === 'collaboration') {
    const row = record(value, ['mode', 'novel_id', 'workspace_id', 'storyline_id', 'branch_id']);
    return { mode, novel_id: text(row.novel_id), workspace_id: text(row.workspace_id), storyline_id: text(row.storyline_id), branch_id: text(row.branch_id) };
  }
  return reject();
}
function referenceStates(value: unknown, definition: CanvasDefinition): CanvasReferenceState[] {
  if (!Array.isArray(value) || value.length !== definition.cards.length) reject();
  return value.map((entry, index) => {
    const row = record(entry, ['card_id', 'state', 'filename'], ['card_id', 'state']);
    const card = definition.cards[index];
    if (row.card_id !== card.id || !['CURRENT_METADATA', 'STALE', 'UNAVAILABLE'].includes(row.state as string)) reject();
    const state = row.state as CanvasReferenceState['state'];
    if ((state === 'UNAVAILABLE') !== (card.asset === undefined)) reject();
    if (state !== 'CURRENT_METADATA' && row.filename !== undefined || state === 'CURRENT_METADATA' && row.filename === undefined) reject();
    return { card_id: card.id, state, ...(row.filename === undefined ? {} : { filename: text(row.filename, 1024) }) };
  });
}
/** Sorted object keys, recorded array order, no input toJSON or extension fields. */
function canonical(value: unknown): string {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value && typeof value === 'object') {
    const row = value as Record<string, unknown>;
    return `{${Object.keys(row).filter(key => row[key] !== undefined).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key])}`).join(',')}}`;
  }
  return JSON.stringify(value) ?? 'null';
}
function members(groups: CanvasDisplayGroup[]) {
  return new Map(groups.flatMap(group => group.card_ids.map(id => [id, group.id] as const)));
}

/** Pure, read-only projection. A ready result means comparable metadata, never restore eligibility. */
export function buildMediaCanvasHistoryComparison(input: MediaCanvasHistoryComparisonInput): MediaCanvasHistoryComparison {
  // Owner retirement must hide old content before touching any base/history getter.
  if (input.current !== true) return unavailable('stale', '当前画布上下文已失效，旧版本对比已隐藏；请重新读取。');
  try {
    const base = record(input.base, ['project_id', 'scope', 'id', 'version', 'definition', 'definition_digest', 'created_at', 'updated_at', 'reference_states', 'execution_authority', 'binary_content_verified', 'capacity']);
    const history = record(input.history, ['project_id', 'scope', 'id', 'incarnation', 'current_version', 'current_definition_digest', 'items', 'restore_policy', 'execution_authority', 'binary_content_verified']);
    if (base.execution_authority !== false || base.binary_content_verified !== false || history.execution_authority !== false || history.binary_content_verified !== false || history.restore_policy !== 'CURRENT_METADATA_ONLY') reject();
    const currentOwner = { project_id: text(base.project_id), scope: scope(base.scope), id: text(base.id) };
    const historyOwner = { project_id: text(history.project_id), scope: scope(history.scope), id: text(history.id) };
    const currentVersion = version(base.version), currentDigest = digest(base.definition_digest);
    const historyVersion = version(history.current_version), historyDigest = digest(history.current_definition_digest), historyIncarnation = text(history.incarnation);
    if (canonical(currentOwner) !== canonical(historyOwner) || currentVersion !== historyVersion || currentDigest !== historyDigest) {
      return unavailable('stale', '项目、范围、画布或当前版本已变化；请重新读取当前画布及历史。');
    }
    if (input.incarnation === undefined) return unavailable('missing', '缺少当前项目 incarnation，无法绑定此对比；请从原项目上下文重新读取。');
    const incarnation = text(input.incarnation);
    if (incarnation !== historyIncarnation) return unavailable('stale', '项目 incarnation 已变化；旧版本对比已隐藏，请重新读取。');
    const targetVersion = version(input.targetVersion);
    const currentDefinition = checkedCanvasDefinition(base.definition), currentStates = referenceStates(base.reference_states, currentDefinition);
    text(base.created_at, 128); text(base.updated_at, 128);
    const capacity = record(base.capacity, ['history_used', 'record_bytes']);
    if (typeof capacity.history_used !== 'number' || !Number.isSafeInteger(capacity.history_used) || capacity.history_used < 0 || capacity.history_used > 20
      || typeof capacity.record_bytes !== 'number' || !Number.isSafeInteger(capacity.record_bytes) || capacity.record_bytes < 1 || capacity.record_bytes > 2_000_000) reject();
    if (!Array.isArray(history.items) || history.items.length > 21) reject();
    const versions = new Set<number>();
    const items = history.items.map(value => {
      const row = record(value, ['version', 'definition', 'definition_digest', 'reference_states', 'created_at', 'updated_at', 'can_restore']);
      const itemVersion = version(row.version);
      if (versions.has(itemVersion) || itemVersion > currentVersion || typeof row.can_restore !== 'boolean') reject();
      versions.add(itemVersion);
      const definition = checkedCanvasDefinition(row.definition), states = referenceStates(row.reference_states, definition);
      text(row.created_at, 128); text(row.updated_at, 128);
      if (row.can_restore !== (itemVersion < currentVersion && states.every(state => state.state === 'CURRENT_METADATA'))) reject();
      return { version: itemVersion, definition_digest: digest(row.definition_digest), definition, reference_states: states, can_restore: row.can_restore };
    });
    const target = items.find(item => item.version === targetVersion);
    if (!target) return unavailable('missing', '所选历史版本已缺失；请重新读取并选择版本。');
    const latest = items.find(item => item.version === currentVersion);
    if (!latest || latest.definition_digest !== currentDigest || canonical(latest.definition) !== canonical(currentDefinition) || canonical(latest.reference_states) !== canonical(currentStates)) {
      return unavailable('stale', '历史中的当前快照与当前画布不一致；请重新读取。');
    }
    if (items.length !== currentVersion || items.some((item, index) => item.version !== index + 1)) reject();

    const counts = emptyCounts(), changes: MediaCanvasHistoryChange[] = [];
    const beforeCards = new Map(currentDefinition.cards.map(card => [card.id, card]));
    const afterCards = new Map(target.definition.cards.map(card => [card.id, card]));
    const beforeStates = new Map(currentStates.map(state => [state.card_id, state.state]));
    const afterStates = new Map(target.reference_states.map(state => [state.card_id, state.state]));
    const beforeGroups = currentDefinition.groups ?? [], afterGroups = target.definition.groups ?? [];
    const beforeMembers = members(beforeGroups), afterMembers = members(afterGroups);
    for (const card of currentDefinition.cards) if (!afterCards.has(card.id)) {
      counts.cardsRemoved++; changes.push({ kind: 'card-removed', cardId: card.id, before: card, referenceState: beforeStates.get(card.id)! });
    }
    for (const card of target.definition.cards) {
      const before = beforeCards.get(card.id);
      if (!before) { counts.cardsAdded++; changes.push({ kind: 'card-added', cardId: card.id, after: card, referenceState: afterStates.get(card.id)! }); continue; }
      const fields: PinField[] = [];
      if (!!before.asset !== !!card.asset) fields.push('presence');
      for (const field of ['asset_id', 'kind', 'version', 'digest'] as const) if (before.asset?.[field] !== card.asset?.[field]) fields.push(field);
      if (fields.length) {
        counts.assetPinsChanged++;
        if (fields.includes('asset_id')) counts.assetIdsChanged++;
        if (fields.includes('kind')) counts.assetKindsChanged++;
        if (fields.includes('version')) counts.assetVersionsChanged++;
        if (fields.includes('digest')) counts.assetDigestsChanged++;
        changes.push({ kind: 'asset-pin', cardId: card.id, before: before.asset, after: card.asset, fields });
      }
      if (canonical(before.position) !== canonical(card.position)) { counts.positionsChanged++; changes.push({ kind: 'position', cardId: card.id, before: before.position, after: card.position }); }
      if (beforeStates.get(card.id) !== afterStates.get(card.id)) { counts.referenceStatesChanged++; changes.push({ kind: 'reference-state', cardId: card.id, before: beforeStates.get(card.id)!, after: afterStates.get(card.id)! }); }
    }
    for (const id of new Set([...beforeCards.keys(), ...afterCards.keys()])) {
      const before = beforeMembers.get(id) ?? null, after = afterMembers.get(id) ?? null;
      if (before !== after) { counts.membershipsChanged++; changes.push({ kind: 'membership', cardId: id, before, after }); }
    }
    const beforeGroupMap = new Map(beforeGroups.map(group => [group.id, group])), afterGroupMap = new Map(afterGroups.map(group => [group.id, group]));
    for (const group of beforeGroups) if (!afterGroupMap.has(group.id)) { counts.groupsRemoved++; changes.push({ kind: 'group-removed', groupId: group.id, before: group }); }
    for (const group of afterGroups) {
      const before = beforeGroupMap.get(group.id);
      if (!before) { counts.groupsAdded++; changes.push({ kind: 'group-added', groupId: group.id, after: group }); }
      else if (canonical(before) !== canonical(group)) { counts.groupsChanged++; changes.push({ kind: 'group', groupId: group.id, before, after: group }); }
    }
    const sharedBeforeCards = currentDefinition.cards.filter(card => afterCards.has(card.id)).map(card => card.id), sharedAfterCards = target.definition.cards.filter(card => beforeCards.has(card.id)).map(card => card.id);
    if (canonical(sharedBeforeCards) !== canonical(sharedAfterCards)) { counts.cardOrderChanged++; changes.push({ kind: 'card-order', before: sharedBeforeCards, after: sharedAfterCards }); }
    const sharedBeforeGroups = beforeGroups.filter(group => afterGroupMap.has(group.id)).map(group => group.id), sharedAfterGroups = afterGroups.filter(group => beforeGroupMap.has(group.id)).map(group => group.id);
    if (canonical(sharedBeforeGroups) !== canonical(sharedAfterGroups)) { counts.groupOrderChanged++; changes.push({ kind: 'group-order', before: sharedBeforeGroups, after: sharedAfterGroups }); }
    if (canonical(currentDefinition.viewport) !== canonical(target.definition.viewport)) { counts.viewportChanged++; changes.push({ kind: 'viewport', before: currentDefinition.viewport, after: target.definition.viewport }); }
    if (canonical(currentDefinition.view_options) !== canonical(target.definition.view_options)) { counts.viewOptionsChanged++; changes.push({ kind: 'view-options', before: currentDefinition.view_options, after: target.definition.view_options }); }
    if (currentDefinition.title !== target.definition.title) { counts.titleChanged++; changes.push({ kind: 'title', before: currentDefinition.title, after: target.definition.title }); }
    for (const state of target.reference_states) {
      if (state.state === 'CURRENT_METADATA') counts.referencesCurrent++;
      else if (state.state === 'STALE') counts.referencesStale++;
      else counts.referencesUnavailable++;
    }
    counts.totalChanges = changes.length;
    return {
      state: 'ready', message: `当前 v${currentVersion} → 历史 v${targetVersion} 的已记录元数据对比。`,
      binding: canonical({ contract: 'media-canvas-history-comparison/1', current: { ...currentOwner, incarnation, version: currentVersion, definition_digest: currentDigest, definition: currentDefinition, reference_states: currentStates }, target }),
      counts, changes,
      notes: [...notes, ...(target.can_restore ? [] : ['所选版本的 can_restore 为 false；此处仅供核对，不表示可恢复。']),
        ...(counts.referencesStale || counts.referencesUnavailable ? ['所选版本包含过期或不可用来源；不可用来源的原 pin 未被猜测或补全。'] : []),
        '变更项可重叠：同一卡片可能同时发生 pin、坐标和分组变化；pin 字段计数仅针对保留的卡片。'],
    };
  } catch {
    // Never render parser errors or arbitrary extension values supplied by metadata.
    return unavailable('invalid', '版本元数据结构或引用状态无法核验；已隐藏对比，请重新读取。');
  }
}
