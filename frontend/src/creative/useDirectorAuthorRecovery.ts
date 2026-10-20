import { useEffect, useRef, useState } from 'react';
import { directorAuthorDraftKey, encodeDirectorAuthorDraft, readDirectorAuthorDraft, type DirectorAuthorLocalDraft } from './directorAuthorLocalDraft';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { CreativeDocument, CreativeInput } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';

type Props = { owner?: StudioGraphDraftOwner; available: boolean; isCurrent: () => boolean;
  draft: CreativeInput; base?: CreativeDocument; pin?: PlanningSnapshot; dirty: boolean; uncertain: boolean };
type Entry = { key: string; raw: string; value: DirectorAuthorLocalDraft };
const MAX_SNAPSHOTS = 16, MAX_ATTEMPTS = 1024;
/** Unique immutable snapshots preserve competing writers without a mutable index.
 * Saving additionally requires a Web Lock + durable lineage barrier: a false
 * sibling snapshot must NEVER regain create/update authority after a lost ACK.
 * No unmount deletion: authority retirement is not user discard. */
export function useDirectorAuthorRecovery(props: Props) {
  const live = useRef(props); live.current = props;
  let prefix: string | undefined;
  try { prefix = props.owner && `${directorAuthorDraftKey(props.owner)}:snapshot:`; } catch { /* Fail closed. */ }
  const first = useRef(prefix); if (!first.current && prefix) first.current = prefix;
  const retired = useRef(false); if (first.current && prefix !== first.current) retired.current = true;
  const prefixRef = useRef(prefix); prefixRef.current = prefix;
  const alive = useRef(true), initialized = useRef(false), own = useRef<Entry>(), halted = useRef(false);
  const pending = useRef<Entry[]>([]), lineage = useRef<{ id: string; base: string }>();
  const [candidate, setCandidate] = useState<DirectorAuthorLocalDraft>();
  const [notice, setNotice] = useState(''), [savedAt, setSavedAt] = useState('');
  const current = () => alive.current && !retired.current && !!prefixRef.current && prefixRef.current === first.current && live.current.available && live.current.isCurrent();
  const baseline = (base?: CreativeDocument) => JSON.stringify(base ? [base.id, base.version] : null);
  const attemptPrefix = () => `${directorAuthorDraftKey(live.current.owner!)}:attempt:`;
  const attempted = (id: string) => localStorage.getItem(`${attemptPrefix()}${id}`) !== null;
  function recoveryId(base?: CreativeDocument) {
    const key = baseline(base);
    if (!lineage.current || lineage.current.base !== key) lineage.current = { id: crypto.randomUUID(), base: key };
    return lineage.current.id;
  }
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function fail(error: unknown) { halted.current = true; setNotice(error instanceof Error ? error.message : '本机存储不可用；导演草稿仍只保留在本页。'); }
  function keys(prefix: string) {
    const found: string[] = [];
    for (let i = 0; i < localStorage.length; i++) { const key = localStorage.key(i); if (key?.startsWith(prefix)) found.push(key); }
    return found.sort();
  }
  function unchanged(entry: Entry, allowRemoved = false) {
    const value = localStorage.getItem(entry.key);
    if (!current() || value !== entry.raw && !(allowRemoved && value === null)) throw new Error('其他页面已修改或移除导演恢复草稿。未覆盖缓存；请重新打开后核对。');
  }
  function remove(entry?: Entry) {
    if (!entry) return;
    // Product writers never replace this immutable key in place. Another tab
    // may retire the same source after creating its own independent snapshot.
    unchanged(entry, true); localStorage.removeItem(entry.key);
  }
  useEffect(() => {
    if (!current() || initialized.current || !props.owner) return;
    initialized.current = true;
    try {
      const all = keys(prefix!); let corrupt = false;
      pending.current = all.slice(0, MAX_SNAPSHOTS).flatMap(key => {
        try { const raw = localStorage.getItem(key); if (raw === null) return [];
          const value = readDirectorAuthorDraft(raw, props.owner!); if (attempted(value.recovery_id)) value.uncertain = true;
          return [{ key, raw, value }];
        } catch { corrupt = true; return []; }
      });
      setCandidate(pending.current[0]?.value);
      if (corrupt) { halted.current = true; setNotice('部分导演本机草稿格式损坏，原字节未覆盖；完整副本仍可逐项核对。当前输入请下载备份。'); }
      else if (all.length > MAX_SNAPSHOTS) setNotice('导演恢复副本较多，本次仅列出前 16 份；逐项处理后重新打开可核对其余副本。');
    } catch { fail(new Error('导演本机草稿无法读取。未覆盖缓存；当前输入请使用备份下载保管。')); }
  }, [prefix, props.available, props.owner]);
  function write(raw: string): Entry {
    if (!current() || !live.current.owner) throw new Error('导演作者身份已改变。');
    if (keys(prefixRef.current!).length >= MAX_SNAPSHOTS) throw new Error('导演恢复副本数量达到上限；未覆盖任何副本，请先逐项核对。');
    if (own.current) unchanged(own.current, true);
    const key = `${prefixRef.current}${crypto.randomUUID()}`;
    if (localStorage.getItem(key) !== null) throw new Error('导演恢复标识冲突；未覆盖任何副本。');
    const value = readDirectorAuthorDraft(raw, live.current.owner);
    localStorage.setItem(key, raw);
    const previous = own.current; own.current = { key, raw, value };
    // New author input is durable before the older exact snapshot is retired.
    if (previous) remove(previous);
    setSavedAt(value.saved_at); setNotice(''); return own.current;
  }
  function persist(draft = live.current.draft, base = live.current.base, pin = live.current.pin, uncertain = live.current.uncertain): boolean {
    if (!current() || !initialized.current || pending.current.length || halted.current || !live.current.owner) return false;
    try {
      const id = recoveryId(base); write(encodeDirectorAuthorDraft(live.current.owner, draft, base, pin, uncertain || attempted(id), id)); return true;
    } catch (reason) { fail(reason instanceof DOMException ? new Error('本机存储空间不足或访问被拒绝；导演输入仍保留在本页，请下载备份。') : reason); return false; }
  }
  /** No dispatch if write-ahead protection fails. A Web Lock serializes marker
   * admission; localStorage read/compare/write is NOT used as a cross-tab lock.
   * Markers are content-free, bounded, and retained for stale sibling copies. */
  async function prepareSave(draft: CreativeInput, base?: CreativeDocument, pin?: PlanningSnapshot): Promise<boolean> {
    if (!prefixRef.current && !first.current && !live.current.owner) return true; // Original hosts without recovery retain explicit save.
    if (!current() || !initialized.current || pending.current.length || halted.current || !live.current.owner) return false;
    try {
      if (!navigator.locks?.request) throw new Error('当前浏览器无法安全协调跨页面保存；未提交，请下载作者备份。');
      const markerPrefix = attemptPrefix(), id = recoveryId(base);
      return await navigator.locks.request(`${markerPrefix}admission`, { mode: 'exclusive', ifAvailable: true }, async lock => {
        if (!lock || !current() || halted.current || pending.current.length) throw new Error('另一页面正在核对保存，未提交；请重新打开后核对。');
        if (attempted(id)) throw new Error('此恢复来源已有保存尝试，必须重新核对结果；未重复提交。');
        if (keys(markerPrefix).length >= MAX_ATTEMPTS) throw new Error('导演保存保护记录达到上限，未提交；请保管作者备份。');
        localStorage.setItem(`${markerPrefix}${id}`, 'RECHECK_REQUIRED');
        if (!attempted(id)) throw new Error('导演保存保护记录未确认，未提交。');
        return persist(draft, base, pin, true);
      });
    } catch (reason) { fail(reason instanceof DOMException ? new Error('本机保存保护记录无法写入；未提交服务器保存，请下载作者备份。') : reason); return false; }
  }
  function clear() {
    if (!current() || !initialized.current) return;
    try {
      remove(own.current); own.current = undefined;
      if (pending.current.length) { remove(pending.current[0]); pending.current.shift(); }
      setCandidate(pending.current[0]?.value); setSavedAt('');
      // Do not delete lineage barriers, including after a confirmed save.
    } catch (reason) { fail(reason); }
  }
  useEffect(() => {
    if (!current() || candidate || halted.current) return;
    if (props.dirty || props.uncertain) persist();
    else if (own.current) clear();
  }, [props.draft, props.base, props.pin, props.dirty, props.uncertain, props.available, candidate, prefix]);
  function verifyCandidate(value: DirectorAuthorLocalDraft) {
    const source = pending.current[0];
    if (!current() || source?.value !== value) throw new Error('导演恢复来源或身份已变化，未恢复输入。');
    unchanged(source);
    if (!value.uncertain && attempted(value.recovery_id)) throw new Error('此恢复来源刚发生保存尝试，未恢复旧状态；请重新打开核对。');
  }
  function consume(value: DirectorAuthorLocalDraft) {
    verifyCandidate(value);
    // The existing immutable source is already durable. Claiming it as the
    // baseline needs no extra slot, so 16 valid snapshots remain recoverable.
    // First edit/save writes a new snapshot BEFORE retiring this exact source.
    own.current = pending.current[0];
    lineage.current = { id: value.recovery_id, base: JSON.stringify(value.base ? [value.base.id, value.base.version] : null) };
    pending.current = []; setCandidate(undefined); setSavedAt(value.saved_at);
  }
  return { candidate: current() ? candidate : undefined, notice: current() ? notice : '', savedAt: current() ? savedAt : '',
    retired: retired.current, enabled: !retired.current && !!prefix && first.current === prefix, persist, prepareSave, clear, verifyCandidate, consume };
}
