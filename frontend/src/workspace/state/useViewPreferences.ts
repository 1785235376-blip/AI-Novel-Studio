/**
 * [HERMIA-FE-20261024 VW-M1] React binding for the view-preference adapter.
 * [HERMIA-FE-20261025 U1-M1] One adapter PER ACTIVATION (lease), not per scope: switching scope retires the previous
 * adapter's lease synchronously during render, so A→B→A gives A a fresh adapter and every late callback bound to the
 * first A adapter is dropped. Session-only values carry over A→B→A through a doc snapshot (never written to storage).
 */
import {useEffect, useMemo, useRef, useState} from 'react';
import type {LayoutScope, StorageLike} from '../../workbench/layout';
import {createViewPreferences, type ViewPrefs, type ViewPrefsDoc} from './viewPreferences';
import {LeaseHolder} from './scopeLease';

export interface UseViewPreferencesOptions {
  scope: LayoutScope | null;
  storage: StorageLike | null;
  persist: boolean;
  /** Distinguishes session caches when scope is null (e.g. the preview's project id). Never persisted. */
  sessionKey?: string | null;
  /** [HERMIA-FE-CONTRACTS fix1] project.incarnation: a new incarnation is a new activation (fresh adapter read from the
   * just-purged storage, no snapshot seed from the old project), so the old in-memory viewport is never written back. */
  incarnation?: string | null;
}
export function useViewPreferences(o: UseViewPreferencesOptions): ViewPrefs {
  const scopeId = o.scope ? `${o.scope.userId}\u0000${o.scope.projectId}\u0000${o.scope.projectInstanceId}` : `session\u0000${o.sessionKey ?? ''}`;
  const k = `${scopeId}\u0000${o.persist ? 1 : 0}\u0000${o.incarnation ?? ''}`;
  const holder = useRef(new LeaseHolder());
  const seeds = useRef(new Map<string, ViewPrefsDoc>());
  const last = useRef<{k: string; p: ViewPrefs} | null>(null);
  // [HERMIA-FE-20261025 U1fix] MUST-FIX 2 root cause: React StrictMode runs mount→cleanup→mount; the unmount cleanup
  // retired the only lease, so every later write was rejected as "not current". Re-mount now re-activates (new lease).
  const [gen, setGen] = useState(0);
  const prefs = useMemo(() => {
    if (last.current) seeds.current.set(last.current.k, last.current.p.snapshot());
    const lease = holder.current.current(k);
    const p = createViewPreferences({scope: o.scope, storage: o.storage, persist: o.persist, isCurrent: lease.isCurrent, seed: seeds.current.get(k) ?? null});
    last.current = {k, p};
    return p;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [k, o.storage, gen]);
  useEffect(() => {
    if (!holder.current.isLive()) setGen(g => g + 1);
    return () => holder.current.invalidate();
  }, []);
  return prefs;
}
