// @vitest-environment jsdom
import {beforeEach, describe, expect, it} from 'vitest';
import {incarnationFromOverview, observeIncarnation, incarnationLedgerKey} from './projectIncarnation';
import {viewPrefsKey} from './viewPreferences';

/** [HERMIA-FE-CONTRACTS G-PURGE-1 incarnation] mock/contract evidence only. */
const s = {userId: 'u1', projectId: 'n1', projectInstanceId: 'w/s/b'};
beforeEach(() => { localStorage.clear(); localStorage.setItem(viewPrefsKey(s), '{}'); localStorage.setItem(viewPrefsKey({...s, userId: 'u2'}), '{}'); });

describe('project incarnation ledger', () => {
  it('first sighting records without purging; same keeps; changed purges own geometry only', () => {
    expect(observeIncarnation(localStorage, 'u1', 'n1', 'file:A').kind).toBe('first');
    expect(localStorage.getItem(viewPrefsKey(s))).not.toBeNull();
    expect(observeIncarnation(localStorage, 'u1', 'n1', 'file:A').kind).toBe('same');
    const r = observeIncarnation(localStorage, 'u1', 'n1', 'file:B');
    expect(r.kind).toBe('changed');
    expect(localStorage.getItem(viewPrefsKey(s))).toBeNull();
    expect(localStorage.getItem(viewPrefsKey({...s, userId: 'u2'}))).not.toBeNull();
    expect(localStorage.getItem(incarnationLedgerKey('u1', 'n1'))).toBe('file:B');
  });
  it('unknown incarnation, missing identity or no storage never purges nor records', () => {
    observeIncarnation(localStorage, 'u1', 'n1', 'file:A');
    for (const bad of [undefined, null, '', ' x', 42, 'a'.repeat(300)]) expect(observeIncarnation(localStorage, 'u1', 'n1', bad).kind).toBe('skipped');
    expect(observeIncarnation(localStorage, '', 'n1', 'file:B').kind).toBe('skipped');
    expect(observeIncarnation(null, 'u1', 'n1', 'file:B').kind).toBe('skipped');
    expect(localStorage.getItem(viewPrefsKey(s))).not.toBeNull();
    expect(localStorage.getItem(incarnationLedgerKey('u1', 'n1'))).toBe('file:A');
  });
  it('extracts incarnation only from the matching project overview', () => {
    expect(incarnationFromOverview({project: {id: 'n1', incarnation: 'file:A'}}, 'n1')).toBe('file:A');
    expect(incarnationFromOverview({project: {id: 'n2', incarnation: 'file:A'}}, 'n1')).toBeNull();
    expect(incarnationFromOverview({project: {id: 'n1'}}, 'n1')).toBeNull();
    expect(incarnationFromOverview(null, 'n1')).toBeNull();
  });
});
