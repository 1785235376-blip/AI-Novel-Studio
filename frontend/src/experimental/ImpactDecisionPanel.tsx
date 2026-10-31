import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { Details, Field } from './shared';
import type { changeImpactClient, ImpactView } from './changeImpactClient';
import type { ImpactDecisionChoice, ImpactDecisionPreview, ImpactDecisionRecord, ImpactDecisionSelection } from './changeImpactDecisionContract';

type Props = { api: ReturnType<typeof changeImpactClient>; view: ImpactView; disabled: boolean };
type Preview = { data: ImpactDecisionPreview; selected: ImpactDecisionSelection[]; ticket: object; authority: object; requestId: string };
const choiceLabel = (choice: ImpactDecisionChoice) => choice === 'KEEP' ? '保留原成果' : '请求重建（仅记录意图）';
const newId = () => globalThis.crypto?.randomUUID?.() || `decision-${Date.now()}-${Math.random().toString(16).slice(2)}`;
export function ImpactDecisionPanel(props: Props) {
  const live = useRef(props); live.current = props;
  const owner = useRef({ api: props.api, view: props.view, token: {} });
  if (owner.current.api !== props.api || owner.current.view !== props.view) owner.current = { api: props.api, view: props.view, token: {} };
  const token = owner.current.token;
  const authority = useRef({ token, disabled: props.disabled, lease: {} });
  if (authority.current.token !== token || authority.current.disabled !== props.disabled) authority.current = { token, disabled: props.disabled, lease: {} };
  const lease = authority.current.lease;
  const alive = useRef(true), running = useRef<object>(), readSequence = useRef(0), readAbort = useRef<AbortController>();
  const [choices, updateChoices] = useState<Record<string, ImpactDecisionChoice>>({});
  const choicesRef = useRef(choices);
  const [preview, updatePreview] = useState<Preview>(), previewRef = useRef<Preview>();
  const [consent, updateConsent] = useState<{ ticket: object }>(), consentRef = useRef<typeof consent>();
  const [recordState, updateRecords] = useState<{ owner: object; items: ImpactDecisionRecord[] }>(), [reading, setReading] = useState(false);
  const records = recordState?.owner === token ? recordState.items : undefined;
  const setRecords = (value: ImpactDecisionRecord[] | undefined | ((previous: ImpactDecisionRecord[] | undefined) => ImpactDecisionRecord[])) => updateRecords(previous => {
    const items = typeof value === 'function' ? value(previous?.owner === token ? previous.items : undefined) : value;
    return items ? { owner: token, items } : undefined;
  });
  const [busy, setBusy] = useState(false), [uncertain, setUncertain] = useState(false), uncertainRef = useRef(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false);
  const current = () => alive.current && owner.current.token === token;
  const editable = () => current() && authority.current.lease === lease && !live.current.disabled && !running.current && !uncertainRef.current && !denied;
  const setPreview = (value: Preview | undefined) => { previewRef.current = value; updatePreview(value); consentRef.current = undefined; updateConsent(undefined); };
  const setChoices = (value: typeof choices) => { choicesRef.current = value; updateChoices(value); setPreview(undefined); };
  const setUnknown = (value: boolean) => { uncertainRef.current = value; setUncertain(value); };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; readAbort.current?.abort(); }; }, []);
  useLayoutEffect(() => {
    running.current = undefined; readSequence.current++; readAbort.current?.abort(); choicesRef.current = {}; updateChoices({});
    setPreview(undefined); setRecords(undefined); setBusy(false); setReading(false); setUnknown(false); setError(''); setNotice(''); setDenied(false);
  }, [token]);
  const fail = (reason: unknown) => {
    if (reason instanceof ApiError && [401, 403, 404].includes(reason.status)) { setDenied(true); setRecords(undefined); setPreview(undefined); }
    setError(reason instanceof ApiError ? reason.message : '读取或保存未确认，请核对后继续。');
  };
  async function loadRecords() {
    if (!current() || live.current.disabled || running.current) return;
    const sequence = ++readSequence.current; readAbort.current?.abort(); const abort = new AbortController(); readAbort.current = abort;
    setReading(true); setError('');
    try {
      const result = await props.api.decisions(props.view.source, abort.signal);
      if (!current() || sequence !== readSequence.current || abort.signal.aborted) return;
      setRecords(result.items);
      const pending = previewRef.current;
      if (uncertainRef.current && pending && result.items.some(row => row.request_id === pending.requestId && row.preview_digest === pending.data.preview_digest)) {
        setUnknown(false); setPreview(undefined); setNotice('已从原保存记录核对此请求，未重复新增决定。');
      }
    } catch (reason) { if (current() && sequence === readSequence.current && !abort.signal.aborted) { setRecords(undefined); fail(reason); } }
    finally { if (current() && sequence === readSequence.current) setReading(false); }
  }
  async function inspect() {
    if (!editable() || reading) return;
    const selected = props.view.items.filter(node => choicesRef.current[node.key]).map(node => ({ key: node.key, expected_version: node.version, choice: choicesRef.current[node.key] }));
    if (!selected.length || selected.length > 20) return;
    const operation = {}; running.current = operation; setBusy(true); setPreview(undefined); setError(''); setNotice('');
    try {
      const data = await props.api.previewDecisions(props.view.source, selected);
      if (current() && authority.current.lease === lease && running.current === operation && !live.current.disabled)
        setPreview({ data, selected, ticket: {}, authority: lease, requestId: newId() });
    } catch (reason) { if (current() && authority.current.lease === lease) fail(reason); }
    finally { if (current() && running.current === operation) { running.current = undefined; setBusy(false); } }
  }
  async function save(box: Preview, granted: typeof consent, retry = false) {
    if (!current() || live.current.disabled || denied || running.current || reading || previewRef.current !== box
      || (retry ? lease : box.authority) !== authority.current.lease || !granted || consentRef.current !== granted || granted.ticket !== box.ticket
      || retry !== uncertainRef.current) return;
    const operation = {}; running.current = operation; setBusy(true); setError(''); setNotice('');
    try {
      const row = await props.api.saveDecisions(props.view.source, box.selected, box.data, box.requestId);
      if (!current() || running.current !== operation) return;
      setUnknown(false); setPreview(undefined); setRecords(previous => [row, ...(previous || []).filter(item => item.id !== row.id)].slice(0, 25));
      setNotice(row.current ? '决定已保存；未锁定、重建或替换任何成果。' : '已核对原请求的保存记录；来源随后已变化，此记录仅供历史核对。');
    } catch (reason) {
      if (!current() || running.current !== operation) return;
      const known = reason instanceof ApiError && [401, 403, 404, 409, 422].includes(reason.status);
      if (known) { setUnknown(false); setPreview(undefined); }
      else setUnknown(true);
      fail(reason);
    } finally { if (current() && running.current === operation) { running.current = undefined; setBusy(false); } }
  }
  const visible = preview && (preview.authority === lease || uncertain) ? preview : undefined;
  const disabled = props.disabled || busy || reading || denied || uncertain;
  const count = Object.keys(choices).length;
  return <section className="experimental-section" aria-label="保留与重建决定">
    <h3>保留与重建决定</h3>
    <p>针对当前来源快照明确记录最多 20 项决定。未选择项保持未知；每位作者在当前范围最多保存 25 份。切换来源或重新读取影响会清除尚未保存的选择，已保存记录可重新读取。记录不会改动成果锁、原稿、预检或任务；请求重建仍需到原领域重新预检、确认与审核。</p>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}
    {denied ? <StatusMessage>当前决定内容不可用，请重新读取有权限的影响范围。</StatusMessage> : <>
      {props.view.items.map(node => <Field key={node.key} label={`决定 ${node.label} · ${node.key}`}><select disabled={disabled} value={choices[node.key] || ''} onChange={event => {
        if (!editable() || reading) return;
        const value = event.target.value;
        if (value && value !== 'KEEP' && value !== 'REBUILD' || value && !choicesRef.current[node.key] && Object.keys(choicesRef.current).length >= 20) return;
        const next = { ...choicesRef.current }; if (value) next[node.key] = value as ImpactDecisionChoice; else delete next[node.key]; setChoices(next); setNotice('');
      }}><option value="">尚未决定</option><option value="KEEP">保留原成果</option><option value="REBUILD">请求重建（仅记录意图）</option></select></Field>)}
      <Button disabled={disabled || !count} onClick={() => void inspect()}>预览 {count} 项保留 / 重建决定</Button>
      {visible && <section className="experimental-record" aria-label="保留与重建决定预览">
        <p>来源：{visible.data.source_snapshot.label}</p><Details value={visible.data.source_snapshot.binding} label="本次来源版本与摘要" open />
        <ul>{visible.data.items.map(item => <li key={item.key}>{item.label} · {item.key} · v{item.version}：{choiceLabel(item.choice)}{item.choice === 'REBUILD' && !item.refresh_candidate ? '；原领域手工核对，不授予执行权限' : ''}</li>)}</ul>
        <label className="experimental-check"><input type="checkbox" disabled={disabled} checked={consent?.ticket === visible.ticket} onChange={event => {
          if (!editable() || reading || previewRef.current !== visible || visible.authority !== authority.current.lease) return;
          const next = event.target.checked ? { ticket: visible.ticket } : undefined; consentRef.current = next; updateConsent(next);
        }} />确认只保存以上决定，保留原成果且不启动任务</label>
        {!uncertain && <Button disabled={disabled || consent?.ticket !== visible.ticket} onClick={() => void save(visible, consent)}>保存保留 / 重建决定</Button>}
        {uncertain && <><StatusMessage tone="warning">本次保存结果不确定。请先读取原保存记录，或使用同一请求核对；不会自动新增、重建或重试任务。</StatusMessage>
          <Button disabled={props.disabled || busy || reading} onClick={() => void save(visible, consent, true)}>使用同一请求核对保存</Button></>}
      </section>}
      <Button disabled={props.disabled || busy || reading} onClick={() => void loadRecords()}>读取已保存的保留 / 重建决定</Button>
      {reading && <StatusMessage>正在读取原决定记录…</StatusMessage>}
      {records && <section aria-label="已保存的保留与重建决定"><h4>已保存决定</h4>{!records.length && <p>当前来源尚无可读取的决定。</p>}
        {records.map(row => <article className="experimental-record" key={row.id}><Badge tone={row.current ? 'neutral' : 'warning'}>{row.current ? '保存时的来源与目标仍一致' : '来源或目标已变化；仅作历史记录'}</Badge>
          <p>{row.id} · 来源 {row.source_snapshot.label}</p><Details value={row.source_snapshot.binding} label="决定保存时的来源版本与摘要" />
          <ul>{row.items.map(item => <li key={item.key}>{item.label} · {item.key} · 保存 v{item.version} / 当前 v{item.current_version}：{choiceLabel(item.choice)}</li>)}</ul></article>)}
      </section>}
    </>}
  </section>;
}
