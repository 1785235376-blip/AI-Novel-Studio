import { useEffect, useMemo, useRef, useState } from 'react';
import { api as originalApi, type Chapter, type CollaborationContext } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { AuthorRequestPreviewPanel } from '../novel/AuthorRequestPreviewPanel';
import { AuthorRequestControls } from '../novel/AuthorRequestControls';
import { authorContextRequest, defaultAuthorRequestScope, type AuthorRequestScope, type AuthorPreviewReceipt, type AuthorRequestBody } from '../novel/authorContextClient';
import type { ExperimentalClient } from './api';
import { Field, ResourceState, useAction, useResource } from './shared';
import { revisionIntelligenceClient, type RevisionPreview, type RevisionProposal, type RevisionSelection, type SelectionReceipt } from './revisionIntelligenceClient';

export type RevisionGenerationOptions = { enabled: boolean; novelId: string; context: CollaborationContext; providerId?: string; modelId?: string; profile: 'LOCAL_ONLY' | 'HYBRID' | 'QUALITY' };
export type RevisionIntelligenceProps = { client: ExperimentalClient; chapter?: Chapter; selection?: { from: number; to: number; text: string }; saved?: boolean; onChapterSaved?: (chapter: Chapter) => void; generation?: RevisionGenerationOptions; onHistory?: () => void };
let scopeSequence = 0;
export function RevisionIntelligencePanel(props: RevisionIntelligenceProps) {
  const identity = useMemo(() => ++scopeSequence, [props.client, props.chapter?.id, props.chapter?.version]);
  return <RevisionBody key={identity} {...props} />;
}
function RevisionBody({ client, chapter, selection, saved = false, onChapterSaved, generation, onHistory }: RevisionIntelligenceProps) {
  const api = useMemo(() => revisionIntelligenceClient(client), [client]);
  const catalog = useResource(signal => api.catalog(chapter?.id, signal), [api, chapter?.id]);
  const history = useResource(signal => api.proposals(signal), [api]);
  const milestones = useResource(signal => api.milestones(signal), [api]);
  const [receipt, setReceipt] = useState<SelectionReceipt>(), [candidates, setCandidates] = useState<Record<string, string>>({});
  const [goal, setGoal] = useState(''), [jobId, setJobId] = useState<string>(), [reviewing, setReviewing] = useState<RevisionProposal>();
  const [milestoneTitle, setMilestoneTitle] = useState('');
  const epoch = useRef(0), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { if (!saved) { epoch.current++; setReceipt(undefined); setReviewing(undefined); setJobId(undefined); } }, [saved]);
  const action = useAction();
  const select = (value: RevisionSelection) => action.run(async () => {
    const ticket = ++epoch.current; setReceipt(undefined); setJobId(undefined);
    const result = await api.selection(value);
    if (alive.current && ticket === epoch.current) { setReceipt(result); setCandidates(Object.fromEntries(result.blocks.map(b => [b.anchor_id, b.before]))); }
  }, '已校验保存版本、精确选区与段落锚点，尚未调用模型。');
  const saveResult = (value: Chapter) => { if (alive.current) { setReceipt(undefined); setReviewing(undefined); setJobId(undefined); onChapterSaved?.(value); catalog.reload(); history.reload(); } };
  return <div className="experimental-section">
    <Panel title="选区修订与段落保护">
      <p>复用原编辑器、章节版本和历史。只修改逐项批准的文字；其他文字、格式和未批准候选保留。这里的锁是应用 AI 编辑约束。</p>
      {!chapter && <EmptyState title="先选择章节" detail="从原章节树打开已保存章节，再选择编辑器文字或下方段落。" />}
      {chapter && <p>当前：{chapter.title} · 已保存版本 v{chapter.version}</p>}
      {!saved && chapter && <StatusMessage tone="warning">先保存正文并解决冲突，再校验选区、生成或采用修订。</StatusMessage>}
      <ResourceState loading={catalog.loading} error={catalog.error} />
      {catalog.data && !catalog.data.branch_sources_available && <StatusMessage tone="warning">当前章节仓库尚无分支隔离正文，不会借用主分支内容执行修订。</StatusMessage>}
      <div className="experimental-actions"><Button disabled={!chapter || !saved || !selection?.text || action.busy} onClick={() => chapter && selection && void select({ chapter_id: chapter.id, chapter_version: chapter.version, from_pos: selection.from, to_pos: selection.to, text: selection.text })}>校验编辑器选区</Button><Button disabled={catalog.loading || action.busy} onClick={catalog.reload}>重读章节段落</Button>{onHistory && <Button onClick={onHistory}>打开原版本历史</Button>}</div>
      {!catalog.loading && !catalog.error && chapter && <details><summary>从当前已保存段落选择</summary><div className="experimental-list">{catalog.data?.blocks.map((block, index) => <article className="experimental-record" key={block.path.join('.')}>
        <div className="experimental-actions"><strong>第 {index + 1} 段</strong><Badge tone={block.lock_state === 'STALE' ? 'warning' : 'neutral'}>{block.lock_state === 'LOCKED' ? 'AI 已锁定' : block.lock_state === 'STALE' ? '锁已漂移，仍阻止 AI' : '未锁定'}</Badge></div>
        <p className="writing-reference-text">{block.text || '空段落'}</p>
        <Button disabled={!saved || !block.supported || !block.text || action.busy} onClick={() => void select({ chapter_id: chapter.id, chapter_version: chapter.version, from_pos: block.from_pos, to_pos: block.to_pos, text: block.text })}>选择第 {index + 1} 段</Button>
        {block.lock_state !== 'UNLOCKED' && <Button disabled={!saved || !onChapterSaved || action.busy || !catalog.data?.document_digest} onClick={() => void action.run(async () => { saveResult(await api.unlockBlock(chapter, block.path, catalog.data!.document_digest!)); }, '已明确解除此段落 AI 锁。')}>明确解锁第 {index + 1} 段</Button>}
      </article>)}</div></details>}
      {receipt && <section aria-label="已校验修订选区"><StatusMessage>已绑定 v{receipt.selection.chapter_version} 的 {receipt.blocks.length} 个文字区块。</StatusMessage>
        <Field label="修订目标与保留要求"><textarea value={goal} maxLength={1000} onChange={e => setGoal(e.target.value)} /></Field>
        {receipt.blocks.map((block, index) => <article className="experimental-record" key={block.anchor_id}>
          <strong>区块 {index + 1} 原文</strong><p className="writing-reference-text">{block.before}</p>
          {block.lock_state !== 'UNLOCKED' && <StatusMessage tone="warning">此段落已锁定或锁已漂移。采用前必须明确解锁并重新审核。</StatusMessage>}
          <Field label={`区块 ${index + 1} 候选文字`}><textarea value={candidates[block.anchor_id] ?? ''} maxLength={100000} onChange={e => { setJobId(undefined); setCandidates(old => ({ ...old, [block.anchor_id]: e.target.value })); }} /></Field>
        </article>)}
        <StatusMessage>{jobId ? '候选来自已授权生成任务，采用时仍检查原任务授权。' : '手工输入 / 导入候选：可验证差异与局部写入，不代表真实 AI 质量。'}</StatusMessage>
        <div className="experimental-actions"><Button disabled={action.busy || !saved || !receipt.blocks.some(b => candidates[b.anchor_id] !== b.before)} onClick={() => void action.run(async () => {
          const ticket = epoch.current;
          const result = await api.create(receipt, receipt.blocks.map(b => ({ anchor_id: b.anchor_id, text: candidates[b.anchor_id] ?? '' })), goal, jobId);
          if (alive.current && ticket === epoch.current) { setReviewing(result); history.reload(); }
        }, '候选已保存，正文未改变。')}>保存候选并逐项审核</Button>
        <Button disabled={action.busy || !saved || !onChapterSaved || receipt.blocks.some(b => b.lock_state !== 'UNLOCKED')} onClick={() => void action.run(async () => { saveResult(await api.locks(receipt, 'lock')); }, '已锁定所在完整段落，并创建原版本检查点。')}>锁定所在段落，禁止 AI 修改</Button>
        <Button disabled={action.busy || !saved || !onChapterSaved || receipt.blocks.some(b => b.lock_state === 'UNLOCKED')} onClick={() => void action.run(async () => { saveResult(await api.locks(receipt, 'unlock')); }, '已明确解除段落 AI 锁，请重新选择当前版本。')}>明确解锁所在段落</Button></div>
        <p>锁定完整所在段落。手动改文仍可进行，旧锁漂移后仍禁止 AI 采用。关闭实验入口或切到 V1 模式不会自动解锁。</p>
        {generation?.enabled && <SelectionGeneration key={receipt.selection_digest} options={generation} selection={receipt} goal={goal} saved={saved} onCandidate={(texts, id) => { setCandidates(Object.fromEntries(receipt.blocks.map((block, i) => [block.anchor_id, texts[i]]))); setJobId(id); }} />}
        {!generation?.enabled && <StatusMessage>选区 AI 未启用；手工候选审核仍可使用。不会自动调用默认模型或云端。</StatusMessage>}
      </section>}
      {action.feedback}
    </Panel>
    {reviewing && <RevisionReview key={`${reviewing.id}:${reviewing.version}`} proposal={reviewing} api={api} saved={saved} canWrite={!!onChapterSaved} onClose={() => setReviewing(undefined)} onResult={(value, updated) => { setReviewing(updated); history.reload(); if (value) saveResult(value); }} />}
    <Panel title="修订草稿记录">
      <Button disabled={history.loading} onClick={history.reload}>刷新修订记录</Button>
      <ResourceState loading={history.loading} error={history.error} empty={!history.data?.items.length} />
      {!history.loading && !history.error && history.data?.items.map(row => <article className="experimental-record" key={row.id}><div className="experimental-actions"><strong>{row.goal || '未命名修订'}</strong><Badge>{row.status} · v{row.version}</Badge><span>章节来源 v{row.source.version}</span></div>
        {row.stale && <StatusMessage tone="warning">来源已改变。原候选仍保留，不能强行套用旧下标。请重新选择当前文字并审核。</StatusMessage>}
        {['ACCEPTING', 'ACCEPTANCE_UNCERTAIN'].includes(row.status) && <StatusMessage tone="warning">采用结果未确认，正文可能已保存。请检查原版本历史，勿重复采用。</StatusMessage>}
        {row.status === 'PARTIAL' && row.accepted_chapter_version && <Button disabled={!saved || !chapter || row.accepted_chapter_version !== chapter.version || action.busy} onClick={() => void action.run(async () => { const result = await api.rebase(row, chapter!.version); if (alive.current) { setReviewing(result); history.reload(); } }, '未修改的剩余区块已创建新审核草稿，仍需再次预览与批准。')}>重新审核剩余未改区块</Button>}
        <Button disabled={row.stale || !row.blocks || !['REVIEW', 'PARTIAL'].includes(row.status)} onClick={() => setReviewing(row)}>审核此修订</Button>
      </article>)}
    </Panel>
    <Panel title="作品里程碑与修订目标"><p>仅标记原章节版本，不复制正文。恢复请使用原历史，会产生新的当前版本。</p>
      <Field label="里程碑名称"><input value={milestoneTitle} maxLength={160} onChange={e => setMilestoneTitle(e.target.value)} /></Field>
      <Button disabled={!chapter || !saved || !milestoneTitle.trim() || action.busy} onClick={() => void action.run(async () => { await api.milestone(chapter!, milestoneTitle, goal); if (alive.current) { setMilestoneTitle(''); milestones.reload(); } }, '里程碑已绑定原章节版本。')}>记录当前版本里程碑</Button>
      <ResourceState loading={milestones.loading} error={milestones.error} />
      <Button disabled={milestones.loading} onClick={milestones.reload}>刷新里程碑</Button>
      {!milestones.loading && !milestones.error && milestones.data?.items.map(row => <article className="experimental-record" key={row.id}><strong>{row.title}</strong><p>{row.chapter_id} · 原版本 v{row.chapter_version}</p><p>{row.goal}</p></article>)}
    </Panel>
  </div>;
}

type RevisionApi = ReturnType<typeof revisionIntelligenceClient>;
function RevisionReview({ proposal, api, saved, canWrite, onClose, onResult }: { proposal: RevisionProposal; api: RevisionApi; saved: boolean; canWrite: boolean; onClose: () => void; onResult: (chapter: Chapter | null, proposal: RevisionProposal) => void }) {
  const [decisions, setDecisions] = useState<Record<string, string>>({}), [preview, setPreview] = useState<RevisionPreview>(), [approved, setApproved] = useState(false);
  const action = useAction(); const epoch = useRef(0), alive = useRef(true);
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { if (!saved) { epoch.current++; setPreview(undefined); setApproved(false); } }, [saved]);
  const input = () => ({ expected_version: proposal.version, accept_ids: Object.keys(decisions).filter(k => decisions[k] === 'accept'), reject_ids: Object.keys(decisions).filter(k => decisions[k] === 'reject') });
  const invalidate = () => { epoch.current++; setPreview(undefined); setApproved(false); };
  return <Panel title="逐区块审核差异">
    <p>文本差异可以计算；人物动机、关系、世界事实和伏笔解释只是带引用的意见，不承诺涵盖所有影响。</p>
    {proposal.blocks?.map((block, index) => <article className="experimental-record" key={block.anchor_id}>
      <div className="experimental-actions"><strong>差异区块 {index + 1}</strong><Badge>{block.status}</Badge></div>
      <div className="experimental-grid"><section><h4>原文</h4><p className="writing-reference-text">{block.before || '空'}</p></section><section><h4>候选</h4><p className="writing-reference-text">{block.after || '删除所选文字，保留段落'}</p></section></div>
      <details><summary>查看可计算字符差异</summary>{block.diff.map((part, i) => <p className="writing-reference-text" key={i}>{part.kind === 'equal' ? part.before : <><del>{part.before}</del> <ins>{part.after}</ins></>}</p>)}</details>
      {proposal.explanations?.filter(item => item.anchor_id === block.anchor_id).map((item, i) => <section key={i}><Badge>{item.source === 'AUTHOR_NOTE' ? '作者注记' : '导入模型意见，质量未验证'}</Badge><p>{item.explanation}</p><p>原文依据：{item.before_quote}</p><p>候选依据：{item.after_quote}</p></section>)}
      <Field label={`区块 ${index + 1} 决定`}><select disabled={block.status !== 'PENDING' || action.busy} value={decisions[block.anchor_id] || ''} onChange={e => { invalidate(); setDecisions(old => ({ ...old, [block.anchor_id]: e.target.value })); }}><option value="">保留为待审草稿</option><option value="accept">接受此区块</option><option value="reject">拒绝此区块</option></select></Field>
    </article>)}
    <div className="experimental-actions"><Button disabled={action.busy || !saved || !Object.values(decisions).some(Boolean)} onClick={() => void action.run(async () => { const ticket = ++epoch.current; const value = await api.preview(proposal.id, input()); if (alive.current && ticket === epoch.current) { setPreview(value); setApproved(false); } }, '预检完成，尚未改文。')}>预览所选区块与检查点</Button><Button disabled={action.busy} onClick={onClose}>关闭审核，保留草稿</Button></div>
    {preview && <section aria-label="采用预览"><StatusMessage>批准 {preview.accept_ids.length} 处，拒绝 {preview.reject_ids.length} 处，保留 {preview.pending_blocks} 处待审。{preview.creates_new_current_revision ? `原章节 v${preview.checkpoint_version} 将保留在历史，新建当前版本。` : '仅更新审核决定，不改正文。'}</StatusMessage>
      <label className="experimental-check"><input type="checkbox" checked={approved} onChange={e => setApproved(e.target.checked)} />已核对所选区块与原版本检查点</label>
      <Button disabled={!approved || !saved || action.busy || (preview.accept_ids.length > 0 && !canWrite)} onClick={() => void action.run(async () => { const ticket = epoch.current; try { const result = await api.apply(proposal.id, { ...input(), preview_digest: preview.preview_digest }); if (alive.current && ticket === epoch.current) onResult(result.chapter, result.proposal); } catch (error) { if (alive.current) invalidate(); throw error; } }, '审核决定已保存。')}>确认仅应用所选决定</Button>
    </section>}
    {action.feedback}
  </Panel>;
}

function SelectionGeneration({ options, selection, goal, saved, onCandidate }: { options: RevisionGenerationOptions; selection: SelectionReceipt; goal: string; saved: boolean; onCandidate: (texts: string[], jobId: string) => void }) {
  const [requestScope, setRequestScope] = useState<AuthorRequestScope>({ ...defaultAuthorRequestScope, source_mode: 'SELECTION_ONLY', include_automatic_context: false });
  const [operation, setOperation] = useState('polish'), [style, setStyle] = useState(''), [receipt, setReceipt] = useState<AuthorPreviewReceipt>(), [authorized, setAuthorized] = useState(false);
  const [job, setJob] = useState<{ id: string; status: string; output: string; error?: string; execution_mode?: string }>();
  const alive = useRef(true), epoch = useRef(0); const action = useAction();
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  const instructions: Record<string, string> = { polish: '润色选中文字，保留事实与语义。', compress: '压缩选中文字，保留关键事实。', expand: '扩写选中文字，保留已有事实。', dialogue: '将选中文字改成自然对白，保留角色与事实。' };
  const body: AuthorRequestBody | null = options.providerId && options.modelId ? { novel_id: options.novelId, chapter_id: selection.selection.chapter_id, chapter_version: selection.selection.chapter_version, operation: 'rewrite', request_scope: requestScope, instruction: `${instructions[operation]}每个输入段落只输出一个对应段落，不加标题、解释或额外整章内容。保留要求：${goal}`, style, profile: options.profile, provider_id: options.providerId, model_id: options.modelId, source: selection.selection.text, selected_text: selection.selection.text, revision_selection: selection.selection, revision_selection_digest: selection.selection_digest } : null;
  const requestKey = JSON.stringify(body);
  useEffect(() => { epoch.current++; setJob(undefined); setReceipt(undefined); setAuthorized(false); }, [requestKey, saved]);
  const outputLines = job?.status === 'COMPLETED' ? job.output.split('\n') : [];
  const representable = outputLines.length === selection.blocks.length && selection.blocks.every(b => !b.before.includes('\n'));
  return <section className="experimental-section" aria-label="选区 AI 助手"><h3>选区 AI 助手</h3>
    <Field label="选区操作"><select value={operation} disabled={action.busy} onChange={e => setOperation(e.target.value)}><option value="polish">润色</option><option value="compress">压缩</option><option value="expand">扩写</option><option value="dialogue">改对白</option></select></Field>
    <Field label="本次选区风格"><input value={style} maxLength={120} onChange={e => setStyle(e.target.value)} /></Field>
    <AuthorRequestControls value={requestScope} onChange={setRequestScope} source={selection.selection.text} operation="rewrite" disabled={action.busy} />
    <AuthorRequestPreviewPanel body={body} context={options.context} saved={saved} disabled={action.busy} onReceipt={value => { setReceipt(value); setAuthorized(false); }} />
    <label className="experimental-check"><input type="checkbox" disabled={!receipt || action.busy} checked={authorized} onChange={e => setAuthorized(e.target.checked)} />已核对实际请求，授权所选明确模型处理这一次选区</label>
    <Button disabled={!body || !receipt || !authorized || !saved || action.busy} onClick={() => void action.run(async () => { const ticket = ++epoch.current; const result = await authorContextRequest<{ job_id: string; status: string }>(options.novelId, 'generate', { ...receipt!.requestBody, preview_digest: receipt!.previewDigest, generation_request_id: receipt!.requestId }, options.context); if (alive.current && ticket === epoch.current) setJob({ id: result.job_id, status: result.status, output: '' }); }, '生成请求已提交，请刷新任务状态。结果仍需逐区块审核。')}>生成一次选区草稿</Button>
    {job && <section aria-label="选区生成结果"><Badge>{job.status}</Badge><Button disabled={action.busy} onClick={() => void action.run(async () => { const ticket = epoch.current; const result = await originalApi.job(job.id, options.context); if (alive.current && ticket === epoch.current) setJob(result); }, '已读取原生成任务当前状态。')}>刷新选区生成任务</Button>
      {job.error && <StatusMessage tone="error">{job.error}</StatusMessage>}
      {job.status === 'COMPLETED' && <><Field label="生成原始结果，尚未采用"><textarea readOnly value={job.output} /></Field><p>执行标记：{job.execution_mode || '未知'}。合成结果不代表真实模型质量。</p>
        {!representable && <StatusMessage tone="warning">输出段落数或范围无法对应选区，不能自动套用。请人工挑选片段填写候选，再重新审核。</StatusMessage>}
        <Button disabled={!representable || action.busy || !saved} onClick={() => onCandidate(outputLines, job.id)}>将对应段落导入候选，仍需审核</Button></>}
    </section>}
    {action.feedback}
  </section>;
}
