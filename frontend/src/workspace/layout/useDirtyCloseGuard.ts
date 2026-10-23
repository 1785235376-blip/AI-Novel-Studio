/**
 * [HERMIA-FE-20261023 M1] Close guard for panels with unsaved edits (contract §2.6).
 * - No dirty source → close immediately (M1-19).
 * - Dirty → caller shows 保存 / 放弃 / 取消 (M1-20..22).
 * - Save failure keeps the panel open and reports the real error; never reports success (M1-25).
 * - Late save resolution after unmount or after a newer request is ignored (M1-24).
 */
import {useCallback, useEffect, useRef, useState} from 'react';

export interface DirtySource {
  isDirty(): boolean;
  /** Real save. Must reject on failure. Local draft caching is NOT a save. */
  save(): Promise<void>;
  /** Drop only this panel's unsaved edits. */
  discard(): void;
}
export interface PendingClose { panelId: string; saving: boolean; error: string | null; }

export function useDirtyCloseGuard(close: (panelId: string) => void) {
  const sources = useRef(new Map<string, DirtySource>());
  const [pending, setPending] = useState<PendingClose | null>(null);
  const mounted = useRef(true);
  const seq = useRef(0);
  const closeRef = useRef(close); closeRef.current = close;
  useEffect(() => { mounted.current = true; return () => { mounted.current = false; seq.current++; }; }, []);

  const register = useCallback((panelId: string, src: DirtySource) => {
    sources.current.set(panelId, src);
    return () => { if (sources.current.get(panelId) === src) sources.current.delete(panelId); };
  }, []);

  const requestClose = useCallback((panelId: string) => {
    const src = sources.current.get(panelId);
    if (!src || !src.isDirty()) { closeRef.current(panelId); return 'closed' as const; }
    setPending({panelId, saving: false, error: null});
    return 'needs-decision' as const;
  }, []);

  const cancel = useCallback(() => { seq.current++; setPending(null); }, []);

  // [HERMIA-FE-20261023 M1] side effects run outside the state updater (updaters must stay pure).
  const pendingRef = useRef(pending); pendingRef.current = pending;
  const discard = useCallback(() => {
    const p = pendingRef.current;
    seq.current++; setPending(null);
    if (p) { sources.current.get(p.panelId)?.discard(); closeRef.current(p.panelId); }
  }, []);

  const save = useCallback(async () => {
    const p = pending; if (!p || p.saving) return;
    const src = sources.current.get(p.panelId);
    if (!src) { setPending(null); closeRef.current(p.panelId); return; }
    const my = ++seq.current;
    setPending({...p, saving: true, error: null});
    try {
      await src.save();
      if (!mounted.current || my !== seq.current) return;
      setPending(null); closeRef.current(p.panelId);
    } catch (e) {
      if (!mounted.current || my !== seq.current) return;
      setPending({panelId: p.panelId, saving: false, error: e instanceof Error ? e.message : String(e)});
    }
  }, [pending]);

  return {register, requestClose, pending, save, discard, cancel};
}
