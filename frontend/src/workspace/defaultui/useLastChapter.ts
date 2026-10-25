// [HERMIA-FE-20261025 UWPORT-S1] Replaces "default to first chapter" in the default UI with "last chapter if it still exists".
import {useEffect, useMemo, useRef} from 'react';
import {resolveWorkspaceIdentity} from '../state/scopeLease';
import {pickChapter, recallChapter, rememberChapter} from './lastPosition';

function storage(): Storage | null { try { return window.localStorage; } catch { return null; } }
export interface LastChapterInput {
  actorId?: string | null; scope?: {workspaceId?: string; projectId?: string; storylineId?: string; branchId?: string} | null;
  novelId: string; chapterId: string; rows: readonly {id: string}[] | undefined; setChapter: (id: string) => void;
  /** [UWPORT-P0] collaboration bootstrap still deciding the actor (or failed with a token/scope): neither pick by memory nor write. */
  identityPending?: boolean;
}
/**
 * [UWPORT-P1-1] Each selected chapter carries an "owner": the identity key it was chosen under (auto pick or explicit
 * user click). Writes happen only when the owner is the current real identity, so a chapter auto-picked in session mode
 * (e.g. after a failed bootstrap) is never written to the real user once identity recovers, and A's chapter is never
 * written to B's key. When identity changes under an auto-picked (or other-real-identity) chapter we re-pick for the new
 * identity (P2: A→B resets the chapter instead of carrying A's ch3 over).
 */
export function useLastChapter({actorId, scope, novelId, chapterId, rows, setChapter, identityPending = false}: LastChapterInput): 'real' | 'session' | 'pending' {
  const id = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: scope ?? null, projectId: novelId || null}),
    [actorId, scope?.workspaceId, scope?.projectId, scope?.storylineId, scope?.branchId, novelId]); // eslint-disable-line react-hooks/exhaustive-deps
  const auto = useRef<{chapter: string; key: string} | null>(null);
  const owner = useRef<{chapter: string; key: string | null; auto: boolean} | null>(null);
  // Attribute the current chapter to an owner (runs before the pick/write effects below).
  if (chapterId && owner.current?.chapter !== chapterId) {
    owner.current = auto.current?.chapter === chapterId
      ? {chapter: chapterId, key: auto.current.key, auto: true}
      : {chapter: chapterId, key: identityPending ? null : id.key, auto: false};
  } else if (!chapterId) owner.current = null;
  const o = owner.current;
  const foreign = !!o && !identityPending && o.key !== id.key && (o.auto || (o.key?.startsWith('real\u0000') ?? false));
  useEffect(() => {
    if (identityPending || !rows) return;
    if (chapterId && !foreign) return;
    const next = pickChapter(rows, recallChapter(storage(), id));
    if (!next) return;
    auto.current = {chapter: next, key: id.key};
    if (next === chapterId) owner.current = {chapter: next, key: id.key, auto: true};
    else setChapter(next);
  }, [rows, chapterId, id, identityPending, foreign]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (identityPending || !chapterId || !rows?.some(r => r.id === chapterId)) return;
    const cur = owner.current;
    if (!cur || cur.chapter !== chapterId || cur.key !== id.key) return;
    rememberChapter(storage(), id, chapterId);
  }, [chapterId, rows, id, identityPending, foreign]);
  return identityPending ? 'pending' : id.kind;
}
