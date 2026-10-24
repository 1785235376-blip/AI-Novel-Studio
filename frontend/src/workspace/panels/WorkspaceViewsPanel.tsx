/**
 * [HERMIA-FE-20261024 VW-M2] 视图管理 dialog: save / apply / rename / delete named worksets.
 * Every button goes through the shared ActionRegistry (same path as command search / shortcuts).
 * In session mode the UI says so; there is no button that pretends to persist.
 */
import {useEffect, useRef, useState} from 'react';
import type {ActionContext, ActionRegistry, ExecuteResult} from '../../workbench/actions';
import {PREFS_REASON_TEXT, type ViewPrefs} from '../state/viewPreferences';
import {VIEW_ACTION_IDS} from '../actions/viewActions';
import {WORKSET_LIMIT, WORKSET_NAME_MAX} from '../layout/worksets';

export interface WorkspaceViewsPanelProps {
  prefs: ViewPrefs; actions: ActionRegistry; ctx: (input?: unknown) => ActionContext;
  onClose(): void; message?: string | null;
}
export function WorkspaceViewsPanel({prefs, actions, ctx, onClose, message}: WorkspaceViewsPanelProps) {
  const [name, setName] = useState('');
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [editing, setEditing] = useState<{id: string; name: string} | null>(null);
  const [confirmDel, setConfirmDel] = useState<string | null>(null);
  const [, force] = useState(0);
  const ref = useRef<HTMLDivElement>(null);
  const opener = useRef<Element | null>(typeof document !== 'undefined' ? document.activeElement : null);
  useEffect(() => { ref.current?.querySelector<HTMLElement>('input,button')?.focus(); const o = opener.current; return () => { (o as HTMLElement | null)?.focus?.(); }; }, []);
  const st = prefs.status(); const list = prefs.getWorksets();
  const session = st.mode === 'session';
  const run = async (id: string, input: unknown, after?: () => void) => {
    if (busy) return; setBusy(true); setErr(null);
    const r: ExecuteResult = await actions.execute(id, ctx(input));
    setBusy(false);
    if (r.status === 'done') { after?.(); force(v => v + 1); }
    else if (r.status === 'blocked') setErr(r.reason);
    else if (r.status === 'error') setErr(String((r.error as Error)?.message ?? r.error));
    else if (r.status === 'stale') setErr('界面已经切换，这次操作没有生效。');
  };
  const onKeyDown = (e: React.KeyboardEvent) => { if (e.key === 'Escape' && !e.nativeEvent.isComposing) { e.stopPropagation(); onClose(); } };
  return (
    <div className="uw-dialog" style={{position: 'fixed'}}><div className="uw-dialog__card" role="dialog" aria-modal="true" aria-labelledby="uw-views-title" ref={ref} onKeyDown={onKeyDown} data-testid="uw-views">
      <h2 id="uw-views-title" style={{fontSize: 16, margin: '0 0 8px'}}>视图</h2>
      <p data-testid="uw-views-mode" data-mode={st.mode} style={{margin: '0 0 8px'}}>{session ? `仅本次会话：${PREFS_REASON_TEXT[st.reason]}` : PREFS_REASON_TEXT[st.reason]}</p>
      <form onSubmit={e => { e.preventDefault(); void run(VIEW_ACTION_IDS.save, name, () => setName('')); }} style={{display: 'flex', gap: 6}}>
        <label>视图名称 <input className="uw-input" value={name} maxLength={WORKSET_NAME_MAX} onChange={e => setName(e.target.value)} aria-describedby="uw-views-limit" /></label>
        <button type="submit" className="uw-btn uw-btn--primary" disabled={busy || list.length >= WORKSET_LIMIT} aria-busy={busy || undefined} data-action-id={VIEW_ACTION_IDS.save}>
          {session ? '保存到本次会话' : '保存当前布局'}</button>
      </form>
      <small id="uw-views-limit">{list.length >= WORKSET_LIMIT ? `已达到 ${WORKSET_LIMIT} 个视图上限，请先删除不用的视图。` : `最多 ${WORKSET_LIMIT} 个，名称最多 ${WORKSET_NAME_MAX} 个字。视图只记录面板位置和大小，不含作品内容。`}</small>
      {(err || message) && <p role={err ? 'alert' : 'status'} data-testid="uw-views-msg">{err ?? message}</p>}
      {list.length === 0 ? <p data-testid="uw-views-empty">还没有保存的视图。</p> :
        <ul aria-label="已保存的视图" style={{listStyle: 'none', padding: 0}}>{list.map(w => <li key={w.id} style={{display: 'flex', gap: 6, alignItems: 'center', margin: '4px 0'}}>
          {editing?.id === w.id
            ? <form onSubmit={e => { e.preventDefault(); void run(VIEW_ACTION_IDS.rename, {id: w.id, name: editing.name}, () => setEditing(null)); }} style={{display: 'flex', gap: 6}}>
                <label>新名称 <input className="uw-input" value={editing.name} maxLength={WORKSET_NAME_MAX} onChange={e => setEditing({id: w.id, name: e.target.value})} /></label>
                <button type="submit" className="uw-btn" disabled={busy}>确定</button>
                <button type="button" className="uw-btn" onClick={() => setEditing(null)}>取消</button></form>
            : confirmDel === w.id
              ? <><span>确定删除「{w.name}」？当前布局不会改变。</span>
                  <button type="button" className="uw-btn" disabled={busy} onClick={() => void run(VIEW_ACTION_IDS.remove, w.id, () => setConfirmDel(null))}>删除</button>
                  <button type="button" className="uw-btn" onClick={() => setConfirmDel(null)}>取消</button></>
              : <><span style={{flex: 1}}>{w.name}</span>
                  <button type="button" className="uw-btn" disabled={busy} data-action-id={VIEW_ACTION_IDS.apply} aria-label={`应用视图「${w.name}」`} onClick={() => void run(VIEW_ACTION_IDS.apply, w.id)}>应用</button>
                  <button type="button" className="uw-btn" aria-label={`重命名视图「${w.name}」`} onClick={() => setEditing({id: w.id, name: w.name})}>重命名</button>
                  <button type="button" className="uw-btn" aria-label={`删除视图「${w.name}」`} onClick={() => setConfirmDel(w.id)}>删除</button></>}
        </li>)}</ul>}
      <div className="uw-dialog__actions"><button type="button" className="uw-btn" onClick={onClose}>关闭</button></div>
    </div></div>
  );
}
