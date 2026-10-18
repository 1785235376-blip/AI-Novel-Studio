import { useEffect, useRef, useState } from 'react';
import { ApiError, type Chapter } from '../api';
import { Badge, Button, StatusMessage } from '../ui/primitives';
import { CreativeField } from './CreativeCanvas';
import type { AdaptationOutput, AdaptationProposal, CreativeClient, DirectorModelRoute } from './client';
import type { CreativeDocument } from './types';

const proposalIdentity = (row: AdaptationProposal) => JSON.stringify([row.id, row.version, row.status, row.source_mode,
  row.chapter_id, row.source_version, row.source_digest, row.selection_digest, row.selected_text,
  row.ordered_sources_digest, row.sources, row.output_digest, row.model_preview?.preview_digest]);

/** Feature content only. Creative owns proposals and documents; no manuscript writes. */
export function SourceAdaptationPanel({ client, chapter, savedChapters, savedChaptersReady = false, loadSavedChapter, onRefreshSavedChapters, sourceReady, canMutate, onDocument, onDenied, onBusyChange, onDraftChange }: {
  client: CreativeClient; chapter?: Chapter; savedChapters?: Chapter[]; savedChaptersReady?: boolean; loadSavedChapter?: (id: string) => Promise<Chapter>; onRefreshSavedChapters?: () => void; sourceReady: boolean; canMutate: boolean;
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
  const [quarantineRequested, setQuarantined] = useState(false);
  const [proposalClient, setProposalClient] = useState<CreativeClient>();
  const [orderedMode, setOrderedMode] = useState(false), [sourceIds, setSourceIds] = useState<string[]>([]);
  const listed = savedChapters?.filter(row => !row.is_archived) ?? (chapter ? [chapter] : []);
  const detailIds = [...new Set([...sourceIds, ...(proposal?.source_mode === 'ORDERED_CHAPTERS' ? (proposal.sources || []).map(row => row.chapter_id) : proposal ? [proposal.chapter_id] : [])])];
  const [detailRefresh, setDetailRefresh] = useState(0);
  const detailIdentity = JSON.stringify([detailRefresh, detailIds.map(id => [id, listed.find(row => row.id === id)?.version])]);
  const [details, setDetails] = useState<{ identity: string; rows: Chapter[] }>();
  const detailFailureRefresh = useRef<number>();
  const proposalDetailIdentity = proposal ? JSON.stringify([proposalIdentity(proposal), detailIdentity, detailRefresh]) : '';
  const [proposalDetailProof, setProposalDetailProof] = useState<{ identity: string; client: CreativeClient }>();
  const quarantined = quarantineRequested || (!!proposal && (proposalClient !== client || (!!loadSavedChapter && (!savedChaptersReady || proposalDetailProof?.client !== client || proposalDetailProof.identity !== proposalDetailIdentity))));
  const detailsReady = !loadSavedChapter || details?.identity === detailIdentity;
  const saved = listed.map(row => detailsReady && loadSavedChapter ? details?.rows.find(item => item.id === row.id) || row : row);
  const selectedSources = sourceIds.map(id => saved.find(row => row.id === id));
  const sourceTotal = selectedSources.reduce((sum, row) => sum + Array.from(row?.content || '').length, 0);
  const validSources = savedChaptersReady && detailsReady && sourceIds.length >= 2 && sourceIds.length <= 16 && new Set(sourceIds).size === sourceIds.length &&
    selectedSources.every(row => row && typeof row.content === 'string' && row.content.trim() && Array.from(row.content).length <= 8000 && Number.isInteger(row.version)) && sourceTotal <= 32000;
  const savedIdentity = JSON.stringify(saved.map(row => [row.id, row.version, row.content]));
  const orderedIdentity = JSON.stringify([sourceIds, savedIdentity, savedChaptersReady]);
  const changeSources = (ids: string[]) => { setSourceIds(ids); setSourceChecked(false); };
  const moveSource = (index: number, offset: number) => { const ids = [...sourceIds]; [ids[index], ids[index + offset]] = [ids[index + offset], ids[index]]; changeSources(ids); };
  const active = useRef(true), lock = useRef(false), epoch = useRef(0), revoked = useRef(false);
  const selectionState = useRef({ id: proposal?.id, dirty, proposal });
  selectionState.current = { id: proposal?.id, dirty, proposal };
  const sourceIdentity = `${chapter?.id}:${chapter?.version}:${chapter?.content}`;
  const creationIdentity = orderedMode ? orderedIdentity : sourceIdentity;
  const currentSource = useRef(creationIdentity); currentSource.current = creationIdentity;
  const describe = (value: unknown) => value instanceof ApiError ? `${value.message} (${value.problem.code})` : '操作回执未确认。请核对服务端，不要重复调用模型。';
  const failure = (value: unknown, mutation: boolean) => {
    if (!active.current || revoked.current) return;
    setError(describe(value));
    if (mutation && (!(value instanceof ApiError) || value.status === 409 || value.status >= 500)) setUncertain(true);
    if (mutation && value instanceof ApiError && [404, 409].includes(value.status)) {
      setQuarantined(true); setRows([]); setReviewChecked(false); setPreviewChecked(false);
    }
    if (value instanceof ApiError && [401, 403].includes(value.status)) {
      revoked.current = true; epoch.current++; setDenied(true); setRows([]); setProposal(undefined); setEdited(undefined); setRoutes([]); onDenied();
    }
  };
  useEffect(() => {
    if (!loadSavedChapter) return;
    if (!savedChaptersReady || detailIds.length > 32) { setDetails(undefined); setProposalDetailProof(undefined); return; }
    let disposed = false;
    // Separate proposal authorization proof from creation-only detail errors. Never
    // let a successful list refresh override a missing or unverified chapter detail.
    setDetails(undefined); setProposalDetailProof(undefined);
    void Promise.allSettled(detailIds.map(id => Promise.resolve().then(() => loadSavedChapter(id)))).then(results => {
      if (disposed || !active.current || revoked.current) return;
      const values: Chapter[] = [];
      for (let index = 0; index < results.length; index++) {
        const result = results[index];
        if (result.status === 'rejected') { failure(result.reason, false); continue; }
        const row = result.value;
        if (!row || row.id !== detailIds[index] || row.version !== listed.find(item => item.id === row.id)?.version || row.is_archived || typeof row.content !== 'string') {
          setError('来源详情与列表版本不一致，请刷新已保存章节后核对。'); continue;
        }
        values.push(row);
      }
      if (revoked.current) return;
      if (values.length === detailIds.length) setDetails({ identity: detailIdentity, rows: values });
      if (proposal) {
        const sources = proposal.source_mode === 'ORDERED_CHAPTERS' ? proposal.sources || [] : [{ chapter_id: proposal.chapter_id, source_version: proposal.source_version, selected_text: proposal.selected_text }];
        const verified = sources.length > 0 && sources.every(source => {
          const row = values.find(item => item.id === source.chapter_id);
          return row?.version === source.source_version && (proposal.source_mode === 'ORDERED_CHAPTERS' ? row.content === source.selected_text : row.content.includes(source.selected_text));
        });
        if (!verified) { detailFailureRefresh.current = detailRefresh; setReviewChecked(false); setPreviewChecked(false); }
        else if (detailFailureRefresh.current === undefined || detailRefresh > detailFailureRefresh.current) {
          setProposalDetailProof({ identity: proposalDetailIdentity, client });
        }
      }
    });
    return () => { disposed = true; };
  }, [detailIdentity, detailRefresh, loadSavedChapter, savedChaptersReady, proposalDetailIdentity, client]);
  const read = async (signal?: AbortSignal) => {
    const ticket = ++epoch.current; setLoading(true); setRows([]);
    if (selectionState.current.id) { setQuarantined(true); setReviewChecked(false); setPreviewChecked(false); }
    try {
      const [proposals, localRoutes] = await Promise.allSettled([client.adaptations(signal), client.adaptationRoutes(signal)]);
      if (!active.current || revoked.current || signal?.aborted || ticket !== epoch.current) return;
      if (proposals.status === 'rejected') throw proposals.reason;
      setRows(proposals.value.items); setError('');
      const selected = proposals.value.items.find(item => item.id === selectionState.current.id);
      const previous = selectionState.current.proposal;
      if (selected && previous && proposalIdentity(selected) === proposalIdentity(previous)) {
        setProposal(selected); setQuarantined(false); // Explicit refresh verified the exact cached revision; keep local edits.
      } else if (previous) setQuarantined(true);
      if (localRoutes.status === 'fulfilled') setRoutes(localRoutes.value.items.filter(row => !row.synthetic));
      else { setRoutes([]); failure(localRoutes.reason, false); }
      // A read can converge an already completed archive, but never replaces unsaved edits or resumes execution.
    } catch (value) { if (!signal?.aborted && ticket === epoch.current) failure(value, false); }
    finally { if (active.current && !signal?.aborted && ticket === epoch.current) setLoading(false); }
  };
  useEffect(() => { active.current = true; setRows([]); setProposal(undefined); setEdited(undefined); setDirty(false); setQuarantined(false); selectionState.current = { id: undefined, dirty: false, proposal: undefined }; const controller = new AbortController(); void read(controller.signal);
    return () => { active.current = false; epoch.current++; controller.abort(); }; }, [client]);
  useEffect(() => { setSourceChecked(false); }, [sourceIdentity, orderedIdentity, orderedMode]);
  useEffect(() => setPreviewChecked(false), [proposal?.version, proposal?.model_preview?.preview_digest, routeId]);
  useEffect(() => {
    onDraftChange(quarantined ? { protected_review_pending: true } : !denied && (dirty || title || direction || selection || sourceIds.length) ? { proposal_id: proposal?.id,
      proposal_version: proposal?.version, title, direction, selection, source_ids: sourceIds, ordered_mode: orderedMode, review_title: reviewTitle, output: edited } : undefined);
  }, [dirty, title, direction, selection, sourceIds, orderedMode, reviewTitle, edited, proposal?.id, proposal?.version, denied, quarantined, onDraftChange]);
  useEffect(() => {
    if (!dirty) return;
    const prevent = (event: BeforeUnloadEvent) => { event.preventDefault(); event.returnValue = ''; };
    window.addEventListener('beforeunload', prevent); return () => window.removeEventListener('beforeunload', prevent);
  }, [dirty]);
  const select = (row: AdaptationProposal) => {
    if (!active.current || revoked.current) return;
    detailFailureRefresh.current = undefined; setProposalDetailProof(undefined); setProposalClient(client); setQuarantined(false); setProposal(row); setEdited(row.output ? structuredClone(row.output) : undefined); setReviewTitle(row.title);
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
  const locked = busy || !canMutate || uncertain || denied || quarantined;
  const proposalSources = proposal?.source_mode === 'ORDERED_CHAPTERS' ? proposal.sources : undefined;
  const sourceMatches = proposal?.source_mode === 'ORDERED_CHAPTERS'
    ? savedChaptersReady && detailsReady && !!proposalSources && proposalSources.length >= 2 && proposalSources.length <= 16 && new Set(proposalSources.map(row => row.chapter_id)).size === proposalSources.length && proposalSources.every((source, index) => {
      const current = saved.find(row => row.id === source.chapter_id);
      return source.ordinal === index + 1 && current?.version === source.source_version && current.content === source.selected_text;
    })
    : !!proposal && (savedChapters ? savedChaptersReady && detailsReady : sourceReady) && saved.some(row => row.id === proposal.chapter_id && row.version === proposal.source_version && row.content.includes(proposal.selected_text));
  const reviewSourceIdentity = JSON.stringify([proposal?.id, sourceMatches, proposalSources?.map(row => [row.chapter_id, row.source_version])]);
  useEffect(() => { setPreviewChecked(false); setReviewChecked(false); }, [reviewSourceIdentity]);
  return <details className="creative-model-controls" aria-label="来源感知剧本改编"><summary>从已保存章节改编剧本</summary>
    <p>选择已保存的章节或其中一段，核对实际输入后调用一次本地模型。场景与差异报告先保留为私有建议，人工采用后创建独立剧本文档。</p>
    {loading && <StatusMessage>读取改编建议和本地路由…</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="info">{notice}</StatusMessage>}
    {denied ? <StatusMessage tone="warning">权限已失效，改编内容已隐藏。</StatusMessage> : <>
      {uncertain && <StatusMessage tone="warning">本地审核编辑仍保留。请刷新建议列表并核对原任务；不会自动重新生成。</StatusMessage>}
      <fieldset disabled={locked || loading || dirty}><legend>改编来源</legend>
        <CreativeField label="改编来源方式"><select value={orderedMode ? "ordered" : "single"} onChange={event => { setOrderedMode(event.target.value === "ordered"); setSourceChecked(false); }}><option value="single">当前章节或选段</option><option value="ordered" disabled={!savedChaptersReady}>按顺序选择多个已保存章节</option></select></CreativeField>
        {orderedMode ? <section aria-label="有序章节来源">
          <p>选择 2–16 个完整的已保存章节，每章最多 8000 字符，合计最多 32000 字符。不截断，也不包含未保存编辑。</p>
          {(!savedChaptersReady || !detailsReady) && <StatusMessage tone="warning">已保存章节列表尚未就绪，请等待刷新完成。</StatusMessage>}
          {saved.map(row => <label className="creative-review-check" key={row.id}><input type="checkbox" aria-label={`选择来源 ${row.title}`} checked={sourceIds.includes(row.id)} disabled={!savedChaptersReady || (!sourceIds.includes(row.id) && sourceIds.length >= 16)} onChange={event => changeSources(event.target.checked ? [...sourceIds, row.id] : sourceIds.filter(id => id !== row.id))} />{row.title} · v{row.version} · {Array.from(row.content || '').length} 字符</label>)}
          <ol>{sourceIds.map((id, index) => { const row = saved.find(item => item.id === id); return <li key={id}>{row ? `${row.title} · v${row.version}` : `${id} · 来源已不可用`}<Button aria-label={`上移来源 ${index + 1}`} disabled={index === 0} onClick={() => moveSource(index, -1)}>上移</Button><Button aria-label={`下移来源 ${index + 1}`} disabled={index === sourceIds.length - 1} onClick={() => moveSource(index, 1)}>下移</Button></li>; })}</ol>
          <p>{sourceIds.length} 个章节 · 合计 {sourceTotal} / 32000 字符</p>
          {!validSources && <StatusMessage tone="warning">请核对数量、各章长度、总长度和可用的已保存版本。</StatusMessage>}
          <details><summary>核对有序完整来源</summary>{detailsReady && selectedSources.map((row, index) => row && <section key={row.id}><h4>{index + 1}. {row.title} · v{row.version}</h4><pre>{row.content}</pre></section>)}</details>
        </section> : <p>{chapter ? `${chapter.title} · 已保存 v${chapter.version}` : '先在小说工作区选择并保存章节。'}</p>}
        <CreativeField label="改编剧本标题"><input value={title} maxLength={240} onChange={event => { setTitle(event.target.value); setSourceChecked(false); }} /></CreativeField>
        <CreativeField label="改编要求"><textarea value={direction} maxLength={4000} onChange={event => { setDirection(event.target.value); setSourceChecked(false); }} /></CreativeField>
        {!orderedMode && <CreativeField label="已保存章节中的选段（留空使用整章）"><textarea value={selection} maxLength={64000} onChange={event => { setSelection(event.target.value); setSourceChecked(false); }} /></CreativeField>}
        <label><input type="checkbox" checked={sourceChecked} onChange={event => setSourceChecked(event.target.checked)} />已选择以上已保存版本作为改编来源</label>
        <Button disabled={!sourceChecked || !title.trim() || (orderedMode ? !validSources : !sourceReady || !chapter || (!!selection && !chapter.content.includes(selection)) || (!selection && chapter.content.length > 64000))} onClick={() => void run(async () => {
          if (orderedMode ? !validSources : !chapter || !sourceReady) return; const captured = creationIdentity;
          const row = await client.createAdaptation(orderedMode
            ? { title, instruction: direction, sources: selectedSources.map(row => ({ chapter_id: row!.id, expected_source_version: row!.version })) }
            : { chapter_id: chapter!.id, expected_source_version: chapter!.version, title, instruction: direction, selected_text: selection });
          if (currentSource.current === captured) { update(row); setTitle(''); setDirection(''); setSelection(''); setSourceIds([]); setSourceChecked(false); } else if (active.current && !revoked.current) { setRows(items => [row, ...items]); setNotice('原来源的改编建议已保存。当前章节已变化，请在列表核对。'); }
        })}>建立改编建议（尚不调用模型）</Button>
      </fieldset>
      <div className="creative-actions"><Button disabled={busy || loading} onClick={() => { setDetailRefresh(value => value + 1); onRefreshSavedChapters?.(); void read(); }}>刷新改编建议列表</Button>{rows.map(row => <Button key={row.id} disabled={busy || loading || dirty || quarantined} aria-pressed={proposal?.id === row.id} onClick={() => select(row)}>{row.title} · {row.status}</Button>)}</div>
      {dirty && !quarantined && <StatusMessage>审核编辑尚未采用。切换建议前请完成审核，或导出并明确放弃本次编辑。<Button onClick={() => { const url = URL.createObjectURL(new Blob([JSON.stringify({ proposal_id: proposal?.id, proposal_version: proposal?.version, title: reviewTitle, output: edited }, null, 2)], { type: 'application/json' })); const anchor = document.createElement('a'); anchor.href = url; anchor.download = 'adaptation-review-draft.json'; try { anchor.click(); } finally { URL.revokeObjectURL(url); } }}>导出改编审核草稿</Button><label><input type="checkbox" checked={discardChecked} onChange={event => setDiscardChecked(event.target.checked)} />确认放弃未保存的审核编辑</label><Button disabled={!discardChecked || busy} onClick={() => { if (proposal) select(rows.find(row => row.id === proposal.id) || proposal); }}>载入服务端建议</Button></StatusMessage>}
      {quarantined && <StatusMessage tone="warning">建议访问或版本尚未重新确认，缓存内容和导出已隐藏。未保存审核编辑仅在本地保留；刷新并验证完全相同的建议后才能继续。
        <label><input type="checkbox" checked={discardChecked} onChange={event => setDiscardChecked(event.target.checked)} />确认放弃隐藏的审核草稿</label>
        <Button disabled={!discardChecked || busy || loading} onClick={() => { setProposal(undefined); setEdited(undefined); setReviewTitle(''); setDirty(false); setQuarantined(false); setDiscardChecked(false); setUncertain(false); }}>放弃隐藏草稿</Button>
      </StatusMessage>}
      {proposal && !quarantined && <section aria-label="改编建议审核"><h3>{proposal.title} · 建议 v{proposal.version}</h3><p>来源章节 {proposal.chapter_id} · v{proposal.source_version}</p>
        {!sourceMatches && !terminal && <StatusMessage tone="warning">已保存章节与建议来源版本不一致或尚未就绪。请核对所有原始来源；本地编辑保留。</StatusMessage>}
        <details><summary>核对原始选段</summary>{proposalSources ? proposalSources.map(source => <section key={source.ordinal}><h4>来源 {source.ordinal} · {source.chapter_id} · v{source.source_version}</h4><pre>{source.selected_text}</pre></section>) : <pre>{proposal.selected_text}</pre>}</details>
        {!execution && !terminal && <><CreativeField label="改编本地模型"><select aria-label="改编本地模型" value={routeId} disabled={locked || loading} onChange={event => setRouteId(event.target.value)}><option value="">选择已验证本地模型</option>{routes.map(item => <option key={item.route_id} value={item.route_id} disabled={!item.available}>{item.provider_id} / {item.model_id}{item.available ? '' : ` · ${item.reasons.join(', ')}`}</option>)}</select></CreativeField>
          {!routes.some(item => item.available) && <StatusMessage tone="warning">暂无已验证、零费用的本地路由。可在 Model Center 配置后刷新；此处不会自动启动或下载模型。</StatusMessage>}
          <Button disabled={locked || !sourceMatches || !route?.available} onClick={() => route && void run(async () => update(await client.previewAdaptation(proposal, route.route_id)))}>预览改编模型输入</Button></>}
        {preview && !execution && !terminal && <section aria-label="改编输入预览"><Badge>预览未调用模型</Badge><p>最多 {preview.timeout_seconds} 秒 · 最高费用 0 USD · 无自动重试</p><p>此次确认会将完成的原始输出与模型、Prompt、参数、来源回执自动存为私有草稿资产；人工采用后记录资产审核版本，不改写原始输出或小说正文。</p><details><summary>实际 Prompt、参数与来源</summary><pre>{JSON.stringify(preview.request, null, 2)}</pre></details><label><input type="checkbox" disabled={locked || !sourceMatches} checked={previewChecked} onChange={event => setPreviewChecked(event.target.checked)} />已核对完整输入，允许本地调用一次并保存待审建议</label><Button variant="primary" disabled={locked || !sourceMatches || !previewChecked || !preview.execution_available || route?.provider_id !== preview.broker.chosen?.provider_id || route?.model_id !== preview.broker.chosen?.model_id} onClick={() => void run(async () => update(await client.dispatchAdaptation(proposal)))}>确认改编调用</Button></section>}
        {execution && <><Badge tone={proposal.status === 'MODEL_UNAVAILABLE' ? 'warning' : 'info'}>{execution.status}</Badge><p>Job {execution.job_id} · {execution.receipt_state}</p>{execution.failure_code && <p>{execution.failure_code}</p>}{!terminal && <div className="creative-actions"><Button disabled={locked || dirty} onClick={() => void run(async () => update(await client.refreshAdaptation(proposal)))}>核对改编模型结果</Button><Button disabled={busy || !canMutate || dirty} onClick={() => void run(async () => update(await client.cancelAdaptation(proposal)))}>取消改编建议</Button></div>}</>}
        {proposal.asset_output && <section aria-label="改编资产归档回执"><Badge tone={proposal.asset_output.state === 'INCOMPLETE' ? 'warning' : 'info'}>{proposal.asset_output.state === 'APPROVED' ? '资产已记录人工采用' : proposal.asset_output.state === 'DRAFT' ? '原始输出已归档为私有草稿' : proposal.asset_output.state === 'INCOMPLETE' ? '资产归档尚未完成' : '等待可验证的完成结果'}</Badge>
          {proposal.asset_output.asset_id && <p>TextAsset {proposal.asset_output.asset_id} · v{proposal.asset_output.version} · SHA-256 {proposal.asset_output.sha256}</p>}
          {proposal.asset_output.state === 'INCOMPLETE' && <StatusMessage tone="warning">原任务不会重放。现有刷新或重新打开会核对并恢复归档；{proposal.status === 'APPROVED' ? '剧本文档已保存，资产审核版本仍待同步。' : '归档确认前暂不显示可采用内容。'}</StatusMessage>}
          {proposal.asset_output.execution_receipt && <details><summary>模型、输入、参数与工作流回执（未验证质量）</summary><pre>{JSON.stringify(proposal.asset_output.execution_receipt, null, 2)}</pre></details>}
        </section>}
        {edited && <fieldset disabled={locked || proposal.status !== 'NEEDS_REVIEW' || !sourceMatches}><legend>人工核对场景与改编差异</legend>
          <CreativeField label="采用后的剧本标题"><input maxLength={240} value={reviewTitle} onChange={event => { setReviewTitle(event.target.value); setDirty(true); setReviewChecked(false); }} /></CreativeField>
          {edited.scenes.map((scene, index) => <details key={scene.id} open><summary>场景 {scene.sequence}{scene.source_ordinal ? ` · 来源 ${scene.source_ordinal}` : ""}</summary><CreativeField label={`改编场景 ${index + 1} 标题`}><input maxLength={500} value={scene.heading} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, heading: event.target.value } : item) })} /></CreativeField><CreativeField label={`改编场景 ${index + 1} 动作`}><textarea maxLength={32000} value={scene.action} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, action: event.target.value } : item) })} /></CreativeField>{scene.dialogue.map((line, lineIndex) => <CreativeField key={lineIndex} label={`改编场景 ${index + 1} 对白 ${lineIndex + 1}（${line.speaker}）`}><textarea maxLength={16000} value={line.text} onChange={event => change({ ...edited, scenes: edited.scenes.map(item => item.id === scene.id ? { ...item, dialogue: item.dialogue.map((dialogue, i) => i === lineIndex ? { ...dialogue, text: event.target.value } : dialogue) } : item) })} /></CreativeField>)}</details>)}
          <CreativeField label="改编差异摘要"><textarea maxLength={4000} value={edited.report.summary} onChange={event => change({ ...edited, report: { ...edited.report, summary: event.target.value } })} /></CreativeField>
          {edited.report.changes.map((item, index) => <section key={item.id} aria-label={`改编差异 ${index + 1}`}><Badge tone={item.kind === 'INFERENCE' ? 'warning' : 'info'}>{item.kind}</Badge><p>{item.source_ordinal ? `来源 ${item.source_ordinal} · ` : ""}对应场景：{item.scene_ids.join(', ') || '已省略'}</p><blockquote>{item.source_quote || '推断内容无原文引用，需特别核对'}</blockquote><CreativeField label={`改编差异 ${index + 1} 说明`}><textarea maxLength={4000} value={item.note} onChange={event => change({ ...edited, report: { ...edited.report, changes: edited.report.changes.map(change => change.id === item.id ? { ...change, note: event.target.value } : change) } })} /></CreativeField></section>)}
          <label><input type="checkbox" checked={reviewChecked} onChange={event => setReviewChecked(event.target.checked)} />已核对原文、场景及删改推断，创建独立剧本文档</label><Button variant="primary" disabled={!reviewChecked || !reviewTitle.trim()} onClick={() => void run(async () => { const result = await client.reviewAdaptation(proposal, reviewTitle, edited); if (!active.current || revoked.current) return; update(result.proposal); onDocument(result.document); setNotice('独立剧本已保存为 v1，差异报告绑定此次采用版本。'); })}>审核并创建剧本</Button>
        </fieldset>}
      </section>}
    </>}
  </details>;
}
