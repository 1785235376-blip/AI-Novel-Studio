// [HERMIA-FE-20261025 UWPORT-P1-1/P3] App-level last-chapter gate + status hint, extracted so they are unit-testable.
import {useEffect, useState, type ReactNode} from 'react';

export interface GateInput { isLoading: boolean; isError: boolean; bootstrapActorId?: string | null; actorId?: string | null }
/** Identity is undetermined while bootstrap loads, after it errored (token/scope present ⇒ query enabled), or while the
 *  store actor has not caught up with the bootstrap actor. */
export function lastChapterIdentityPending({isLoading, isError, bootstrapActorId, actorId}: GateInput): boolean {
  return isLoading || isError || (!!bootstrapActorId && bootstrapActorId !== actorId);
}
export const LASTPOS_TIMEOUT_MS = 8000;
type T = (k: 'status.lastPosSession' | 'status.lastPosPending' | 'status.lastPosTimeout' | 'status.lastPosFailed') => string;
function PendingHint({failed, t}: {failed: boolean; t: T}) {
  const [late, setLate] = useState(false);
  useEffect(() => { const h = setTimeout(() => setLate(true), LASTPOS_TIMEOUT_MS); return () => clearTimeout(h); }, []);
  const k = failed ? 'status.lastPosFailed' : late ? 'status.lastPosTimeout' : 'status.lastPosPending';
  return <span data-testid="dui-lastpos-pending" data-state={failed ? 'failed' : late ? 'timeout' : 'loading'} role="status">{` · ${t(k)}`}</span>;
}
export function lastPosStatus(novelId: string, mode: 'real' | 'session' | 'pending', failed: boolean, t: T): ReactNode {
  if (!novelId) return null;
  if (mode === 'session') return <span data-testid="dui-lastpos-session">{` · ${t('status.lastPosSession')}`}</span>;
  if (mode === 'pending') return <PendingHint failed={failed} t={t} />;
  return null;
}
