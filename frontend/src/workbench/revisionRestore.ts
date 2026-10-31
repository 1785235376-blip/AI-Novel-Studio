/**
 * [HERMIA-FE-20261022 H-P0-02] Chapter-scoped revision restore confirmation.
 * Binds lifecycle epoch + chapter identity + expectedCurrentVersion + revisionVersion.
 * A→B→A chapter/project switch invalidates an old confirmation (same as §11.2).
 * Does not call the network; callers still use api.restore + existing ScopedRevisionHistory fences.
 */
import {LifecycleTracker, bindConfirmation, checkConfirmation, type ConfirmationBinding, type LifecycleToken} from './lifecycle';

export interface RestoreTarget {
  novelId: string;
  chapterId: string;
  revisionVersion: number;
  expectedCurrentVersion: number;
}

export function restoreLifecycleContext(t: RestoreTarget) {
  return {projectId: t.novelId, documentId: t.chapterId, jobId: `restore:${t.chapterId}`};
}

export function bindRestoreConfirmation(token: LifecycleToken, t: RestoreTarget): ConfirmationBinding {
  return bindConfirmation(token, 'novel.revision.restore', t.chapterId, String(t.expectedCurrentVersion), {
    novelId: t.novelId, chapterId: t.chapterId,
    revisionVersion: t.revisionVersion, expectedCurrentVersion: t.expectedCurrentVersion,
  });
}

export type RestoreGate =
  | {ok: true}
  | {ok: false; reason: string};

/** Re-check at confirm time AND again immediately before applying a late result. */
export function gateRestore(binding: ConfirmationBinding, tracker: LifecycleTracker, t: RestoreTarget): RestoreGate {
  const c = checkConfirmation(
    binding, tracker, 'novel.revision.restore', t.chapterId, String(t.expectedCurrentVersion),
    {novelId: t.novelId, chapterId: t.chapterId, revisionVersion: t.revisionVersion, expectedCurrentVersion: t.expectedCurrentVersion},
  );
  if (!c.ok) return {ok: false, reason: `恢复确认已失效：${c.reason}（请重新打开版本历史并确认）`};
  return {ok: true};
}

export function syncRestoreLifecycle(tracker: LifecycleTracker, t: RestoreTarget): LifecycleToken {
  return tracker.update(restoreLifecycleContext(t));
}
