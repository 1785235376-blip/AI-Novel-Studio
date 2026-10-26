/**
 * [HERMIA-FE-20261025 U3-M7] Parameter edit surface for ParamSession. Two explicit confirmations (create, execute),
 * each in a modal confirm step that names the affected task, the changed fields and the (unknown) cost.
 * No auto calls on mount, selection or layout changes. Raw ids/digests only in data-* attributes.
 */
import {useState, useSyncExternalStore} from 'react';
import type {ParamSession} from './paramSession';
import {label} from './paramSession';

export function ParamEditPanel({session, targetTitle}: {session: ParamSession; targetTitle: string}) {
  const ver = useSyncExternalStore(f => session.subscribe(f), () => session.phase);
  const ph = ver;
  const [err, setErr] = useState<Record<string, string>>({});
  const [confirm, setConfirm] = useState<null | 'create' | 'execute'>(null);
  const changed = session.changed();
  const busy = ph.kind === 'previewing' || ph.kind === 'creating' || ph.kind === 'executing';
  const locked = !['editing', 'previewed', 'failed', 'blocked'].includes(ph.kind);
  return <section data-testid="u3-params" data-phase={ph.kind} aria-label="参数修改" style={{padding: 8}}>
    <fieldset disabled={locked} style={{border: 0, padding: 0}}>
      <legend>修改对象：{targetTitle}</legend>
      <label><input type="radio" name="u3-scope" checked={session.scope === 'this-task'} onChange={() => session.setScope('this-task')} /> 只改本次任务</label>{' '}
      <label><input type="radio" name="u3-scope" checked={session.scope === 'shared-template'} onChange={() => session.setScope('shared-template')} /> 修改共享模板</label>
      <ul style={{listStyle: 'none', padding: 0}}>
        {session.fields.map(f => <li key={f.key} data-field={f.key} data-mode={f.mode}>
          {f.mode === 'editable' ? <label>{f.label}{' '}
            <input aria-label={f.label} defaultValue={String(session.values[f.key] ?? '')} onChange={e => {
              const m = session.edit(f.key, e.target.value); setErr(x => ({...x, [f.key]: m ?? ''}));
            }} />{err[f.key] ? <span role="alert"> {err[f.key]}</span> : null}</label>
            : <span>{f.label}：{f.mode === 'readonly' ? '只读' : '不支持'}{f.reason ? `（${f.reason}）` : ''}</span>}
        </li>)}
      </ul>
    </fieldset>
    <p data-testid="u3-cost">成本：未知。{session.cost.state === 'UNKNOWN' ? session.cost.why : ''}</p>
    {ph.kind === 'blocked' ? <p role="alert">{ph.text}</p> : null}
    {ph.kind === 'editing' && changed.length ? <p data-testid="u3-preview-stale">参数已修改，之前的预览已作废，需要重新生成预览。</p> : null}
    {ph.kind === 'failed' ? <p role="alert">{ph.text}</p> : null}
    {ph.kind === 'unknown' ? <div role="alert" data-testid="u3-unknown"><p>{ph.next}</p>
      {ph.job ? <button type="button" onClick={() => void session.verify()}>读取原任务核对</button> : <p>无法按任务读取：请到任务面板刷新后查看是否已创建。</p>}</div> : null}
    {ph.kind === 'created' ? <p data-testid="u3-created">任务已创建但还没有执行。</p> : null}
    {ph.kind === 'executed' ? <p data-testid="u3-executed" data-job-status={ph.job.status}>已提交执行。结果会作为候选出现，需要你自己审核，不会自动采用。</p> : null}
    <div>
      <button type="button" data-testid="u3-preview" disabled={busy || ph.kind !== 'editing' && ph.kind !== 'failed' || session.scope !== 'this-task'} onClick={() => void session.preview()}>生成预览</button>{' '}
      <button type="button" data-testid="u3-ask-create" disabled={busy || ph.kind !== 'previewed'} onClick={() => setConfirm('create')}>创建任务…</button>{' '}
      <button type="button" data-testid="u3-ask-execute" disabled={busy || ph.kind !== 'created'} onClick={() => setConfirm('execute')}>执行…</button>
    </div>
    {confirm ? <div role="dialog" aria-modal="true" aria-label="确认" data-testid="u3-confirm">
      <p>{confirm === 'create' ? '将按这份预览创建一个任务（不会立即执行）。' : '将执行这个任务，可能调用模型。'}</p>
      <p>影响对象：{targetTitle}。修改的参数：{changed.length ? changed.map(label).join('、') : '无'}。成本：未知。</p>
      <button type="button" data-testid="u3-confirm-yes" disabled={busy} onClick={() => {
        const c = confirm; setConfirm(null);
        if (c === 'create' && ph.kind === 'previewed') void session.confirmCreate(ph.preview.preview_digest);
        if (c === 'execute' && ph.kind === 'created') void session.confirmExecute(ph.job.version);
      }}>确认</button>{' '}
      <button type="button" autoFocus onClick={() => setConfirm(null)}>取消</button>
    </div> : null}
  </section>;
}
