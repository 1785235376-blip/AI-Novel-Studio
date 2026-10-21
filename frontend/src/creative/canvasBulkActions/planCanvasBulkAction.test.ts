import { describe, expect, it, vi } from 'vitest';
import { removeCanvasCard } from '../mediaCanvasGroups';
import { alignCanvasCards } from '../mediaCanvasSelection';
import { checkedCanvasDefinition } from '../studioCanvasViewClient';
import { input } from './canvasBulkActions.testFixtures';
import { planCanvasBulkAction, type CanvasBulkActionInput, type CanvasBulkOperation } from './planCanvasBulkAction';

function freeze(value: unknown) { if (value && typeof value === 'object') { Object.values(value).forEach(freeze); Object.freeze(value); } }
describe('original Canvas metadata bulk plans', () => {
  it('matches original removal helpers, retains groups and unselected metadata, and never mutates input', () => {
    const value = input(), original = structuredClone(value); freeze(value);
    const result = planCanvasBulkAction(value);
    expect(result.state).toBe('ready');
    expect(result.definition).toEqual(value.selectedIds.reduce(removeCanvasCard, value.definition));
    expect(result.definition).toEqual(checkedCanvasDefinition(result.definition));
    expect(result.definition?.cards).toEqual([value.definition.cards[2]]);
    expect(result.definition?.groups).toEqual([{ ...value.definition.groups![0] }, { ...value.definition.groups![1], card_ids: [] }]);
    expect(result.items.map(item => [item.cardId, item.beforeGroupId, item.afterGroupId, item.changed, item.after])).toEqual([
      ['Card0', 'Child', null, true, undefined], ['Card1', 'Child', null, true, undefined]]);
    expect(result.items.map(item => item.referenceState)).toEqual(['CURRENT_METADATA', 'STALE']);
    expect(value).toEqual(original); expect(result.definition?.viewport).toEqual(value.definition.viewport);
    expect(result.notes.join(' ')).toContain('不会生成或删除素材文件');
  });
  it.each([['ALIGN_LEFT', 'left'], ['ALIGN_TOP', 'top']] as const)('matches original %s positions, pins, viewport and membership', (operation, mode) => {
    const value = input(); value.operation = operation; const original = structuredClone(value); freeze(value);
    const result = planCanvasBulkAction(value);
    expect(result.state).toBe('ready'); expect(result.definition).toEqual(alignCanvasCards(value.definition, value.selectedIds, mode));
    expect(result.definition?.groups).toEqual(value.definition.groups);
    expect(result.definition?.cards[2]).toEqual(value.definition.cards[2]);
    expect(result.definition?.cards.map(card => card.asset)).toEqual(value.definition.cards.map(card => card.asset));
    expect(result.items.every(item => item.afterGroupId === item.beforeGroupId)).toBe(true); expect(value).toEqual(original);
  });
  it('returns detached results, and supports exactly 24 targets without truncating', () => {
    const value = input(); value.base = undefined; value.definition.groups = undefined;
    value.definition.cards = Array.from({ length: 25 }, (_, i) => ({ id: `Card${i}`, position: { x: i, y: i } }));
    value.selectedIds = value.definition.cards.slice(0, 24).map(card => card.id);
    const result = planCanvasBulkAction(value); expect(result.state).toBe('ready'); expect(result.items).toHaveLength(24);
    expect(result.definition?.cards.map(card => card.id)).toEqual(['Card24']);
    result.items[0].before.position.x = 999; expect(value.definition.cards[0].position.x).toBe(0);
    value.selectedIds.push('Card24'); expect(planCanvasBulkAction(value).state).toBe('invalid');
  });
  it.each([
    ['empty', (v: CanvasBulkActionInput) => { v.selectedIds = []; }, 'invalid'],
    ['duplicate', (v: CanvasBulkActionInput) => { v.selectedIds = ['Card0', 'Card0']; }, 'invalid'],
    ['missing', (v: CanvasBulkActionInput) => { v.selectedIds = ['Card0', 'Missing']; }, 'missing'],
    ['malformed id', (v: CanvasBulkActionInput) => { v.selectedIds = ['../Card0']; }, 'invalid'],
    ['single alignment', (v: CanvasBulkActionInput) => { v.operation = 'ALIGN_LEFT'; v.selectedIds = ['Card0']; }, 'invalid'],
    ['unsupported operation', (v: CanvasBulkActionInput) => { v.operation = 'EXECUTE' as CanvasBulkOperation; }, 'invalid'],
    ['missing owner', (v: CanvasBulkActionInput) => { v.owner = undefined; }, 'missing'],
    ['invalid incarnation', (v: CanvasBulkActionInput) => { v.owner!.incarnation = ''; }, 'invalid'],
    ['cross project', (v: CanvasBulkActionInput) => { v.base!.project_id = 'Other'; }, 'stale'],
    ['cross scope', (v: CanvasBulkActionInput) => { v.base!.scope = { mode: 'collaboration', novel_id: 'Project', workspace_id: 'Work', storyline_id: 'Story', branch_id: 'Branch' }; }, 'stale'],
    ['unsupported state', (v: CanvasBulkActionInput) => { (v.base!.reference_states[0] as any).state = 'BINARY_VERIFIED'; }, 'invalid'],
    ['missing state', (v: CanvasBulkActionInput) => { v.base!.reference_states.pop(); }, 'invalid'],
    ['wrong state pin', (v: CanvasBulkActionInput) => { v.base!.reference_states[0] = { card_id: 'Card0', state: 'UNAVAILABLE' }; }, 'invalid'],
    ['execution authority', (v: CanvasBulkActionInput) => { (v.base as any).execution_authority = true; }, 'invalid'],
    ['invalid draft', (v: CanvasBulkActionInput) => { v.definition.cards[0].position.x = NaN; }, 'invalid'],
    ['invalid base', (v: CanvasBulkActionInput) => { v.base!.definition.cards[0].position.y = Infinity; }, 'invalid'],
  ])('fails closed for %s without partial output', (_name, mutate, state) => {
    const value = input(); mutate(value); const result = planCanvasBulkAction(value);
    expect(result.state).toBe(state); expect(result.binding).toBeNull(); expect(result.items).toEqual([]); expect(result.definition).toBeUndefined();
  });
  it('does not read stale input getters or a mismatched scope content getter', () => {
    const getter = vi.fn(() => { throw new Error('must not read'); });
    const value = Object.fromEntries(['definition', 'base', 'owner', 'selectedIds', 'operation'].map(key => [key, undefined]));
    for (const key of Object.keys(value)) Object.defineProperty(value, key, { get: getter });
    const stale = Object.create(null); Object.defineProperties(stale, Object.getOwnPropertyDescriptors(value)); stale.current = false;
    expect(planCanvasBulkAction(stale).state).toBe('stale'); expect(getter).not.toHaveBeenCalled();
    const changed = input(); changed.base!.project_id = 'Other'; Object.defineProperty(changed.base, 'definition', { get: getter });
    expect(planCanvasBulkAction(changed).state).toBe('stale'); expect(getter).not.toHaveBeenCalled();
  });
  it('distinguishes unavailable pins and unverified draft pins without borrowing the base current status', () => {
    const value = input(); delete value.definition.cards[0].asset; value.base = undefined;
    let result = planCanvasBulkAction(value); expect(result.items.map(item => item.referenceState)).toEqual(['UNAVAILABLE', 'UNVERIFIED']);
    const changed = input(); changed.definition.cards[0].asset!.version++;
    result = planCanvasBulkAction(changed); expect(result.items[0].referenceState).toBe('UNVERIFIED'); expect(result.items[0].filename).toBeUndefined();
  });
  it('supports a precisely matching collaboration scope', () => {
    const value = input(); value.owner = { ...value.owner!, mode: 'collaboration', actorWorkspaceId: 'Work', workspaceId: 'Work', storylineId: 'Story', branchId: 'Branch' };
    value.base!.scope = { mode: 'collaboration', novel_id: 'Project', workspace_id: 'Work', storyline_id: 'Story', branch_id: 'Branch' };
    expect(planCanvasBulkAction(value).state).toBe('ready');
    value.owner.branchId = 'Other'; expect(planCanvasBulkAction(value).state).toBe('stale');
  });
  it('rejects a no-op rather than emitting a misleading draft edit', () => {
    const value = input(); value.operation = 'ALIGN_LEFT'; value.definition.cards[1].position.x = value.definition.cards[0].position.x;
    expect(planCanvasBulkAction(value).state).toBe('invalid');
  });
  it.each([
    ['incarnation', (v: CanvasBulkActionInput) => { v.owner!.incarnation = 'file:replacement'; }],
    ['actor', (v: CanvasBulkActionInput) => { v.owner!.actorId = 'OtherAuthor'; }],
    ['base id', (v: CanvasBulkActionInput) => { v.base!.id = 'OtherCanvas'; }],
    ['base version', (v: CanvasBulkActionInput) => { v.base!.version++; }],
    ['base digest', (v: CanvasBulkActionInput) => { v.base!.definition_digest = 'b'.repeat(64); }],
    ['base pins', (v: CanvasBulkActionInput) => { v.base!.definition.cards[2].asset!.version++; }],
    ['reference status', (v: CanvasBulkActionInput) => { v.base!.reference_states[0] = { card_id: 'Card0', state: 'STALE' }; }],
    ['unselected draft', (v: CanvasBulkActionInput) => { v.definition.cards[2].position.x++; }],
    ['draft pin', (v: CanvasBulkActionInput) => { v.definition.cards[1].asset!.digest = 'c'.repeat(64); }],
    ['selection order', (v: CanvasBulkActionInput) => { v.selectedIds.reverse(); }],
    ['operation', (v: CanvasBulkActionInput) => { v.operation = 'ALIGN_TOP'; }],
  ])('binds the full %s metadata', (_name, mutate) => {
    const value = input(), original = planCanvasBulkAction(value); mutate(value);
    const next = planCanvasBulkAction(value); expect(next.state).toBe('ready'); expect(next.binding).not.toBe(original.binding);
  });
});
