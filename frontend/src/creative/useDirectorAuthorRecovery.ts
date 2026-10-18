import { useEffect, useRef, useState } from 'react';
import { directorAuthorDraftKey, encodeDirectorAuthorDraft, readDirectorAuthorDraft, type DirectorAuthorLocalDraft } from './directorAuthorLocalDraft';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { CreativeDocument, CreativeInput } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';

type Props = { owner?: StudioGraphDraftOwner; available: boolean; isCurrent: () => boolean;
  draft: CreativeInput; base?: CreativeDocument; pin?: PlanningSnapshot; dirty: boolean; uncertain: boolean };
type Entry = { key: string; raw: string; value: DirectorAuthorLocalDraft };
const MAX_SNAPSHOTS = 16;
/** Immutable, unique snapshot keys avoid read/compare/write races between tabs.
 * A writer creates its next snapshot BEFORE retiring its own previous one.
 * No shared mutable index and no unmount deletion: retirement is not discard. */
export function useDirectorAuthorRecovery(props: Props) {
  const live = useRef(props); live.current = props;
  let prefix: string | undefined;
  try { prefix = props.owner && `${directorAuthorDraftKey(props.owner)}:snapshot:`; } catch { /* Fail closed. */ }
  const first = useRef(prefix); if (!first.current && prefix) first.current = prefix;
  const retired = useRef(false); if (first.current && prefix !== first.current) retired.current = true;
  const prefixRef = useRef(prefix); prefixRef.current = prefix;
  const alive = useRef(true), initialized = useRef(false), own = useRef<Entry>(), consumed = useRef<Entry>(), halted = useRef(false);
  const pending = useRef<Entry[]>([]);
  const [candidate, setCandidate] = useState<DirectorAuthorLocalDraft>();
  const [notice, setNotice] = useState(''), [savedAt, setSavedAt] = useState('');
  const current = () => alive.current && !retired.current && !!prefixRef.current && prefixRef.current === first.current && live.current.available && live.current.isCurrent();
  useEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function fail(error: unknown) { halted.current = true; setNotice(error instanceof Error ? error.message : '本机存储不可用；导演草稿仍只保留在本页。'); }
  function keys() {
    const found: string[] = [];
    for (let i = 0; i < localStorage.length; i++) { const key = localStorage.key(i); if (key?.startsWith(prefixRef.current!)) found.push(key); }
    if (found.length > MAX_SNAPSHOTS) throw new Error('导演恢复副本数量达到上限；未覆盖任何副本。请先逐项核对或下载当前输入。');
    return found.sort();
  }
  function unchanged(entry: Entry) {
    if (!current() || localStorage.getItem(entry.key) !== entry.raw) throw new Error('其他页面已修改或移除导演恢复草稿。未覆盖缓存；请重新打开后核对。');
  }
  function remove(entry?: Entry) {
    if (!entry) return;
    // This key is immutable in this protocol. Another writer only creates NEW
    // keys; deletion cannot race with an in-place replacement by this product.
    unchanged(entry); localStorage.removeItem(entry.key);
  }
  useEffect(() => {
    if (!current() || initialized.current || !props.owner) return;
    initialized.current = true;
    try {
      pending.current = keys().map(key => { const raw = localStorage.getItem(key); if (raw === null) throw new Error('导演恢复副本已变化，请重新打开后核对。');
        return { key, raw, value: readDirectorAuthorDraft(raw, props.owner!) }; });
      setCandidate(pending.current[0]?.value);
    } catch { fail(new Error('导演本机草稿无法读取、格式损坏或副本过多。未覆盖缓存；当前输入请使用备份下载保管。')); }
  }, [prefix, props.available, props.owner]);
  function write(raw: string): Entry {
    if (!current() || !live.current.owner) throw new Error('导演作者身份已改变。');
    if (keys().length >= MAX_SNAPSHOTS) throw new Error('导演恢复副本数量达到上限；未覆盖任何副本，请先逐项核对。');
    if (own.current) unchanged(own.current);
    const key = `${prefixRef.current}${crypto.randomUUID()}`;
    if (localStorage.getItem(key) !== null) throw new Error('导演恢复标识冲突；未覆盖任何副本。');
    const value = readDirectorAuthorDraft(raw, live.current.owner);
    localStorage.setItem(key, raw);
    const previous = own.current; own.current = { key, raw, value };
    // If retiring the older snapshot fails, the newer input is already durable.
    if (previous) remove(previous);
    setSavedAt(value.saved_at); setNotice(''); return own.current;
  }
  function persist(draft = live.current.draft, base = live.current.base, pin = live.current.pin, uncertain = live.current.uncertain) {
    if (!current() || !initialized.current || pending.current.length || halted.current || !live.current.owner) return;
    try { write(encodeDirectorAuthorDraft(live.current.owner, draft, base, pin, uncertain)); }
    catch (reason) { fail(reason instanceof DOMException ? new Error('本机存储空间不足或访问被拒绝；导演输入仍保留在本页，请下载备份。') : reason); }
  }
  function clear() {
    if (!current() || !initialized.current || halted.current) return;
    try {
      remove(own.current); own.current = undefined;
      if (consumed.current && localStorage.getItem(consumed.current.key) !== null) remove(consumed.current);
      consumed.current = undefined;
      if (pending.current.length) { remove(pending.current[0]); pending.current.shift(); }
      setCandidate(pending.current[0]?.value); setSavedAt('');
    } catch (reason) { fail(reason); }
  }
  useEffect(() => {
    if (!current() || candidate || halted.current) return;
    if (props.dirty || props.uncertain) persist();
    else if (own.current) clear();
  }, [props.draft, props.base, props.pin, props.dirty, props.uncertain, props.available, candidate, prefix]);
  function verifyCandidate(value: DirectorAuthorLocalDraft) {
    const source = pending.current[0];
    if (!current() || halted.current || source?.value !== value) throw new Error('导演恢复来源或身份已变化，未恢复输入。');
    unchanged(source);
  }
  function consume(value: DirectorAuthorLocalDraft) {
    verifyCandidate(value);
    // Keep the source until this explicit recovery has its own durable copy.
    const source = pending.current[0]; write(source.raw); consumed.current = source;
    pending.current = []; setCandidate(undefined);
  }
  return { candidate: current() ? candidate : undefined, notice: current() ? notice : '', savedAt: current() ? savedAt : '',
    retired: retired.current, enabled: !retired.current && !!prefix && first.current === prefix, persist, clear, verifyCandidate, consume };
}
