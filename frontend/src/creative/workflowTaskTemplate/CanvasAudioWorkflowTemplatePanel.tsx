import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../../ui/primitives';
import { studioGraphDraftKey, type StudioGraphDraftOwner } from '../studioGraphLocalDraft';
import type { StudioGraphRecord } from '../studioGraphTypes';
import { CanvasAudioTemplateParameterComparison } from './CanvasAudioTemplateParameterComparison';
import { captureCanvasAudioWorkflowTemplate, type CanvasAudioTemplateParameters, type CanvasAudioWorkflowTemplateRef } from './canvasAudioWorkflowTemplate';

export type CanvasAudioWorkflowTemplatePanelProps = {
  currentParameters?: CanvasAudioTemplateParameters;
  owner?: StudioGraphDraftOwner; ownerToken: object; current: boolean; busy: boolean; canApply: boolean;
  isCurrent: () => boolean;
  list: () => Promise<StudioGraphRecord[]>;
  read: (id: string) => Promise<StudioGraphRecord>;
  onApply: (reference: CanvasAudioWorkflowTemplateRef) => void | Promise<void>;
};
type Source = { raw: StudioGraphRecord; snapshot: string; record: StudioGraphRecord };
type SavedList = { token: object; sources: Source[] };
type Loaded = { token: object; source: Source; choices: CanvasAudioWorkflowTemplateRef[] };
type Choice = { token: object; loaded: Loaded; reference: CanvasAudioWorkflowTemplateRef };
const snapshot = (value: unknown): string => {
  const text = JSON.stringify(value);
  if (!text || text.length > 2_000_000) throw new Error('原图快照不可用。');
  return text;
};
const source = (raw: StudioGraphRecord): Source => {
  const saved = snapshot(raw);
  return { raw, snapshot: saved, record: JSON.parse(saved) as StudioGraphRecord };
};
const currentParameterSnapshot = (value: CanvasAudioTemplateParameters | undefined) => {
  if (value === undefined) return '';
  try { return snapshot(Object.fromEntries(['in_ms', 'out_ms', 'gain_db', 'fade_in_ms', 'fade_out_ms']
    .filter(key => Object.hasOwn(value, key)).map(key => [key, value[key as keyof CanvasAudioTemplateParameters]]))); }
  catch { return 'INVALID'; }
};
const unmodified = (value: Source) => snapshot(value.raw) === value.snapshot;
const samePin = (a: StudioGraphRecord, b: StudioGraphRecord) => a.id === b.id && a.version === b.version
  && a.definition_digest === b.definition_digest && a.execution_digest === b.execution_digest;

/** Consumes the original owner-checked Graph list/get; never saves or executes a graph. */
export function CanvasAudioWorkflowTemplatePanel(props: CanvasAudioWorkflowTemplatePanelProps) {
  const [saved, setSaved] = useState<SavedList>(), [loaded, setLoaded] = useState<Loaded>(), [choice, setChoice] = useState<Choice>();
  const [working, setWorking] = useState<object>(), [error, setError] = useState(''), [applied, setApplied] = useState(false), [, rerender] = useState(0);
  const alive = useRef(true), live = useRef(props), ticket = useRef(0), active = useRef<object>();
  const consent = useRef<Choice>(), listRef = useRef<SavedList>(), loadedRef = useRef<Loaded>(), choiceRef = useRef<Choice>(); live.current = props;
  const values = [props.owner && studioGraphDraftKey(props.owner), props.ownerToken, props.current, props.busy, props.canApply,
    props.isCurrent, props.list, props.read, props.onApply, currentParameterSnapshot(props.currentParameters)];
  const fence = useRef({ values, token: {}, retired: false });
  if (values.some((value, i) => !Object.is(value, fence.current.values[i]))) {
    fence.current.retired = true;
    fence.current = { values, token: {}, retired: false };
  }
  const token = fence.current.token;
  function current() {
    if (!alive.current || fence.current.token !== token || fence.current.retired) return false;
    const p = live.current;
    let valid = false;
    try { valid = !!p.owner && studioGraphDraftKey(p.owner) === values[0] && p.current && !p.busy && p.canApply && currentParameterSnapshot(p.currentParameters) === values[9] && p.isCurrent(); } catch { /* Fail closed on a retired client. */ }
    if (!valid) fence.current.retired = true;
    return valid;
  }
  const eligible = current(), pending = working === token;
  const visibleList = saved?.token === token ? saved : undefined;
  const visibleLoaded = loaded?.token === token ? loaded : undefined;
  const visibleChoice = choice?.token === token && choice.loaded === visibleLoaded ? choice : undefined;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; ticket.current++; }; }, []);
  useLayoutEffect(() => {
    ticket.current++; active.current = undefined; consent.current = undefined;
    listRef.current = undefined; loadedRef.current = undefined; choiceRef.current = undefined;
    setSaved(undefined); setLoaded(undefined); setChoice(undefined); setWorking(undefined); setError(''); setApplied(false);
  }, [token]);
  function clearChoice() { consent.current = undefined; choiceRef.current = undefined; setChoice(undefined); setApplied(false); }
  function clearLoaded() { loadedRef.current = undefined; setLoaded(undefined); clearChoice(); }
  function begin() {
    if (!current() || active.current) return;
    const operation = {}; active.current = operation; setWorking(token); setError('');
    return { operation, request: ++ticket.current };
  }
  const ongoing = (operation: { operation: object; request: number }) => current() && active.current === operation.operation && ticket.current === operation.request;
  function finish(operation: { operation: object }) {
    if (active.current === operation.operation) { active.current = undefined; if (alive.current) setWorking(undefined); }
  }
  async function refresh() {
    const operation = begin(); if (!operation) return;
    listRef.current = undefined; setSaved(undefined); clearLoaded();
    try {
      const records = await props.list(); if (!ongoing(operation)) return;
      if (!Array.isArray(records) || records.length > 25 || new Set(records.map(row => row.id)).size !== records.length) throw new Error();
      const value = { token, sources: records.map(source) }; listRef.current = value; setSaved(value);
    } catch { if (ongoing(operation)) setError('已保存图读取失败，请重新核对项目和权限。'); }
    finally { finish(operation); }
  }
  async function selectGraph(id: string) {
    const operation = begin(); if (!operation) return;
    clearLoaded();
    try {
      if (!id) return;
      const listed = listRef.current === visibleList ? visibleList?.sources.find(row => row.record.id === id) : undefined;
      if (!listed || !unmodified(listed)) throw new Error();
      const raw = await props.read(id); if (!ongoing(operation)) return;
      const reread = source(raw);
      if (!unmodified(listed) || !samePin(listed.record, reread.record)) throw new Error();
      const choices: CanvasAudioWorkflowTemplateRef[] = [];
      for (const node of reread.record.definition.nodes) {
        try { choices.push(captureCanvasAudioWorkflowTemplate(reread.record, node.id, props.owner!)); } catch { /* Only genuinely supported nodes are offered. */ }
      }
      if (!choices.length) throw new Error();
      const value = { token, source: reread, choices }; loadedRef.current = value; setLoaded(value);
    } catch { if (ongoing(operation)) setError('此保存图没有可用的音频截取节点，或原图版本、来源已变化。请刷新列表后重新读取。'); }
    finally { finish(operation); }
  }
  function selectNode(id: string) {
    if (!current() || active.current) return;
    clearChoice();
    try {
      if (!id) return;
      if (!visibleLoaded || loadedRef.current !== visibleLoaded || !unmodified(visibleLoaded.source)) throw new Error();
      const reference = captureCanvasAudioWorkflowTemplate(visibleLoaded.source.record, id, props.owner!);
      const value = { token, loaded: visibleLoaded, reference }; choiceRef.current = value; setChoice(value);
    } catch { clearLoaded(); setError('原图数据已变化，请重新读取并确认。'); }
  }
  async function apply() {
    if (!visibleChoice || choiceRef.current !== visibleChoice || consent.current !== visibleChoice) return;
    const operation = begin(); if (!operation) return;
    const selected = visibleChoice; consent.current = undefined; choiceRef.current = undefined; setChoice(undefined);
    try {
      if (!unmodified(selected.loaded.source)) throw new Error();
      const raw = await props.read(selected.reference.graph_id); if (!ongoing(operation)) return;
      if (!unmodified(selected.loaded.source)) throw new Error();
      const checked = source(raw);
      const reference = captureCanvasAudioWorkflowTemplate(checked.record, selected.reference.node_id, props.owner!);
      if (snapshot(reference) !== snapshot(selected.reference) || checked.snapshot !== selected.loaded.source.snapshot) throw new Error();
      if (!ongoing(operation)) return;
      await props.onApply(reference);
      if (ongoing(operation)) { clearLoaded(); setApplied(true); }
    } catch { if (ongoing(operation)) { clearLoaded(); setError('原图版本、来源或本次任务已变化，未应用模板。请重新读取并显式确认。'); } }
    finally { finish(operation); }
  }
  return <section aria-label="本次音频卡片任务模板">
    <h4>使用已保存工作流的音频截取参数</h4>
    <p>从原工作流编辑器保存的媒体图读取模板。只复制该版本明确提供的截取、增益与淡入淡出参数到本次音频卡片任务；模板未提供的效果字段保留本次设置。修改共享模板请返回原工作流编辑器。</p>
    <p>应用只准备任务草稿。排队、执行和正式结果审核仍需在原任务流程中分别确认。</p>
    {!eligible && <StatusMessage>当前项目实例、身份或原卡片任务不可用，请重新建立任务后读取模板。</StatusMessage>}
    <Button disabled={!eligible || pending} loading={pending} onClick={() => void refresh()}>读取已保存工作流</Button>
    {visibleList && <label>已保存工作流<select aria-label="已保存工作流" value={visibleLoaded?.source.record.id ?? ''} disabled={!eligible || pending}
      onChange={event => void selectGraph(event.target.value)}>
      <option value="">请选择并读取原图</option>
      {visibleList.sources.map(row => <option key={row.record.id} value={row.record.id}>{row.record.definition.title} · {row.record.id} · v{row.record.version}</option>)}
    </select></label>}
    {visibleList?.sources.length === 0 && <StatusMessage>当前身份和项目范围没有已保存工作流。</StatusMessage>}
    {visibleLoaded && <label>已核对的音频截取节点<select aria-label="已核对的音频截取节点" value={visibleChoice?.reference.node_id ?? ''} disabled={!eligible || pending}
      onChange={event => selectNode(event.target.value)}><option value="">请选择节点</option>
      {visibleLoaded.choices.map(row => <option key={row.node_id} value={row.node_id}>{row.node_id} · {row.parameters.in_ms}–{row.parameters.out_ms} ms</option>)}
    </select></label>}
    {visibleChoice && <div>
      <p>原图 {visibleChoice.reference.graph_id} · v{visibleChoice.reference.graph_version} · 节点 {visibleChoice.reference.node_id}</p>
      <p>截取区间：{visibleChoice.reference.parameters.in_ms}–{visibleChoice.reference.parameters.out_ms} ms。影响范围：只覆盖本次任务中模板明确提供的字段，其他设置保持。</p>
      <CanvasAudioTemplateParameterComparison source={visibleChoice.reference.parameters} current={props.currentParameters} />
      <p>复制后仍须通过原任务预览核验；本次修改不会改变共享模板或已排队任务。</p>
      <p style={{ overflowWrap: 'anywhere' }}>定义摘要：<code>{visibleChoice.reference.definition_digest}</code><br />执行摘要：<code>{visibleChoice.reference.execution_digest}</code></p>
      <label><input type="checkbox" checked={consent.current === visibleChoice} disabled={!eligible || pending} onChange={event => {
        if (!current() || active.current || choiceRef.current !== visibleChoice) return;
        if (!unmodified(visibleChoice.loaded.source)) { clearLoaded(); setError('原图数据已变化，请重新读取并确认。'); return; }
        consent.current = event.target.checked ? visibleChoice : undefined; rerender(value => value + 1);
      }} />{['gain_db', 'fade_in_ms', 'fade_out_ms'].some(key => Object.hasOwn(visibleChoice.reference.parameters, key))
        ? '确认把此版本截取与效果参数复制到本次音频卡片任务' : '确认把此版本截取区间复制到本次音频卡片任务'}</label>
      <Button disabled={!eligible || pending || consent.current !== visibleChoice} onClick={() => void apply()}>核对原图并应用到本次任务</Button>
    </div>}
    {applied && <StatusMessage tone="success">已准备本次任务参数副本；原工作流模板保持原版本。请核对任务预览后再排队。</StatusMessage>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}
  </section>;
}
