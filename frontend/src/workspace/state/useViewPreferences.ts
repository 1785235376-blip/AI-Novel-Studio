/**
 * [HERMIA-FE-20261024 VW-M1] React binding for the view-preference adapter.
 * One adapter per scope identity (user/project/instance); switching scope creates a new adapter synchronously during
 * render, so the first frame of a project already reads its own preferences (no flash of another project's pan/zoom).
 * Session-only adapters are cached per scope key in this hook instance so A→B→A keeps A's session view.
 */
import {useMemo, useRef} from 'react';
import type {LayoutScope, StorageLike} from '../../workbench/layout';
import {createViewPreferences, type ViewPrefs} from './viewPreferences';

export interface UseViewPreferencesOptions {
  scope: LayoutScope | null;
  storage: StorageLike | null;
  persist: boolean;
  /** Distinguishes session caches when scope is null (e.g. the preview's project id). Never persisted. */
  sessionKey?: string | null;
}
export function useViewPreferences(o: UseViewPreferencesOptions): ViewPrefs {
  const scopeId = o.scope ? `${o.scope.userId}\u0000${o.scope.projectId}\u0000${o.scope.projectInstanceId}` : `session\u0000${o.sessionKey ?? ''}`;
  const current = useRef(scopeId); current.current = scopeId;
  const cache = useRef(new Map<string, ViewPrefs>());
  return useMemo(() => {
    const id = scopeId;
    const k = `${id}\u0000${o.persist ? 1 : 0}`;
    const hit = cache.current.get(k); if (hit) return hit;
    const p = createViewPreferences({scope: o.scope, storage: o.storage, persist: o.persist, isCurrent: () => current.current === id});
    cache.current.set(k, p); return p;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [scopeId, o.persist, o.storage]);
}
