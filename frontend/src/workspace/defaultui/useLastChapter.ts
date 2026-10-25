// [HERMIA-FE-20261025 UWPORT-S1] Replaces "default to first chapter" in the default UI with "last chapter if it still exists".
import {useEffect, useMemo} from 'react';
import {resolveWorkspaceIdentity} from '../state/scopeLease';
import {pickChapter, recallChapter, rememberChapter} from './lastPosition';

function storage(): Storage | null { try { return window.localStorage; } catch { return null; } }
export interface LastChapterInput {
  actorId?: string | null; scope?: {workspaceId?: string; projectId?: string; storylineId?: string; branchId?: string} | null;
  novelId: string; chapterId: string; rows: readonly {id: string}[] | undefined; setChapter: (id: string) => void;
  /** [UWPORT-P0] collaboration bootstrap still deciding the actor: neither pick by memory nor write (Vera reopen race). */
  identityPending?: boolean;
}
export function useLastChapter({actorId, scope, novelId, chapterId, rows, setChapter, identityPending = false}: LastChapterInput): 'real' | 'session' | 'pending' {
  const id = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: scope ?? null, projectId: novelId || null}),
    [actorId, scope?.workspaceId, scope?.projectId, scope?.storylineId, scope?.branchId, novelId]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (identityPending || chapterId || !rows) return;
    const next = pickChapter(rows, recallChapter(storage(), id));
    if (next) setChapter(next);
  }, [rows, chapterId, id, identityPending]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (!identityPending && chapterId && rows?.some(r => r.id === chapterId)) rememberChapter(storage(), id, chapterId);
  }, [chapterId, rows, id, identityPending]);
  return identityPending ? 'pending' : id.kind;
}
