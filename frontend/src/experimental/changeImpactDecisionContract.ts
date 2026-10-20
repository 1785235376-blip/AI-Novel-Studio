import { ApiError } from '../api';
import type { ImpactSource } from './changeImpactClient';
export type ImpactDecisionChoice = 'KEEP' | 'REBUILD';
export type ImpactDecisionSelection = { key: string; expected_version: number; choice: ImpactDecisionChoice };
export type ImpactDecisionPreview = { source_snapshot: ImpactSource; preview_digest: string; decision_only: true; automatic_execution: false;
  items: { key: string; kind: string; label: string; version: number; choice: ImpactDecisionChoice; locked: boolean; stale: boolean; refresh_candidate: boolean; refresh_reason: string | null }[] };
export type ImpactDecisionRecord = { id: string; version: 1; request_id: string; source_snapshot: ImpactSource; preview_digest: string; current: boolean; decision_only: true; automatic_execution: false;
  items: { key: string; kind: string; label: string; version: number; current_version: number; choice: ImpactDecisionChoice; current: boolean }[] };
const invalid = (): never => { throw new ApiError({ status: 200, code: 'CHANGE_IMPACT_DECISION_RESPONSE_INVALID', message: '决定回执与本次来源或选择不一致，请读取原保存记录核对。' }); };
const record = (v: unknown): Record<string, unknown> => !v || typeof v !== 'object' || Array.isArray(v) ? invalid() : v as Record<string, unknown>;
const text = (v: unknown, max = 500): string => typeof v !== 'string' || !v.trim() || v.length > max || /[\u0000-\u001f\u007f]/.test(v) ? invalid() : v;
const integer = (v: unknown): number => typeof v !== 'number' || !Number.isSafeInteger(v) || v < 0 ? invalid() : v;
const bool = (v: unknown): boolean => typeof v !== 'boolean' ? invalid() : v;
const digest = (v: unknown): string => typeof v !== 'string' || !/^[a-f0-9]{64}$/.test(v) ? invalid() : v;
const choice = (v: unknown): ImpactDecisionChoice => v === 'KEEP' || v === 'REBUILD' ? v : invalid();
const requestId = (v: unknown): string => typeof v !== 'string' || !/^[A-Za-z0-9][A-Za-z0-9_-]{0,119}$/.test(v) ? invalid() : v;
const rows = (v: unknown, max: number): unknown[] => !Array.isArray(v) || !v.length || v.length > max ? invalid() : v;
const canonical = (value: unknown): string => JSON.stringify(value, (_key, item) => item && typeof item === 'object' && !Array.isArray(item)
  ? Object.fromEntries(Object.keys(item).sort().map(key => [key, item[key]])) : item);
function source(v: unknown, expected: ImpactSource): ImpactSource {
  const r = record(v); if (r.kind !== expected.kind || r.id !== expected.id || r.binding == null || canonical(r.binding).length > 4096) invalid();
  return { kind: expected.kind, id: expected.id, label: text(r.label, 2000), binding: r.binding };
}
function flags(r: Record<string, unknown>) { if (r.decision_only !== true || r.automatic_execution !== false) invalid(); }
export function checkedDecisionPreview(v: unknown, expected: ImpactSource, selected: readonly ImpactDecisionSelection[]): ImpactDecisionPreview {
  const r = record(v); flags(r); const snapshot = source(r.source_snapshot, expected);
  if (canonical(snapshot.binding) !== canonical(expected.binding)) invalid();
  const items = rows(r.items, 20).map(value => { const item = record(value); return { key: text(item.key), kind: text(item.kind, 80), label: text(item.label, 2000),
    version: integer(item.version), choice: choice(item.choice), locked: bool(item.locked), stale: bool(item.stale), refresh_candidate: bool(item.refresh_candidate),
    refresh_reason: item.refresh_reason === null ? null : text(item.refresh_reason) }; });
  if (items.length !== selected.length || new Set(items.map(item => item.key)).size !== items.length
    || items.some((item, index) => item.key !== selected[index].key || item.version !== selected[index].expected_version || item.choice !== selected[index].choice)) invalid();
  return { source_snapshot: snapshot, items, preview_digest: digest(r.preview_digest), decision_only: true, automatic_execution: false };
}
export function checkedDecisionRecord(v: unknown, expected: ImpactSource): ImpactDecisionRecord {
  const r = record(v); flags(r); if (r.version !== 1) invalid();
  const items = rows(r.items, 20).map(value => { const item = record(value); return { key: text(item.key), kind: text(item.kind, 80), label: text(item.label, 2000),
    version: integer(item.version), current_version: integer(item.current_version), choice: choice(item.choice), current: bool(item.current) }; });
  const current = bool(r.current);
  if (new Set(items.map(item => item.key)).size !== items.length || current !== items.every(item => item.current)) invalid();
  return { id: text(r.id, 240), version: 1, request_id: requestId(r.request_id), source_snapshot: source(r.source_snapshot, expected),
    preview_digest: digest(r.preview_digest), items, current, decision_only: true, automatic_execution: false };
}
export function checkedDecisionSave(v: unknown, expected: ImpactSource, preview: ImpactDecisionPreview, id: string): ImpactDecisionRecord {
  const row = checkedDecisionRecord(v, expected);
  if (row.request_id !== id || row.preview_digest !== preview.preview_digest || canonical(row.source_snapshot) !== canonical(preview.source_snapshot)
    || row.items.length !== preview.items.length || row.items.some((item, index) => item.key !== preview.items[index].key
      || item.version !== preview.items[index].version || item.choice !== preview.items[index].choice)) invalid();
  return row;
}
export function checkedDecisionRows(v: unknown, expected: ImpactSource): { items: ImpactDecisionRecord[] } {
  const r = record(v);
  const items = (Array.isArray(r.items) && r.items.length <= 25 ? r.items : invalid()).map((row: unknown) => checkedDecisionRecord(row, expected));
  if (new Set(items.map(item => item.id)).size !== items.length || new Set(items.map(item => item.request_id)).size !== items.length) invalid();
  return { items };
}
