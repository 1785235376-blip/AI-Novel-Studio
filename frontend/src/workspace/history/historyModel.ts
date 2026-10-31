/**
 * [HERMIA-FE-20261025 U4-M9a] History projection over the EXISTING canvas-view history owner
 * (studioCanvasViewClient.history / restore). Restore = owner writes a NEW version (old records kept);
 * it never reruns a model, never touches tasks, never re-adopts a result by itself.
 */
import type {RecordKind} from '../contracts';
import type {CanvasDefinition, CanvasViewHistory, CanvasViewHistoryItem} from '../../creative/studioCanvasViewClient';

export const RECORD_KIND_TEXT: Record<RecordKind, {label: string; detail: string}> = {
  'local-draft': {label: '浏览器本地草稿', detail: '只存在这台设备的浏览器里，还没保存到项目。'},
  'saved-work': {label: '已保存作品', detail: '已保存到项目的作品版本。'},
  'asset-version': {label: '正式素材版本', detail: '已审核入库的素材版本，内容不可改写。'},
  'execution-record': {label: '任务执行记录', detail: '一次生成任务的记录；查看它不会重新执行。'},
};

export type CardChange = {cardId: string; change: 'added' | 'removed' | 'moved' | 'asset-changed' | 'asset-cleared'; from?: string; to?: string};
export interface DefinitionDiff { titleChanged: boolean; cards: CardChange[]; viewportChanged: boolean; groupsChanged: boolean; }
const assetText = (a?: {version: number; kind: string}) => a ? `${a.kind === 'image' ? '图像' : a.kind === 'video' ? '视频' : '音频'}素材第 ${a.version} 版` : '空';

export function diffDefinitions(current: CanvasDefinition, other: CanvasDefinition): DefinitionDiff {
  const cur = new Map(current.cards.map(c => [c.id, c])), old = new Map(other.cards.map(c => [c.id, c]));
  const cards: CardChange[] = [];
  for (const [id, c] of cur) {
    const o = old.get(id);
    if (!o) { cards.push({cardId: id, change: 'added'}); continue; }
    if (o.position.x !== c.position.x || o.position.y !== c.position.y) cards.push({cardId: id, change: 'moved'});
    const a = c.asset, b = o.asset;
    if (a && !b) cards.push({cardId: id, change: 'asset-changed', from: assetText(), to: assetText(a)});
    else if (!a && b) cards.push({cardId: id, change: 'asset-cleared', from: assetText(b), to: assetText()});
    else if (a && b && (a.asset_id !== b.asset_id || a.version !== b.version || a.digest !== b.digest)) cards.push({cardId: id, change: 'asset-changed', from: assetText(b), to: assetText(a)});
  }
  for (const id of old.keys()) if (!cur.has(id)) cards.push({cardId: id, change: 'removed'});
  return {titleChanged: current.title !== other.title, cards,
    viewportChanged: JSON.stringify(current.viewport) !== JSON.stringify(other.viewport),
    groupsChanged: JSON.stringify(current.groups ?? []) !== JSON.stringify(other.groups ?? [])};
}

/** Human summary of what a restore to `target` would change relative to the current version (direction: current → target). */
export function restoreImpact(h: CanvasViewHistory, targetVersion: number): {ok: true; lines: string[]; newVersion: number} | {ok: false; reason: string} {
  const target = h.items.find(i => i.version === targetVersion), current = h.items.find(i => i.version === h.current_version);
  if (!target || !current) return {ok: false, reason: '找不到这个历史版本，请重新读取历史。'};
  if (target.version === h.current_version) return {ok: false, reason: '这已经是当前版本。'};
  if (!target.can_restore) return {ok: false, reason: '这个历史版本引用的素材已不可用，服务端不允许恢复。'};
  const d = diffDefinitions(target.definition, current.definition), lines: string[] = [];
  const n = (k: CardChange['change']) => d.cards.filter(c => c.change === k).length;
  if (d.titleChanged) lines.push('标题会改回历史版本');
  if (n('added')) lines.push(`会恢复 ${n('added')} 张已删除的卡片`);
  if (n('removed')) lines.push(`会移除 ${n('removed')} 张之后新增的卡片`);
  if (n('moved')) lines.push(`${n('moved')} 张卡片位置会改回`);
  if (n('asset-changed') + n('asset-cleared')) lines.push(`${n('asset-changed') + n('asset-cleared')} 张卡片引用的素材会改回历史版本（不会重新生成，也不会改动素材本身）`);
  if (!lines.length) lines.push('内容与当前版本相同，只会多一条新的版本记录');
  lines.push(`恢复后生成新的第 ${h.current_version + 1} 版；当前第 ${h.current_version} 版和所有旧版本都保留`);
  lines.push('不会重跑模型、不会重新入队，也不会自动重新采用旧结果');
  return {ok: true, lines, newVersion: h.current_version + 1};
}

/** Provenance line for one history item (no raw ids). */
export function provenance(item: CanvasViewHistoryItem): string {
  const refs = item.definition.cards.filter(c => c.asset).length;
  const stale = item.reference_states.filter(s => s.state !== 'CURRENT_METADATA').length;
  return `第 ${item.version} 版 · 保存于 ${item.updated_at} · 引用 ${refs} 份素材${stale ? `（${stale} 份已过期或不可用）` : ''}`;
}
