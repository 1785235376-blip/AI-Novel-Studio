import { ApiError } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';
import type { StudioGraphOwner } from './studioGraphTypes';

export type CanvasAssetReference = { asset_id: string; version: number; digest: string; kind: 'image' | 'video' | 'audio' };
export type CanvasCard = { id: string; position: { x: number; y: number }; asset?: CanvasAssetReference };
export type CanvasDisplayGroup = { id: string; name: string; card_ids: string[]; parent_id?: string; collapsed: boolean };
export type CanvasDefinition = { schema_version: 1; title: string; cards: CanvasCard[]; viewport: { x: number; y: number; zoom: number }; groups?: CanvasDisplayGroup[] };
export type CanvasReferenceState = { card_id: string; state: 'CURRENT_METADATA' | 'STALE' | 'UNAVAILABLE'; filename?: string };
export type CanvasViewRecord = StudioGraphOwner & { id: string; version: number; definition: CanvasDefinition; definition_digest: string;
  created_at: string; updated_at: string; reference_states: CanvasReferenceState[]; execution_authority: false; binary_content_verified: false;
  capacity: { history_used: number; record_bytes: number } };
export type CanvasViewSummary = Pick<CanvasViewRecord, 'id' | 'version' | 'definition_digest' | 'created_at' | 'updated_at'> & { title: string; card_count: number };
function invalid(): never { throw new ApiError({ status: 422, code: 'STUDIO_CANVAS_VIEW_INVALID', message: '媒体画布数据不完整或已经变化，请重新读取。' }); }
function object(v: unknown): Record<string, unknown> { if (!v || typeof v !== 'object' || Array.isArray(v)) invalid(); return v as Record<string, unknown>; }
function keys(v: Record<string, unknown>, allowed: string[]) { if (Object.keys(v).some(k => !allowed.includes(k))) invalid(); }
function text(v: unknown, max = 240): string { if (typeof v !== 'string' || !v.trim() || [...v].length > max) invalid(); return v; }
function number(v: unknown, min: number, max: number): number { if (typeof v !== 'number' || !Number.isFinite(v) || v < min || v > max) invalid(); return v; }
function integer(v: unknown, min = 1, max = Number.MAX_SAFE_INTEGER): number { const n = number(v, min, max); if (!Number.isSafeInteger(n)) invalid(); return n; }
function digest(v: unknown): string { const s = text(v, 64); if (!/^[a-f0-9]{64}$/.test(s)) invalid(); return s; }
function list(v: unknown, max: number): unknown[] { if (!Array.isArray(v) || v.length > max) invalid(); return v; }
function position(v: unknown) { const r = object(v); keys(r, ['x', 'y']); return { x: number(r.x, -100_000, 100_000), y: number(r.y, -100_000, 100_000) }; }
function reference(v: unknown): CanvasAssetReference { const r = object(v); keys(r, ['asset_id', 'version', 'digest', 'kind']); if (!['image', 'video', 'audio'].includes(r.kind as string)) invalid();
  return { asset_id: text(r.asset_id), version: integer(r.version), digest: digest(r.digest), kind: r.kind as CanvasAssetReference['kind'] }; }
export function checkedCanvasDefinition(v: unknown, writable = false): CanvasDefinition {
  const r = object(v); keys(r, ['schema_version', 'title', 'cards', 'viewport', 'groups']); if (r.schema_version !== 1) invalid();
  const cards = list(r.cards, 1000).map(v => { const c = object(v); keys(c, ['id', 'position', 'asset']); const id = text(c.id, 64);
    if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id) || writable && c.asset === undefined) invalid();
    return { id, position: position(c.position), ...(c.asset === undefined ? {} : { asset: reference(c.asset) }) }; });
  if (new Set(cards.map(c => c.id)).size !== cards.length) invalid();
  const view = object(r.viewport); keys(view, ['x', 'y', 'zoom']);
  const result: CanvasDefinition = { schema_version: 1, title: text(r.title, 160), cards,
    viewport: { x: number(view.x, -100_000, 100_000), y: number(view.y, -100_000, 100_000), zoom: number(view.zoom, .35, 2.5) } };
  if (r.groups !== undefined) {
    const groups = list(r.groups, 64).map(v => { const g = object(v); keys(g, ['id', 'name', 'card_ids', 'parent_id', 'collapsed']); const id = text(g.id, 64);
      if (!/^[A-Za-z][A-Za-z0-9_-]{0,63}$/.test(id) || typeof g.collapsed !== 'boolean') invalid();
      const ids = list(g.card_ids, 1000).map(v => text(v, 64));
      const parent = g.parent_id === undefined ? undefined : text(g.parent_id, 64);
      return { id, name: text(g.name, 80), card_ids: ids, ...(parent === undefined ? {} : { parent_id: parent }), collapsed: g.collapsed };
    });
    if (!groups.length || new Set(groups.map(g => g.id)).size !== groups.length) invalid();
    const byId = new Map(groups.map(g => [g.id, g])), members = new Set<string>(), cardIds = new Set(cards.map(c => c.id));
    for (const group of groups) {
      for (const id of group.card_ids) { if (!cardIds.has(id) || members.has(id)) invalid(); members.add(id); }
      const seen = new Set([group.id]); let parent = group.parent_id;
      while (parent !== undefined) { if (!byId.has(parent) || seen.has(parent) || seen.size >= 8) invalid(); seen.add(parent); parent = byId.get(parent)!.parent_id; }
    }
    result.groups = groups;
  }
  if (new TextEncoder().encode(JSON.stringify(result)).length > 512_000) invalid();
  return result;
}

/** No credential lookup or execution methods. The original Graph client supplies its captured transport and owner decoder. */
export function createCanvasViewClient(projectId: string, transport: StudioGraphTransport, owner: (row: Record<string, unknown>) => StudioGraphOwner) {
  const base = `/api/projects/${encodeURIComponent(projectId)}/studio/canvas-views`;
  function summary(v: unknown): CanvasViewSummary { const r = object(v); keys(r, ['id', 'version', 'definition_digest', 'created_at', 'updated_at', 'title', 'card_count']);
    return { id: text(r.id), version: integer(r.version), definition_digest: digest(r.definition_digest), created_at: text(r.created_at, 128), updated_at: text(r.updated_at, 128), title: text(r.title, 160), card_count: integer(r.card_count, 0, 1000) }; }
  function record(v: unknown, expectedId?: string): CanvasViewRecord {
    const r = object(v); keys(r, ['project_id', 'scope', 'id', 'version', 'definition', 'definition_digest', 'created_at', 'updated_at', 'reference_states', 'execution_authority', 'binary_content_verified', 'capacity']);
    const ownership = owner(r), id = text(r.id); if (expectedId !== undefined && id !== expectedId || r.execution_authority !== false || r.binary_content_verified !== false) invalid();
    const definition = checkedCanvasDefinition(r.definition);
    const states = list(r.reference_states, 1000).map((v, index): CanvasReferenceState => {
      const s = object(v); keys(s, ['card_id', 'state', 'filename']); const card = definition.cards[index];
      if (!card || s.card_id !== card.id || !['CURRENT_METADATA', 'STALE', 'UNAVAILABLE'].includes(s.state as string)) invalid();
      if ((s.state === 'UNAVAILABLE') !== (card.asset === undefined)) invalid();
      if (s.state !== 'CURRENT_METADATA' && s.filename !== undefined || s.state === 'CURRENT_METADATA' && s.filename === undefined) invalid();
      return { card_id: card.id, state: s.state as CanvasReferenceState['state'], ...(s.filename === undefined ? {} : { filename: text(s.filename, 1024) }) };
    });
    if (states.length !== definition.cards.length) invalid();
    const capacity = object(r.capacity); keys(capacity, ['history_used', 'record_bytes']);
    return { ...ownership, id, version: integer(r.version), definition, definition_digest: digest(r.definition_digest), created_at: text(r.created_at, 128), updated_at: text(r.updated_at, 128),
      reference_states: states, execution_authority: false, binary_content_verified: false, capacity: { history_used: integer(capacity.history_used, 0, 20), record_bytes: integer(capacity.record_bytes, 1, 2_000_000) } };
  }
  return {
    list: async (signal?: AbortSignal) => { const r = object(await transport.json<unknown>(base, 'GET', undefined, signal)); keys(r, ['items', 'execution_authority']); if (r.execution_authority !== false) invalid();
      const items = list(r.items, 8).map(summary); if (new Set(items.map(x => x.id)).size !== items.length) invalid(); return { items }; },
    get: async (id: string, signal?: AbortSignal) => record(await transport.json<unknown>(`${base}/${encodeURIComponent(text(id))}`, 'GET', undefined, signal), id),
    create: async (definition: CanvasDefinition, requestId: string) => {
      const captured = checkedCanvasDefinition(definition, true); if (!/^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$/.test(requestId)) invalid();
      const result = record(await transport.json<unknown>(base, 'POST', { request_id: requestId, expected_version: 0, definition: captured }));
      if (result.version !== 1 || JSON.stringify(result.definition) !== JSON.stringify(captured)) invalid(); return result;
    },
    save: async (id: string, expectedVersion: number, definition: CanvasDefinition) => {
      const captured = checkedCanvasDefinition(definition, true), expected = integer(expectedVersion);
      const result = record(await transport.json<unknown>(`${base}/${encodeURIComponent(text(id))}`, 'PUT', { expected_version: expected, definition: captured }), id);
      if (result.version !== expected + 1 || JSON.stringify(result.definition) !== JSON.stringify(captured)) invalid(); return result;
    },
  };
}
export type CanvasViewClient = ReturnType<typeof createCanvasViewClient>;
