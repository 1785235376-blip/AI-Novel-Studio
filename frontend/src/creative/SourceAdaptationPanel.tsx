import { useEffect, useRef, useState } from 'react';
import { ApiError, type Chapter } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { CreativeField } from './CreativeCanvas';
import type { AdaptationOutput, AdaptationProposal, CreativeClient, DirectorModelRoute } from './client';
import type { CreativeDocument } from './types';

/** Feature content only. Creative owns proposals and documents; no manuscript writes. */
export function SourceAdaptationPanel({ client, chapter, sourceReady, canMutate, onDocument, onDenied, onBusyChange, onDraftChange }: {
  client: CreativeClient; chapter?: Chapter; sourceReady: boolean; canMutate: boolean;
  onDocument: (row: CreativeDocument) => void; onDenied: () => void; onBusyChange: (busy: boolean) => void;
  onDraftChange: (value: Record<string, unknown> | undefined) => void;
}) {
  const [rows, setRows] = useState<AdaptationProposal[]>([]), [routes, setRoutes] = useState<DirectorModelRoute[]>([]);
  const [proposal, setProposal] = useState<AdaptationProposal>(), [routeId, setRouteId] = useState('');
  const [title, setTitle] = useState(''), [direction, setDirection] = useState(''), [selection, setSelection] = useState('');
  const [sourceChecked, setSourceChecked] = useState(false), [previewChecked, setPreviewChecked] = useState(false), [reviewChecked, setReviewChecked] = useState(false);
  const [edited, setEdited] = useState<AdaptationOutput>(), [reviewTitle, setReviewTitle] = useState(''), [dirty, setDirty] = useState(false);
  const [busy, setBusy] = useState(false), [loading, setLoading] = useState(true), [uncertain, setUncertain] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState(''), [denied, setDenied] = useState(false);
  const [discardChecked, setDiscardChecked] = useState(false);
  const active = useRef(true), lock = useRef(false), epoch = useRef(0), revoked = useRef(false);
  const sourceIdentity = `${chapter?.id}:${chapter?.version}:${chapter?.content}`;
  const currentSource = useRef(sourceIdentity); currentSource.current = sourceIdentity;
  const describe = (value: unknown) => value instanceof ApiError ? `${value.message} (${value.problem.code})` : '操作回执未确认。请核对服务端，不要重复调用模型。';
  const failure = (value: unknown, mutation: boolean) => {
    if (!active.current || revoked.current) return;
    setError(describe(value));
    if (mutation && (!(value instanceof ApiError) || value.status === 409 || value.status >= 500)) setUncertain(true);
    if (value instanceof ApiError && [401, 403].includes(value.status)) {
      revoked.current = true; epoch.current++; setDenied(true); setRows([]); setProposal(undefined); setEdited(undefined); setRoutes([]); onDenied();
    }
  };
  const read = async (signal?: AbortSignal) => {
    const ticket = ++epoch.current; setLoading(true);
    try {
      const [proposals, localRoutes] = await Promise.allSettled([client.adaptations(signal), client.adaptationRoutes(signal)]);
      if (!active.current || revoked.current || signal?.aborted || ticket !== epoch.current) return;
      if (proposals.status === 'rejected') throw proposals.reason;
      setRows(proposals.value.items); setError('');
      if (localRoutes.status === 'fulfilled') setRoutes(localRoutes.value.items.filter(row => !row.synthetic));
      else { setRoutes([]); failure(localRoutes.reason, false); }
      // A read never replaces unsaved review edits or silently resumes execution.
    } catch (value) { if (!signal?.aborted && ticket === epoch.current) failure(value, false); }
    finally { if (active.current && !signal?.aborted && ticket === epoch.current) setLoading(false); }
  };
  useEffect(() => { active.current = true; const controller = new AbortController(); void read(controller.signal);
    return () => { active.current = false; epoch.current++; controller.abort(); }; }, [client]);
  useEffect(() => { setSourceChecked(false); setPreviewChecked(false); setReviewChecked(false); }, [sourceIdentity]);
  useEffect(() => setPreviewChecked(false), [proposal?.version, proposal?.model_preview?.preview_digest, routeId]);
  useEffect(() => {
    onDraftChange(!denied && (dirty || title || direction || selection) ? { proposal_id: proposal?.id,
      proposal_version: proposal?.version, title, direction, selection, review_title: reviewTitle, output: edited } : undefined);
  }, [dirty, title, direction, selection, reviewTitle, edited, proposal?.id, proposal?.version, denied, onDraftChange]);
  useEffect(() => {
    if (!dirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);
  const select = (row: AdaptationProposal) => {
    if (!active.current || revoked.current) return;
    setProposal(row); setEdited(row.output ? structuredClone(row.output) : undefined); setReviewTitle(row.title);
    setPreviewChecked(false); setReviewChecked(false); setDirty(false); setDiscardChecked(false); setUncertain(false);
  };
  const update = (row: AdaptationProposal) => { if (!active.current || revoked.current) return;
    setRows(current => [row, ...current.filter(item => item.id !== row.id)]); select(row);
  };
  const run = async (operation: () => Promise<void>) => {
    if (lock.current || !canMutate || revoked.current) return;
    lock.current = true; setBusy(true); onBusyChange(true); setError(''); setNotice('');
    try { await operation(); } catch (value) { failure(value, true); }
    finally { lock.current = false; if (active.current) { setBusy(false); onBusyChange(false); } }
  };
  const change = (value: AdaptationOutput) => { setEdited(value); setDirty(true); setReviewChecked(false); };
  const preview = proposal?.model_preview, execution = proposal?.model_execution;
  const route = routes.find(row => row.route_id === routeId);
  const terminal = proposal && ['APPROVED', 'CANCELLED'].includes(proposal.status);
  const locked = busy || !canMutate || uncertain || denied;
  const sourceMatches = !!chapter && proposal?.chapter_id === chapter.id && proposal.source_version === chapter.version && sourceReady;
  return <details className="creative-model-controls" aria-label="来源感知剧本改编"><summary>从已保存章节改编剧本</summary>
    <p>选择已保存的章节或其中一段，核对实际输入后调用一次本地模型。场景与差异报告先保留为私有建议，人工采用后创建独立剧本文档。</p>
    {loading && <StatusMessage>读取改编建议和本地路由…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="info">{notice}</StatusMessage>}
    {denied ? <StatusMessage tone="warning">权限已失效，改编内容已隐藏。</StatusMessage> : <>
      {uncertain && <StatusMessage tone="warning">本地审核编辑仍保留。请刷新建议列表并核对原任务；不会自动重新生成。</StatusMessage>}
      <fieldset disabled={locked || loading || !sourceReady || !chapter}><legend>改编来源</legend>
        <p>{chapter ? `${chapter.title} · 已保存 v${chapter.version}` : '先在小说工作区选择并保存章节。'}</p>
        <CreativeField label="改编剧本标题"><input value={title} maxLength={240} onChange={event => { setTitle(event.target.value); setSourceChecked(false); }} /></CreativeField>
        <CreativeField label="改编要求"><textarea value={direction} maxLength={4000} onChange={event => { setDirection(event.target.value); setSourceChecked(false); }} /></CreativeField>
        <CreativeField label="已保存章节中的选段（留空使用整章）"><textarea value={selection} maxLength={64000} onChange={event => { setSelection(event.target.value); setSourceChecked(false); }} /></CreativeField>
        <label><input type="checkbox" checked={sourceChecked} onChange={event => setSourceChecked(event.target.checked)} />已选择以上已保存版本作为改编来源</label>
        <Button disabled={!sourceChecked || !title.trim() || (!!selection && !chapter?.content.includes(selection)) || (!selection && (chapter?.content.length || 0) > 64000)} onClick={() => void run(async () => {
          if (!chapter) return; const captured = sourceIdentity;
          const row = await client.createAdaptation({ chapter_id: chapter.id, expected_source_version: chapter.version, title, instruction: direction, selected_text: selection });
          if (currentSource.current === captured) { update(row); setTitle(''); setDirection(''); setSelection(''); setSourceChecked(false); } else if (active.current && !revoked.current) { setRows(items => [row, ...items]); setNotice('原来源的改编建议已保存。当前章节已变化，请在列表核对。'); }
        })}>建立改编建议（尚不调用模型）</Button>
      </fieldset>
      <div className="creative-actions"><Button disabled={busy || loading} onClick={() => void read()}>刷新改编建议列表</Button>{rows.map(row => <Button key={row.id} disabled={busy || dirty} aria-pressed={proposal?.id === row.id} onClick={() => select(row)}>{row.title} · {row.status}</Button>)}</div>
      {dirty && <StatusMessage>审核编辑尚未采用。切换建议前请完成审核，或导出并明确放弃本次编辑。<Button onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify({ proposal_id: proposal?.id, proposal_version: proposal?.version, title: reviewTitle, output: edited }, null, 2)], { type: 'application/json' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'adaptation-review-draft.json'; try { anchor.click(); } finally { URL.revokeObjectURL(url); } }}>导出改编审核草稿</Button><label><input type="checkbox" checked={discardChecked} onChange={event => setDiscardChecked(event.target.checked)} />确认放弃未保存的审核编辑</label><Button disabled={!discardChecked || busy} onClick={() => { if (proposal) select(rows.find(row => row.id === proposal.id) || proposal); }}>载入服务端建议</Button></StatusMessage>}
      {proposal && <section aria-label="改编建议审核"><h3>{proposal.title} · 建议 v{proposal.version}</h3><p>来源章节 {proposal.chapter_id} · v{proposal.source_version}</p>
        {!sourceMatches && !terminal && <StatusMessage tone="warning">当前选中的已保存章节与建议来源不一致。请返回原来源核对；本地编辑保留。</StatusMessage>}
        <details><summary>核对原始选段</summary><pre>{proposal.selected_text}</pre></details>
        {!execution && !terminal && <><CreativeField label="改编本地模型"><select aria-label="改编本地模型" value={routeId} disabled={locked || loading} onChange={event => setRouteId(event.target.value)}><option value="">选择已验证本地模型</option>{routes.map(item => <option key={item.route_id} value={item.route_id} disabled={!item.available}>{item.provider_id} / {item.model_id}{item.available ? '' : ` · ${item.reasons.join(', ')}`}</option>)}</select></CreativeField>
          {!routes.some(item => item.available) && <StatusMessage tone="warning">暂无已验证、零费用的本地路由。可在 Model Center 配置后刷新；此处不会自动启动或下载模型。</StatusMessage>}
          <Button disabled={locked || !sourceMatches || !route?.available} onClick={() => route && void run(async () => update(await client.previewAdaptation(proposal, route.route_id)))}>预览改编模型输入</Button></>}
        {preview && !execution && !terminal && <section aria-label="改编输入预览"><Badge>预览未调用模型</Badge><p>最多 {preview.timeout_seconds} 秒 · 最高费用 0 USD · 无自动重试</p><details><summary>实际 Prompt、参数与来源</summary><pre>{JSON.stringify(preview.request, null, 2)}</pre></details><label><input type="checkbox" disabled={locked || !sourceMatches} checked={previewChecked} onChange={event => setPreviewChecked(event.target.checked)} />已核对完整输入，允许本地调用一次并保存待审建议</label><Button variant="primary" disabled={locked || !sourceMatches || !previewChecked || !preview.execution_available || route?.provider_id !== preview.broker.chosen?.provider_id || route?.model_id !== preview.broker.chosen?.model_id} onClick={() => void run(async () => update(await client.dispatchAdaptation(proposal)))}>确认改编调用</Button></section>}
        {execution && <><Badge tone={proposal.status === 'MODEL_UNAVAILABLE' ? 'warning' : 'info'}>{execution.status}</Badge><p>Job {execution.job_id} · {execution.receipt_state}</p>{execution.failure_code && <p>{execution.failure_code}</p>}{!terminal && <div className="creative-actions"><Button disabled={locked || dirty} onClick={() => void run(async () => update(await client.refreshAdaptation(proposal)))}>核对改编模型结果</Button><Button disabled={busy || !canMutate} onClick={() => void run(async () => update(await client.cancelAdaptation(proposal)))}>取消改编建议</Button></div>}</>}
        {edited && <fieldset disabled={locked || proposal.status !== 'NEEDS_REVIEW' || !sourceMatches}><legend>人工核对场景与改编差异</legend>
          <CreativeField label="采用后的剧本标题"><input maxLength={240} value={reviewTitle} onChange={event => { setReviewTitle(event.target.value); setDirty(true); setReviewChecked(false); }} /></CreativeField>
          {edited.scenes.map((scene, index) => <details key={scene.id} open><summary>场景 {scene.sequence}</summary><CreativeField label={`改编场景 ${index + 1} 标题`}><input maxLength={500} value={scene.heading} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, heading: event.target.value } : item) })} /></CreativeField><CreativeField label={`改编场景 ${index + 1} 动作`}><textarea maxLength={32000} value={scene.action} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, action: event.target.value } : item) })} /></CreativeField>{scene.dialogue.map((line, lineIndex) => <CreativeField key={lineIndex} label={`改编场景 ${index + 1} 对白 ${lineIndex + 1}（${line.speaker}）`}><textarea maxLength={16000} value={line.text} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, dialogue: item.dialogue.map((dialogue, i) => i === lineIndex ? { ...dialogue, text: event.target.value } : dialogue) } : item) })} /></CreativeField>)}</details>)}
          <CreativeField label="改编差异摘要"><textarea maxLength={4000} value={edited.report.summary} onChange={event => change({ ...edited, report: { ...edited.report, summary: event.target.value } })} /></CreativeField>
          {edited.report.changes.map((item, index) => <section key={item.id} aria-label={`改编差异 ${index + 1}`}><Badge tone={item.kind === 'INFERENCE' ? 'warning' : 'info'}>{item.kind}</Badge><p>对应场景：{item.scene_ids.join(', ') || '已省略'}</p><blockquote>{item.source_quote || '推断内容无原文引用，需特别核对'}</blockquote><CreativeField label={`改编差异 ${index + 1} 说明`}><textarea maxLength={4000} value={item.note} onChange={event => change({ ...edited, report: { ...edited.report, changes: edited.report.changes.map(change => change.id === item.id ? { ...change, note: event.target.value } : change) } })} /></CreativeField></section>)}
          <label><input type="checkbox" checked={reviewChecked} onChange={event => setReviewChecked(event.target.checked)} />已核对原文、场景及删改推断，创建独立剧本文档</label><Button variant="primary" disabled={!reviewChecked || !reviewTitle.trim()} onClick={() => void run(async () => { const result = await client.reviewAdaptation(proposal, reviewTitle, edited); if (!active.current || revoked.current) return; update(result.proposal); onDocument(result.document); setNotice('独立剧本已保存为 v1，差异报告绑定此次采用版本。'); })}>审核并创建剧本</Button>
        </fieldset>}
      </section>}
    </>}
  </details>;
}
