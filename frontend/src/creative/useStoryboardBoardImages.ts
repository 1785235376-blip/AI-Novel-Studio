import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { useStudio } from '../store';
import type { StoryboardReceipt, StoryboardShot } from './studioStoryboardContract';
import { loadStoryboardImage, readStoryboardImageReceipt, serializeStoryboardImage, storyboardImageKey, storyboardImageProblem,
  StoryboardImageError, STORYBOARD_IMAGE_WINDOW, type StoryboardImageAccess } from './storyboardImagePreview';

type Entry = { state: 'QUEUED' | 'LOADING' | 'READY' | 'FAILED'; url?: string; problem?: string };
type Session = { token: object; origin: object; page: number; abort: AbortController; urls: Set<string>; receipt?: StoryboardReceipt; entries: Map<string, Entry>; comparison?: { shotId: string; selection: object; entry: Entry } };
type Props = { access?: StoryboardImageAccess; active: boolean; dirty: boolean; busy: boolean; selectedId?: string };
const studioIdentity = () => { const owner = useStudio.getState(); return JSON.stringify([owner.novelId, owner.sessionToken, owner.actor?.id, owner.actor?.workspaceId, owner.scope?.workspaceId, owner.scope?.projectId, owner.scope?.storylineId, owner.scope?.branchId]); };
const hostIdentity = () => { const owner = useLocalHostSession.getState(); return JSON.stringify([owner.token, owner.actorId, owner.epoch]); };
/** Read-only view state. Formal ownership stays with Creative/Asset, selection stays with CreativeCanvas. */
export function useStoryboardBoardImages(props: Props) {
  const latest = useRef(props); latest.current = props;
  const authority = useRef({ studio: studioIdentity(), host: hostIdentity(), revoked: false });
  const values = [props.access?.client, props.access?.studio, props.access?.document, props.access?.available, props.active, props.dirty, props.access?.isCurrent()];
  const fence = useRef({ values, token: {} });
  if (values.some((value, i) => !Object.is(value, fence.current.values[i]))) fence.current = { values, token: {} };
  const origin = fence.current.token;
  const selected = useRef({ id: props.selectedId, token: {} });
  if (selected.current.id !== props.selectedId) selected.current = { id: props.selectedId, token: {} };
  const selectedToken = selected.current.token;
  const alive = useRef(true), session = useRef<Session>();
  const [, update] = useState(0), [problem, setProblem] = useState('');
  const notify = () => { if (alive.current) update(value => value + 1); };
  const authorityCurrent = () => !authority.current.revoked && authority.current.studio === studioIdentity() && authority.current.host === hostIdentity();
  const admitted = () => alive.current && authorityCurrent() && latest.current.active && !latest.current.dirty && !!latest.current.access?.available && latest.current.access.isCurrent();
  const current = (owner: Session) => admitted() && session.current === owner && fence.current.token === owner.origin && !owner.abort.signal.aborted;
  function release(owner?: Session) {
    if (!owner) return;
    owner.abort.abort(); for (const url of owner.urls) URL.revokeObjectURL(url); owner.urls.clear(); owner.entries.clear(); owner.comparison = undefined; owner.receipt = undefined;
  }
  function close(message = '') { const old = session.current; session.current = undefined; release(old); setProblem(message); notify(); }
  function failure(owner: Session, reason: unknown) {
    if (!current(owner)) return;
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) { close(storyboardImageProblem(reason)); latest.current.access?.onDenied(); }
    else if (reason instanceof ApiError && [404, 409].includes(reason.status)) close(storyboardImageProblem(reason));
    else if (reason instanceof StoryboardImageError && ['SOURCE_CHANGED', 'ASSET_CHANGED', 'INTEGRITY', 'TIMEOUT'].includes(reason.code)) close(reason.message);
  }
  function begin(page: number) {
    if (!admitted() || latest.current.busy) return;
    close();
    const access = latest.current.access!;
    const total = Math.ceil(access.document.shots.length / STORYBOARD_IMAGE_WINDOW);
    if (page < 0 || page >= Math.max(1, total)) return;
    const owner: Session = { token: {}, origin: fence.current.token, page, abort: new AbortController(), urls: new Set(), entries: new Map() };
    session.current = owner; notify();
    void serializeStoryboardImage(async () => {
      if (!current(owner)) return;
      try {
        owner.receipt = await readStoryboardImageReceipt(access, () => current(owner), owner.abort.signal);
        if (current(owner)) notify();
      } catch (reason) { if (current(owner)) { failure(owner, reason); if (current(owner)) close(storyboardImageProblem(reason)); } }
    });
  }
  const visible = session.current && current(session.current) ? session.current : undefined;
  const receipt = visible?.receipt;
  // Display order is the original board order; receipt lookup supplies the exact saved pin.
  const ids = visible ? props.access!.document.shots.slice(visible.page * STORYBOARD_IMAGE_WINDOW, (visible.page + 1) * STORYBOARD_IMAGE_WINDOW).map(row => row.id) : [];
  const rows = receipt ? ids.map(id => receipt.shots.find(row => row.shot_id === id)).filter((row): row is StoryboardShot => !!row) : [];
  useLayoutEffect(() => {
    if (session.current && !current(session.current)) close();
  }, [origin]);
  useLayoutEffect(() => {
    const owner = session.current, old = owner?.comparison;
    if (old && old.selection !== selectedToken) {
      if (old.entry.url) { URL.revokeObjectURL(old.entry.url); owner!.urls.delete(old.entry.url); }
      owner!.comparison = undefined; notify();
    }
  }, [selectedToken]);
  useLayoutEffect(() => {
    alive.current = true;
    const changed = () => {
      if (!authorityCurrent()) { authority.current.revoked = true; close('身份、项目或会话已变化。请重新打开工作区后读取图片。'); return; }
      const owner = session.current; if (owner && !current(owner)) close();
    };
    const owner = useStudio.subscribe(changed), host = useLocalHostSession.subscribe(changed);
    const hidden = () => { if (document.visibilityState === 'hidden' && session.current) close('离开页面后已释放图片。返回时请重新核验已保存版本。'); };
    const blurred = () => { if (session.current) close('窗口失去焦点后已释放图片。请重新核验已保存版本。'); };
    document.addEventListener('visibilitychange', hidden); window.addEventListener('blur', blurred);
    return () => { alive.current = false; const previous = session.current; session.current = undefined; release(previous); owner(); host(); document.removeEventListener('visibilitychange', hidden); window.removeEventListener('blur', blurred); };
  }, []);
  useEffect(() => {
    const owner = session.current, access = latest.current.access;
    if (!owner?.receipt || !access || !current(owner)) return;
    const captured = owner.receipt;
    for (const row of rows) {
      if (!row.image_asset) continue;
      const key = storyboardImageKey(row);
      if (owner.entries.has(key)) continue;
      owner.entries.set(key, { state: 'QUEUED' });
      void serializeStoryboardImage(async () => {
        if (!current(owner)) return;
        owner.entries.set(key, { state: 'LOADING' }); notify();
        try {
          const blob = await loadStoryboardImage(access, captured, row, 320, () => current(owner), owner.abort.signal);
          if (!current(owner)) return;
          const url = URL.createObjectURL(blob); owner.urls.add(url); owner.entries.set(key, { state: 'READY', url }); notify();
        } catch (reason) { failure(owner, reason); if (current(owner)) { owner.entries.set(key, { state: 'FAILED', problem: storyboardImageProblem(reason) }); notify(); } }
      });
    }
  }, [receipt, visible?.token]);
  useEffect(() => {
    const owner = session.current, access = latest.current.access;
    if (!owner?.receipt || !access || !current(owner)) return;
    const row = rows.find(row => row.shot_id === latest.current.selectedId);
    if (!row?.image_asset || owner.comparison?.selection === selectedToken) return;
    const captured = owner.receipt, selection = selectedToken;
    owner.comparison = { shotId: row.shot_id, selection, entry: { state: 'QUEUED' } }; notify();
    const comparisonCurrent = () => current(owner) && selected.current.token === selection && owner.comparison?.selection === selection;
    void serializeStoryboardImage(async () => {
      if (!comparisonCurrent()) return;
      owner.comparison!.entry = { state: 'LOADING' }; notify();
      try {
        const blob = await loadStoryboardImage(access, captured, row, 1024, comparisonCurrent, owner.abort.signal);
        if (!comparisonCurrent()) return;
        const url = URL.createObjectURL(blob); owner.urls.add(url); owner.comparison!.entry = { state: 'READY', url }; notify();
      } catch (reason) { failure(owner, reason); if (comparisonCurrent()) { owner.comparison!.entry = { state: 'FAILED', problem: storyboardImageProblem(reason) }; notify(); } }
    });
  }, [receipt, visible?.token, selectedToken]);
  const comparison = visible?.comparison?.selection === selectedToken ? visible.comparison : undefined;
  return {
    open: !!visible, loading: !!visible && !receipt, receipt, rows, ids, problem,
    page: visible?.page ?? 0, pages: Math.ceil((props.access?.document.shots.length ?? 0) / STORYBOARD_IMAGE_WINDOW),
    available: admitted(), canStart: admitted() && !props.busy,
    show: () => begin(visible?.page ?? Math.max(0, Math.floor((props.access?.document.shots.findIndex(row => row.id === props.selectedId) ?? 0) / STORYBOARD_IMAGE_WINDOW))),
    hide: () => close(), go: begin,
    thumbnail: (shotId: string) => { const row = rows.find(row => row.shot_id === shotId); return row?.image_asset ? visible?.entries.get(storyboardImageKey(row)) : undefined; },
    selected: rows.find(row => row.shot_id === props.selectedId), comparison: comparison?.entry,
  };
}
export type StoryboardBoardImages = ReturnType<typeof useStoryboardBoardImages>;
