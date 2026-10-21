/**
 * [HERMIA-FE-20261022 H-P0-02] Chapter-scoped restore confirm + lifecycle epoch.
 */
import {describe, expect, it} from 'vitest';
import {LifecycleTracker} from './lifecycle';
import {
  bindRestoreConfirmation, gateRestore, syncRestoreLifecycle, type RestoreTarget,
} from './revisionRestore';

const t = (over: Partial<RestoreTarget> = {}): RestoreTarget => ({
  novelId: 'n1', chapterId: 'c1', revisionVersion: 3, expectedCurrentVersion: 7, ...over,
});

describe('revisionRestore H-P0-02', () => {
  it('binds and gates while lifecycle is current', () => {
    const life = new LifecycleTracker();
    const target = t();
    const token = syncRestoreLifecycle(life, target);
    const binding = bindRestoreConfirmation(token, target);
    expect(gateRestore(binding, life, target)).toEqual({ok: true});
  });

  it('rejects after chapter A→B switch (lifecycle invalidate)', () => {
    const life = new LifecycleTracker();
    const a = t({chapterId: 'cA'});
    const token = syncRestoreLifecycle(life, a);
    const binding = bindRestoreConfirmation(token, a);
    // switch to chapter B
    syncRestoreLifecycle(life, t({chapterId: 'cB'}));
    const gate = gateRestore(binding, life, a);
    expect(gate.ok).toBe(false);
    if (!gate.ok) expect(gate.reason).toContain('lifecycle-changed');
  });

  it('rejects A→B→A (ABA): returning to A still has new epoch', () => {
    const life = new LifecycleTracker();
    const a = t({chapterId: 'cA'});
    const token = syncRestoreLifecycle(life, a);
    const binding = bindRestoreConfirmation(token, a);
    syncRestoreLifecycle(life, t({chapterId: 'cB'}));
    syncRestoreLifecycle(life, a); // back to A — new epoch
    const gate = gateRestore(binding, life, a);
    expect(gate.ok).toBe(false);
  });

  it('rejects when expectedCurrentVersion drifts', () => {
    const life = new LifecycleTracker();
    const target = t({expectedCurrentVersion: 7});
    const token = syncRestoreLifecycle(life, target);
    const binding = bindRestoreConfirmation(token, target);
    const drifted = t({expectedCurrentVersion: 8});
    // same lifecycle context (same chapter) but version in check differs
    const gate = gateRestore(binding, life, drifted);
    expect(gate.ok).toBe(false);
    if (!gate.ok) expect(gate.reason).toMatch(/version-changed|input-changed/);
  });

  it('rejects forced invalidate (identity/store change)', () => {
    const life = new LifecycleTracker();
    const target = t();
    const token = syncRestoreLifecycle(life, target);
    const binding = bindRestoreConfirmation(token, target);
    life.invalidate();
    expect(gateRestore(binding, life, target).ok).toBe(false);
  });
});
