import { expect, it, vi } from 'vitest';
import fixture from '../../../tests/fixtures/studio_dual_canvas_loop.json';
import { buildMediaCanvasHistoryComparison } from './mediaCanvasHistoryCompare';
import type { MediaCanvasHistoryComparisonInput } from './mediaCanvasHistoryCompare';
import type { CanvasDefinition, CanvasReferenceState } from './studioCanvasViewClient';

const a = 'a'.repeat(64), b = 'b'.repeat(64);
function definition(): CanvasDefinition { return { schema_version: 1, title: 'Canvas', cards: [], viewport: { x: 0, y: 0, zoom: 1 } }; }
function states(value: CanvasDefinition): CanvasReferenceState[] {
  return value.cards.map(card => ({ card_id: card.id, state: card.asset ? 'CURRENT_METADATA' : 'UNAVAILABLE', ...(card.asset ? { filename: 'synthetic.png' } : {}) }));
}
function input(before = definition(), after = definition()): MediaCanvasHistoryComparisonInput {
  return {
    current: true, incarnation: 'incarnation-A', targetVersion: 1,
    base: { project_id: 'project', scope: { mode: 'local', novel_id: 'novel' }, id: 'canvas', version: 2, definition_digest: b, definition: before,
      reference_states: states(before), created_at: 'created', updated_at: 'updated', execution_authority: false, binary_content_verified: false, capacity: { history_used: 1, record_bytes: 1000 } },
    history: { project_id: 'project', scope: { mode: 'local', novel_id: 'novel' }, id: 'canvas', incarnation: 'incarnation-A', current_version: 2, current_definition_digest: b,
      items: [{ version: 1, definition: after, definition_digest: a, reference_states: states(after), created_at: 'created', updated_at: 'updated', can_restore: after.cards.every(card => !!card.asset) },
        { version: 2, definition: structuredClone(before), definition_digest: b, reference_states: states(before), created_at: 'created', updated_at: 'updated', can_restore: false }],
      restore_policy: 'CURRENT_METADATA_ONLY', execution_authority: false, binary_content_verified: false },
  };
}
const card = (id: string) => ({ id, position: { x: 0, y: 0 }, asset: { asset_id: `asset-${id}`, kind: 'image' as const, version: 1, digest: a } });
function freeze(value: unknown): void {
  if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); }
}
it('compares empty/default definitions without inventing changes or authority', () => {
  const result = buildMediaCanvasHistoryComparison(input());
  expect(result.state).toBe('ready'); expect(result.changes).toEqual([]);
  expect(Object.values(result.counts).every(value => value === 0)).toBe(true);
  expect(result.binding).toContain('media-canvas-history-comparison/1');
  expect(result.notes.join(' ')).toContain('不授予恢复权限');
});
it('counts add/remove, exact source pin fields, positions, viewport, view options and all group effects', () => {
  const before = definition(), after = definition();
  before.cards = [card('Shared'), card('Removed')]; after.cards = [card('Shared'), card('Added')];
  after.cards[0].asset = { asset_id: 'older-audio', kind: 'audio', version: 7, digest: b };
  after.cards[0].position = { x: 24, y: -8 }; after.viewport = { x: 16, y: 32, zoom: 1.5 };
  after.title = 'Historical'; after.view_options = { grid: false, snap_step: null };
  before.groups = [{ id: 'Old', name: 'Old', card_ids: ['Shared'], collapsed: false }, { id: 'Gone', name: 'Gone', card_ids: ['Removed'], collapsed: false }];
  after.groups = [{ id: 'Old', name: 'Renamed', card_ids: [], collapsed: true }, { id: 'New', name: 'New', card_ids: ['Shared', 'Added'], parent_id: 'Old', collapsed: false }];
  const result = buildMediaCanvasHistoryComparison(input(before, after));
  expect(result.state).toBe('ready');
  expect(result.counts).toMatchObject({ cardsAdded: 1, cardsRemoved: 1, assetPinsChanged: 1, assetIdsChanged: 1, assetKindsChanged: 1, assetVersionsChanged: 1, assetDigestsChanged: 1,
    positionsChanged: 1, groupsAdded: 1, groupsRemoved: 1, groupsChanged: 1, membershipsChanged: 3, viewportChanged: 1, viewOptionsChanged: 1, titleChanged: 1, referencesCurrent: 2 });
  expect(result.changes.find(change => change.kind === 'asset-pin')).toMatchObject({ before: card('Shared').asset, after: after.cards[0].asset, fields: ['asset_id', 'kind', 'version', 'digest'] });
  expect(result.counts.totalChanges).toBe(result.changes.length);
});
it('shows masked unavailable and stale sources honestly without filling pins from another card or latest metadata', () => {
  const before = definition(), after = definition(); before.cards = [card('Shared')]; after.cards = [{ id: 'Shared', position: { x: 0, y: 0 } }];
  const result = buildMediaCanvasHistoryComparison(input(before, after));
  expect(result.state).toBe('ready'); expect(result.counts).toMatchObject({ assetPinsChanged: 1, referencesUnavailable: 1, referenceStatesChanged: 1 });
  expect(result.changes.find(change => change.kind === 'asset-pin')).toMatchObject({ after: undefined, fields: ['presence', 'asset_id', 'kind', 'version', 'digest'] });
  expect(result.notes.join(' ')).toContain('原 pin 未被猜测或补全');
  const stale = input(before, before); stale.history.items[0].reference_states[0] = { card_id: 'Shared', state: 'STALE' }; stale.history.items[0].can_restore = false;
  expect(buildMediaCanvasHistoryComparison(stale).counts.referencesStale).toBe(1);
});
it.each(['unknown-state', 'wrong-card', 'duplicate-card', 'missing-state', 'invalid-position', 'group-cycle', 'unknown-field', 'forged-can-restore'] as const)('hides invalid metadata: %s', kind => {
  const d = definition(); d.cards = [card('Card')]; const value = input(d, d), target = value.history.items[0];
  if (kind === 'unknown-state') (target.reference_states[0] as any).state = 'PASS';
  if (kind === 'wrong-card') target.reference_states[0].card_id = 'Other';
  if (kind === 'duplicate-card') target.definition.cards.push(card('Card'));
  if (kind === 'missing-state') target.reference_states = [];
  if (kind === 'invalid-position') target.definition.cards[0].position.x = Infinity;
  if (kind === 'group-cycle') target.definition.groups = [{ id: 'Group', name: 'Group', card_ids: ['Card'], parent_id: 'Group', collapsed: false }];
  if (kind === 'unknown-field') (target.definition as any).secret = 'DO_NOT_ECHO';
  if (kind === 'forged-can-restore') target.can_restore = false;
  const result = buildMediaCanvasHistoryComparison(value);
  expect(result.state).toBe('invalid'); expect(result.binding).toBeNull(); expect(result.changes).toEqual([]); expect(JSON.stringify(result)).not.toContain('DO_NOT_ECHO');
});
it.each(['project', 'scope', 'canvas', 'incarnation', 'current-version', 'current-digest', 'current-definition', 'current-reference'] as const)('retires a comparison after %s changes', kind => {
  const d = definition(); d.cards = [card('Card')]; const value = input(d, d);
  if (kind === 'project') value.base.project_id = 'other';
  if (kind === 'scope') value.base.scope = { mode: 'local', novel_id: 'other' };
  if (kind === 'canvas') value.base.id = 'other';
  if (kind === 'incarnation') value.incarnation = 'incarnation-B';
  if (kind === 'current-version') value.base.version = 3;
  if (kind === 'current-digest') value.base.definition_digest = a;
  if (kind === 'current-definition') value.base.definition.title = 'Changed without digest';
  if (kind === 'current-reference') value.base.reference_states[0].filename = 'changed.png';
  const result = buildMediaCanvasHistoryComparison(value); expect(result.state).toBe('stale'); expect(result.binding).toBeNull(); expect(result.changes).toEqual([]);
});
it('handles missing incarnation/selection, duplicate versions and incomplete histories without pretending a comparison exists', () => {
  const value = input(); value.incarnation = undefined; expect(buildMediaCanvasHistoryComparison(value).state).toBe('missing');
  value.incarnation = 'incarnation-A'; value.targetVersion = 3; expect(buildMediaCanvasHistoryComparison(value).state).toBe('missing');
  value.targetVersion = 1; value.history.items.push(structuredClone(value.history.items[0])); expect(buildMediaCanvasHistoryComparison(value).state).toBe('invalid');
  const incomplete = input(); incomplete.base.version = 3; incomplete.history.current_version = 3; incomplete.history.items[1].version = 3;
  expect(buildMediaCanvasHistoryComparison(incomplete).state).toBe('invalid');
});
it('checks current=false before reading any old data or selection getters', () => {
  const poisoned = { current: false } as MediaCanvasHistoryComparisonInput;
  for (const key of ['base', 'history', 'incarnation', 'targetVersion']) Object.defineProperty(poisoned, key, { get: () => { throw new Error(`read ${key}`); } });
  expect(buildMediaCanvasHistoryComparison(poisoned)).toMatchObject({ state: 'stale', binding: null, changes: [], notes: [] });
});
it('canonicalizes all scope fields and includes every current identity and selected snapshot binding field', () => {
  const original = input(), initial = buildMediaCanvasHistoryComparison(original).binding!;
  const changes: ((value: MediaCanvasHistoryComparisonInput) => void)[] = [
    v => { v.base.project_id = v.history.project_id = 'another-project'; },
    v => { v.base.id = v.history.id = 'another-canvas'; },
    v => { v.base.scope = v.history.scope = { mode: 'collaboration', novel_id: 'novel', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' }; },
    v => { v.incarnation = v.history.incarnation = 'incarnation-B'; },
    v => { v.base.definition_digest = v.history.current_definition_digest = v.history.items[1].definition_digest = a; },
    v => { v.history.items[0].definition_digest = b; },
    v => { v.history.items[0].definition.title = 'Changed target'; },
    v => { v.targetVersion = 2; },
    v => { v.base.version = v.history.current_version = 3; v.history.items[1].can_restore = true; v.history.items.push({ ...structuredClone(v.history.items[1]), version: 3, can_restore: false }); },
  ];
  for (const change of changes) { const value = structuredClone(original); change(value); const result = buildMediaCanvasHistoryComparison(value); expect(result.state).toBe('ready'); expect(result.binding).not.toBe(initial); }
  const withPin = definition(); withPin.cards = [card('Card')]; const pinned = input(withPin, withPin), pinnedBinding = buildMediaCanvasHistoryComparison(pinned).binding;
  pinned.history.items[0].reference_states[0].filename = 'another.png'; expect(buildMediaCanvasHistoryComparison(pinned).binding).not.toBe(pinnedBinding);
  const ordered = input(); ordered.base.scope = { novel_id: 'novel', mode: 'local' }; expect(buildMediaCanvasHistoryComparison(ordered).binding).toBe(initial);
  // Pure A/B/A yields the same A display identity; the original owner must latch retirement, never this helper.
  expect(buildMediaCanvasHistoryComparison(original).binding).toBe(initial);
});
it.each(['workspace_id', 'storyline_id', 'branch_id', 'novel_id'] as const)('binds collaboration %s independently', key => {
  const value = input(); value.base.scope = value.history.scope = { mode: 'collaboration', novel_id: 'novel', workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch' };
  const initial = buildMediaCanvasHistoryComparison(value).binding;
  value.base.scope = { ...value.base.scope, [key]: 'changed' }; value.history.scope = { ...value.history.scope, [key]: 'changed' };
  expect(buildMediaCanvasHistoryComparison(value).binding).not.toBe(initial);
});
it.each(['asset-id', 'kind', 'pin-version', 'pin-digest', 'position', 'viewport', 'groups', 'view-options', 'reference-state'] as const)('binds selected %s metadata even when its claimed definition digest is unchanged', kind => {
  const d = definition(); d.cards = [card('Card')]; const value = input(d, structuredClone(d)), target = value.history.items[0];
  const initial = buildMediaCanvasHistoryComparison(value).binding;
  if (kind === 'asset-id') target.definition.cards[0].asset!.asset_id = 'another-asset';
  if (kind === 'kind') target.definition.cards[0].asset!.kind = 'audio';
  if (kind === 'pin-version') target.definition.cards[0].asset!.version = 5;
  if (kind === 'pin-digest') target.definition.cards[0].asset!.digest = b;
  if (kind === 'position') target.definition.cards[0].position.x = 8;
  if (kind === 'viewport') target.definition.viewport.zoom = 2;
  if (kind === 'groups') target.definition.groups = [{ id: 'Group', name: 'Group', card_ids: ['Card'], collapsed: false }];
  if (kind === 'view-options') target.definition.view_options = { grid: false, snap_step: null };
  if (kind === 'reference-state') { target.reference_states = [{ card_id: 'Card', state: 'STALE' }]; target.can_restore = false; }
  const result = buildMediaCanvasHistoryComparison(value); expect(result.state).toBe('ready'); expect(result.binding).not.toBe(initial);
});
it('projects the existing saved dual canvas history fixture without changing its original pins', () => {
  const value = { base: structuredClone(fixture.returned), history: structuredClone(fixture.history), targetVersion: 1, incarnation: fixture.incarnation, current: true } as unknown as MediaCanvasHistoryComparisonInput;
  const initial = JSON.stringify(value), result = buildMediaCanvasHistoryComparison(value);
  expect(result.state).toBe('ready'); expect(result.counts.assetPinsChanged).toBeGreaterThan(0); expect(result.binding).toContain(fixture.incarnation); expect(JSON.stringify(value)).toBe(initial);
});
it('preserves card/group ordering differences and explicit default view options', () => {
  const before = definition(), after = definition(); before.cards = [card('First'), card('Second')]; after.cards = [card('Second'), card('First')];
  before.groups = [{ id: 'One', name: 'One', card_ids: [], collapsed: false }, { id: 'Two', name: 'Two', card_ids: [], collapsed: false }]; after.groups = [...before.groups].reverse();
  after.view_options = { grid: true, snap_step: 16 };
  expect(buildMediaCanvasHistoryComparison(input(before, after)).counts).toMatchObject({ cardOrderChanged: 1, groupOrderChanged: 1, viewOptionsChanged: 1 });
});
it('does not mutate frozen inputs, return their object references, use transport, or echo extension getter values', () => {
  const value = input(), initial = JSON.stringify(value); freeze(value); const fetch = vi.fn(); vi.stubGlobal('fetch', fetch);
  try { const result = buildMediaCanvasHistoryComparison(value); expect(result.state).toBe('ready'); expect(JSON.stringify(value)).toBe(initial); expect(fetch).not.toHaveBeenCalled(); }
  finally { vi.unstubAllGlobals(); }
  const d = definition(); d.cards = [card('Card')]; const mutable = input(d, definition()), result = buildMediaCanvasHistoryComparison(mutable);
  const removed = result.changes.find(change => change.kind === 'card-removed'); if (removed?.kind === 'card-removed') removed.before.position.x = 100;
  expect(mutable.base.definition.cards[0].position.x).toBe(0);
  const extension = input(), getter = vi.fn(() => 'SECRET_EXTENSION'); Object.defineProperty(extension.history, 'credential', { enumerable: true, get: getter });
  const invalid = buildMediaCanvasHistoryComparison(extension); expect(invalid.state).toBe('invalid'); expect(getter).not.toHaveBeenCalled(); expect(JSON.stringify(invalid)).not.toContain('SECRET_EXTENSION');
});
