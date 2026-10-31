/**
 * [HERMIA-FE-20261025 U4-M9d] Work history: record kinds, provenance, current-vs-historical diff, explicit restore.
 * Restore appends a new version via the owner; old/new records kept. No rerun, no re-adopt, no auto read on mount.
 */
import {useRef, useState} from 'react';
import type {CanvasViewHistory} from '../../creative/studioCanvasViewClient';
import {RECORD_KIND_TEXT, provenance, restoreImpact} from './historyModel';
import {createRestoreFlow, type RestoreDeps} from './restoreFlow';
import type {RecordKind} from '../contracts';

import {useDz} from '../defaultui/drawerEn';
export function HistoryPanel(props: {deps: RestoreDeps; canvasId: string; localDraft?: boolean}) {
  const z = useDz(); // [UWPORT-P2] en drawer text
  const restore = useRef(createRestoreFlow(props.deps)).current;
  const [h, setH] = useState<CanvasViewHistory | null>(null), [pick, setPick] = useState<number | null>(null), [confirm, setConfirm] = useState(false);
  const [busy, setBusy] = useState(false), [msg, setMsg] = useState<{tone: string; text: string} | null>(null);
  async function load() {
    setBusy(true); setMsg(null); setConfirm(false); const epoch = props.deps.lease.epoch;
    try { const r = await props.deps.canvasViews.history(props.canvasId); if (props.deps.lease.isCurrent() && props.deps.lease.epoch === epoch) setH(r); }
    catch { setMsg({tone: 'error', text: z('读取历史失败。请检查网络后再点「读取历史」。')}); }
    setBusy(false);
  }
  const impact = h && pick != null ? restoreImpact(h, pick) : null;
  async function doRestore() {
    if (!h || pick == null) return; setBusy(true); setConfirm(false);
    const r = await restore(props.canvasId, h, pick);
    if (r.state === 'restored') { setMsg({tone: 'success', text: z(`已恢复为新的第 ${r.record.version} 版，旧版本都还在。没有重跑任何生成。`)}); setPick(null);
      try { setH(await props.deps.canvasViews.history(props.canvasId)); } catch { /* keep message; user can reload */ } }
    else setMsg({tone: r.state === 'blocked' ? 'error' : 'warning', text: r.state === 'blocked' ? r.text : r.next});
    setBusy(false);
  }
  const kinds: RecordKind[] = ['local-draft', 'saved-work', 'asset-version', 'execution-record'];
  return (
    <section aria-label={z('作品历史')} data-testid="u4-history">
      <header><h3>{z('作品历史')}</h3></header>
      <details><summary>{z('这些记录有什么区别？')}</summary><ul>{kinds.map(k => <li key={k}><strong>{z(RECORD_KIND_TEXT[k].label)}</strong>{z('：')}{z(RECORD_KIND_TEXT[k].detail)}</li>)}</ul></details>
      {props.localDraft && <p data-testid="u4-local-draft" data-record-kind="local-draft">{z(`这台设备上还有未保存的${RECORD_KIND_TEXT['local-draft'].label}，它不在下面的历史里。`)}</p>}
      <button type="button" onClick={load} disabled={busy} data-testid="u4-history-read">{z(h ? '重新读取历史' : '读取历史')}</button>
      {h && <ol data-testid="u4-history-list">{[...h.items].reverse().map(it => (
        <li key={it.version} data-record-kind="saved-work" data-version={it.version}>
          <span>{z(RECORD_KIND_TEXT['saved-work'].label)} · {z(provenance(it))}{it.version === h.current_version ? z('（当前）') : ''}</span>
          {it.version !== h.current_version && <button type="button" onClick={() => { setPick(it.version); setConfirm(false); }} data-testid={`u4-compare-${it.version}`}>{z('与当前对比')}</button>}
        </li>))}</ol>}
      {impact && (impact.ok ? <div data-testid="u4-impact"><p>{z(`恢复到第 ${pick} 版会：`)}</p><ul>{impact.lines.map(l => <li key={l}>{z(l)}</li>)}</ul>
        {props.deps.canMutate() ? <button type="button" onClick={() => setConfirm(true)} disabled={busy} data-testid="u4-restore">{z('恢复这个版本…')}</button>
          : <p>{z('你当前没有修改这个项目的权限，不能恢复。')}</p>}</div>
        : <p data-testid="u4-impact-blocked">{impact.reason}</p>)}
      {confirm && <div role="alertdialog" aria-label="确认恢复" data-testid="u4-restore-confirm"><p>{z('确认恢复？这会新增一个版本，不会删除任何记录，也不会重新生成。')}</p>
        <button type="button" onClick={doRestore} disabled={busy} data-testid="u4-restore-yes">{z('确认恢复')}</button><button type="button" onClick={() => setConfirm(false)}>{z('取消')}</button></div>}
      {msg && <div role={msg.tone === 'error' ? 'alert' : 'status'} data-testid="u4-history-msg" data-tone={msg.tone}>{msg.text}</div>}
    </section>);
}
