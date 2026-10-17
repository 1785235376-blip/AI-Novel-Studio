import { DirectorTargetPanel } from './DirectorTargetPanel';
import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Badge, Button, EmptyState, Panel, StatusMessage } from '../ui/primitives';
import { DirectorModelControls } from './DirectorModelControls';
import { DirectorFields, CreativeField } from './CreativeCanvas';
import type { DirectorProposalClient, DirectorProposal } from './client';
import { validDirectorGenre, type CreativeDocument, type DirectorSceneNote, type VisualTarget } from './types';
import type { AssetSelection } from './AssetBrowser';
type Props = { client: DirectorProposalClient; documents: CreativeDocument[]; canMutate: boolean; onDocument: (document: CreativeDocument) => void; onDenied: () => void; asset?: AssetSelection; onOpenModels?: () => void; environment?: React.ReactNode; onBusyChange?: (busy: boolean) => void; onPendingChange?: (pending: boolean) => void };

/** A changed original-owner client retires all private drafts and late callbacks. */
export function AIDirectorPanel(props: Props) {
  const origin = useRef({ client: props.client, generation: 0 });
  if (origin.current.client !== props.client) origin.current = { client: props.client, generation: origin.current.generation + 1 };
  return <DirectorProposalPanel key={origin.current.generation} {...props} />;
}

function DirectorProposalPanel({ client, documents, canMutate, onDocument, onDenied, asset, onOpenModels, environment, onBusyChange, onPendingChange }: Props) {
  const [proposals, setProposals] = useState<DirectorProposal[]>([]), [proposal, setProposal] = useState<DirectorProposal>(), [sourceId, setSourceId] = useState(''), [title, setTitle] = useState(''), [notes, setNotes] = useState<DirectorSceneNote[]>([]), [reviewed, setReviewed] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [uncertain, setUncertain] = useState(false);
  const [preparedGoal, setPreparedGoal] = useState<VisualTarget>(), [goal, setGoal] = useState<VisualTarget>();
  const [reviewDirty, setReviewDirty] = useState(false), [preparedDirty, setPreparedDirty] = useState(false);
  const [discardConfirmed, setDiscardConfirmed] = useState(false), [recoveryRows, setRecoveryRows] = useState<DirectorProposal[]>();
  const [unresolvedResult, setUnresolvedResult] = useState(false);
  const [recoveryTargetId, setRecoveryTargetId] = useState<string | null>(null);
  const [opened, setOpened] = useState<Pick<CreativeDocument, 'id' | 'version' | 'status'>>();
  const live = useRef(true), lock = useRef(false), epoch = useRef(0);
  const selection = useRef(0), reopening = useRef<AbortController>();
  // Retained DOM callbacks cannot borrow a later render's source, authority or draft.
  const admission = useRef(0), admittedRender = ++admission.current;
  const admitsAction = () => live.current && admission.current === admittedRender;
  const edit = (change: () => void) => { if (!admitsAction() || lock.current) return; admission.current++; change(); };
  useEffect(() => { live.current = true; return () => { live.current = false; epoch.current++; }; }, []);
  useEffect(() => () => reopening.current?.abort(), []);
  useEffect(() => { onBusyChange?.(busy); return () => onBusyChange?.(false); }, [busy, onBusyChange]);
  const localReviewPending = reviewed || reviewDirty;
  const pending = busy || uncertain || localReviewPending || preparedDirty;
  useEffect(() => { onPendingChange?.(pending); }, [pending, onPendingChange]);
  useEffect(() => () => onPendingChange?.(false), [onPendingChange]);
  const read = async (signal?: AbortSignal): Promise<DirectorProposal[] | undefined> => { const ticket = ++epoch.current; try { const result = await client.proposals(signal); if (!signal?.aborted && live.current && ticket === epoch.current) { setProposals(result.items); setError(''); return result.items; } return undefined; } catch (value) { if (!signal?.aborted && live.current && ticket === epoch.current) { setError(value instanceof ApiError ? `${value.message} (${value.problem.code})` : '导演建议暂时不可读。'); if (value instanceof ApiError && (value.status === 401 || value.status === 403)) onDenied(); } return undefined; } };
  useEffect(() => { const controller = new AbortController(); void read(controller.signal); return () => controller.abort(); }, [client]);
  const sources = documents.filter(row => row.mode === 'SCREENPLAY' && row.scenes.length || row.mode === 'STORYBOARD' && row.shots.length);
  const source = sources.find(row => row.id === sourceId) || sources[0];
  const proposalSource = documents.find(row => row.id === proposal?.source_document_id);
  const sourceMode = proposal?.provenance?.source_mode;
  const storyboardProposal = sourceMode === 'STORYBOARD' || proposalSource?.mode === 'STORYBOARD';
  const sourceMismatch = !!proposal && (
    (sourceMode !== undefined && sourceMode !== 'STORYBOARD' && sourceMode !== 'SCREENPLAY')
    || (sourceMode !== undefined && !!proposalSource && sourceMode !== proposalSource.mode)
    || (proposalSource?.mode === 'STORYBOARD' && sourceMode !== 'STORYBOARD')
    || (sourceMode !== 'STORYBOARD' && proposal.provenance?.source_shots !== undefined)
  );
  const modelSourceAllowed = !storyboardProposal && !sourceMismatch
    && (!proposalSource || proposalSource.mode === 'SCREENPLAY');
  const select = (row: DirectorProposal) => { admission.current++; selection.current++; reopening.current?.abort(); setOpened(undefined); setProposal(row); setGoal(row.visual_target ? structuredClone(row.visual_target) : undefined); setNotes(structuredClone(row.director_notes)); setTitle(row.title); setReviewed(false); setReviewDirty(false); setDiscardConfirmed(false); setNotice(''); };
  async function reconcile() {
    if (!live.current || lock.current || !uncertain) return;
    lock.current = true; setBusy(true); setRecoveryRows(undefined); setDiscardConfirmed(false);
    try {
      const rows = await read();
      // Reading status never discards local review text, even on a failed read.
      if (live.current && rows) setRecoveryRows(rows);
    } finally { lock.current = false; if (live.current) setBusy(false); }
  }
  function adoptRecoveredStatus() {
    if (!admitsAction() || lock.current || !uncertain || !recoveryRows || !discardConfirmed) return;
    const row = recoveryRows.find(item => item.id === recoveryTargetId);
    if (row) select(row);
    else {
      selection.current++; setProposal(undefined); setTitle(''); setNotes([]); setGoal(undefined); setOpened(undefined);
      setReviewed(false); setReviewDirty(false); setDiscardConfirmed(false); setUnresolvedResult(true);
    }
    // The separate preparation target is not part of this review-discard consent.
    setRecoveryRows(undefined); setUncertain(false);
    setNotice(row ? '已按明确确认采用原建议的当前状态；没有重新提交写入。' : '已明确放弃本地审核内容；先前请求的远端结果仍需核对。');
  }
  const validId = (value: unknown): value is string => typeof value === 'string' && !!value.trim() && value.length <= 240;
  const linked = (row: DirectorProposal) => row.status === 'APPROVED' && validId(row.id) && validId(row.document_id) && validId(row.source_document_id)
    && Number.isSafeInteger(row.version) && row.version > 0
    && typeof row.source_digest === 'string' && /^[a-f0-9]{64}$/.test(row.source_digest)
    && Number.isSafeInteger(row.source_version) && row.source_version > 0;
  async function reopen() {
    if (!proposal || !linked(proposal) || lock.current || uncertain) return;
    const selected = proposal, ticket = selection.current, controller = new AbortController();
    const current = () => live.current && !controller.signal.aborted && selection.current === ticket;
    reopening.current = controller; lock.current = true; setBusy(true); setError(''); setNotice(''); setOpened(undefined);
    try {
      // Re-read the exact proposal first: its owner checks the source even after
      // approval. Listing an old row or knowing a document ID is not evidence.
      const receipt = await client.proposal(selected.id, controller.signal);
      if (!current()) return;
      if (!linked(receipt) || receipt.id !== selected.id || receipt.version !== selected.version
        || receipt.document_id !== selected.document_id || receipt.source_document_id !== selected.source_document_id
        || receipt.source_version !== selected.source_version || receipt.source_digest !== selected.source_digest) {
        throw new Error('建议与采用回执不一致，请重新读取建议状态。');
      }
      const document = await client.get(receipt.document_id!, controller.signal);
      if (!current()) return;
      const source = document.source_documents?.[receipt.source_document_id];
      if (document.id !== receipt.document_id || document.mode !== 'DIRECTOR' || document.status !== 'DRAFT'
        || !Number.isSafeInteger(document.version) || document.version < 1
        || source?.version !== receipt.source_version || source?.digest !== receipt.source_digest) {
        throw new Error('原导演草稿与建议来源不一致，未打开此结果。');
      }
      setOpened({ id: document.id, version: document.version, status: document.status });
      setNotice('已核对采用后的原导演草稿。建议已采用，文档仍是 DRAFT；不代表制作审核通过。');
      onDocument(document);
    } catch (value) {
      if (!current()) return;
      setError(value instanceof ApiError ? `${value.message} (${value.problem.code})` : value instanceof Error ? value.message : '原导演草稿暂时不可读。');
      if (value instanceof ApiError && [401, 403].includes(value.status)) onDenied();
    } finally {
      if (reopening.current === controller) { reopening.current = undefined; lock.current = false; if (live.current) setBusy(false); }
    }
  }
  const run = async (action: () => Promise<void>, targetId: string | null = proposal?.id ?? null) => { if (!admitsAction() || lock.current || !canMutate || uncertain) return; lock.current = true; setBusy(true); setError(''); setNotice(''); try { await action(); } catch (value) { if (live.current) { setError(value instanceof ApiError ? `${value.message} (${value.problem.code})` : '操作回执不确定。请重新读取建议，勿重复创建或采用。'); setReviewed(false); if (!(value instanceof ApiError) || value.status >= 500 || value.status === 409) { setRecoveryTargetId(targetId); setUncertain(true); } if (value instanceof ApiError && (value.status === 401 || value.status === 403)) onDenied(); } } finally { lock.current = false; if (live.current) setBusy(false); } };
  // A fast receipt can release the lock before the second native double-click.
  // Keep one proposal per gesture; keyboard (0) and later single clicks (1) still work.
  const prepareProposal = (clickCount: number) => { if (!admitsAction() || clickCount > 1 || localReviewPending || !source || !validDirectorGenre(preparedGoal)) return; void run(async () => { const result = await client.propose(source, preparedGoal); if (live.current) { select(result); setPreparedDirty(false); setProposals(rows => [result, ...rows]); setNotice('建议已生成，等待逐项核对。未调用模型。'); } }, null); };
  return <div className="creative-director-panel" aria-label="AI 导演面板"><header><span className="creative-eyebrow">AI Director</span><h2>导演协作与审核</h2></header>{asset && <Panel title="选中资产"><strong>{asset.title}</strong><p>{asset.kind} · {asset.detail}</p><small>{asset.id}</small></Panel>}
    <Panel title="从已保存剧本或分镜准备导演建议"><p>本地规则辅助会整理场景调度草案。不会调用模型；采用后新增独立导演文档。</p><p>本地规则辅助（RULE_ASSISTED）整理待审草案。分镜按已写镜头序号逐镜头复制相机与时长，并提供待核对的调度提示；这不是模型分析。采用后新增独立导演 DRAFT，原分镜、资产和画布绑定不变。</p><CreativeField label="导演建议来源剧本或分镜"><select value={source?.id || ''} disabled={busy || uncertain || localReviewPending} onChange={e => { if (!uncertain && !localReviewPending) edit(() => setSourceId(e.target.value)); }}><option value="">选择已保存剧本或分镜</option>{sources.map(row => <option key={row.id} value={row.id}>{row.title} · {row.mode === 'STORYBOARD' ? '分镜' : '剧本'} · v{row.version}</option>)}</select></CreativeField><details><summary>本次导演建议的视觉目标（可选）</summary><fieldset disabled={!canMutate || busy || uncertain}><DirectorTargetPanel prefix="建议准备 " value={preparedGoal} onChange={value => edit(() => { setPreparedGoal(value); setPreparedDirty(true); })} /></fieldset></details><Button disabled={!canMutate || busy || uncertain || localReviewPending || !source || !validDirectorGenre(preparedGoal)} onClick={event => prepareProposal(event.detail)}>{busy ? '处理中…' : '准备待审导演建议'}</Button>{preparedDirty && <Button disabled={busy || uncertain} onClick={() => edit(() => { setPreparedGoal(undefined); setPreparedDirty(false); })}>清空未提交的视觉目标</Button>}{!sources.length && <p>先保存一份含场景的剧本或含镜头的分镜，再准备导演建议。</p>}</Panel>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}{notice && <StatusMessage tone="success">{notice}</StatusMessage>}{unresolvedResult && <StatusMessage tone="warning">先前请求的远端结果仍未知。读取列表不能证明请求未执行；再次建立前请核对原建议和文档，勿重复提交。</StatusMessage>}
    {uncertain && <StatusMessage tone="warning">操作结果需核对。当前审核内容已保留。<Button disabled={busy} onClick={() => void reconcile()}>重新读取建议状态</Button>
      {recoveryRows && <section aria-label="核对后的建议状态">
        <p>已读取服务端建议状态；本地审核修改仍保留，须明确确认后才能替换。</p>
        {recoveryTargetId === null ? <p>先前建立请求没有可核对的建议标识；当前选中建议不能作为该请求回执。放弃本地内容不会证明远端结果。</p>
          : recoveryRows.find(row => row.id === recoveryTargetId)
            ? <p>原建议当前状态：{recoveryRows.find(row => row.id === recoveryTargetId)!.status}</p>
            : <p>当前列表未匹配到原建议，不能确认先前请求是否执行。放弃本地内容不会证明远端结果。</p>}
        <label><input type="checkbox" disabled={busy} checked={discardConfirmed} onChange={event => edit(() => setDiscardConfirmed(event.target.checked))} />确认放弃本地审核修改并采用已读取建议状态</label>
        <Button disabled={busy || !discardConfirmed} onClick={adoptRecoveredStatus}>处理已核对的建议状态</Button>
      </section>}
    </StatusMessage>}
    {localReviewPending && !uncertain && <StatusMessage tone="info">当前审核有未保存修改或确认。采用或明确放弃后，才能切换建议、准备新建议或读取替换内容。</StatusMessage>}
    <Panel title="建议审核队列" actions={<Button disabled={busy || uncertain} onClick={() => void read()}>刷新</Button>}><div className="creative-proposal-list">{proposals.map(row => <Button key={row.id} disabled={busy || uncertain || localReviewPending} aria-pressed={proposal?.id === row.id} onClick={() => { if (admitsAction() && !lock.current && !uncertain && !localReviewPending) select(row); }}>{row.title}<Badge>{row.status}</Badge></Button>)}</div>{!proposals.length && !error && <EmptyState title="没有待审导演建议" detail="手动编辑始终可用。只有明确核对并采用建议才会创建导演文档。" />}
      {proposal && <section aria-label="导演建议审核"><p>来源 {proposal.source_document_id} · v{proposal.source_version} · {proposal.source_digest || '摘要未返回'} · 建议 v{proposal.version}</p>{proposal.status === 'APPROVED' && <section aria-label="已采用建议的原导演草稿"><p>建议 APPROVED：已采用为独立导演草稿。文档保存与制作审核状态仍由原文档确认。</p>{!linked(proposal) && <StatusMessage tone="warning">采用回执缺少原文档或来源摘要，请重新读取建议状态。</StatusMessage>}<Button disabled={busy || uncertain || !linked(proposal)} onClick={() => void reopen()}>核对并打开已采用的导演草稿</Button>{opened && <p>原文档 {opened.id} · v{opened.version} · {opened.status}</p>}</section>}<Badge tone="info">{proposal.provenance?.model_called ? '模型产出 · 需审核' : '本地规则辅助 · 未调用模型'}</Badge>{!modelSourceAllowed ? <StatusMessage tone="info">{sourceMismatch ? '来源类型记录不一致或缺失，模型操作已禁用；请重新读取原来源与建议。' : 'STORYBOARD 当前仅支持 RULE_ASSISTED。模型分析尚未支持；未调用模型。'}</StatusMessage> : <DirectorModelControls key={proposal.id} client={client} proposal={proposal} disabled={busy || !canMutate || uncertain || localReviewPending} run={run} onUpdate={row => { if (!live.current) return; select(row); setProposals(rows => rows.map(item => item.id === row.id ? row : item)); }} />}
        <p>{notes.length} 个候选镜头 · 预计总时长 {notes.every(note => Number.isInteger(note.duration_seconds) && note.duration_seconds >= 1 && note.duration_seconds <= 600) ? `${notes.reduce((sum, note) => sum + note.duration_seconds, 0)} 秒` : '待修正'}。仅为当前候选顺序的时长相加，不含备选方案，不代表成片时长。</p>
        {proposal.provenance?.source_mode === 'STORYBOARD' && <section aria-label="分镜来源与规则建议说明"><p>下列是未编辑的已保存来源快照。相机与时长直接复制，并非推断；当前候选编辑值请在下方核对。节奏与调度提示是假设，需人工确认。</p>{proposal.provenance.source_shots?.map(item => <details key={item.note_id}><summary>原分镜 #{item.source_number} · {item.source_shot_id} → {item.note_id}</summary><p>场景：{item.scene_id} · 景别：{item.source_shot.shot_size} · 机位：{item.source_shot.camera_angle} · 运镜：{item.source_shot.camera_motion} · 时长：{item.source_shot.duration_seconds} 秒</p><p>复制字段：{item.copied_fields.join('、')}</p><p>规则假设字段（需审核）：{item.suggested_fields.join('、')}</p><p>仅保留在来源记录、未映射为导演执行字段：{item.retained_source_only_fields.join('、') || '无'}</p><pre>{JSON.stringify(item.source_shot, null, 2)}</pre></details>)}</section>}
        <details><summary>规则辅助检查（原始候选）</summary><p>规则只检查已填写的镜头词汇。编辑后的取值需重新人工核对；轴线、视线和实际空间关系未知，不能据此判定连续性正确。</p>{proposal.rule_checks?.map(check => <p key={check.note_id}>{check.note_id}：{Object.entries(check.camera.classification).map(([field, code]) => `${field}: ${code}`).join(' · ')}</p>)}</details>
        {localReviewPending && !uncertain && <section aria-label="放弃本地审核修改"><label><input type="checkbox" disabled={busy} checked={discardConfirmed} onChange={event => edit(() => setDiscardConfirmed(event.target.checked))} />确认放弃本地审核修改并恢复原建议</label><Button disabled={busy || !discardConfirmed} onClick={() => { if (admitsAction() && discardConfirmed && !lock.current && !uncertain) select(proposal); }}>放弃本地审核修改，恢复原建议</Button></section>}<fieldset disabled={busy || !canMutate || proposal.status !== 'NEEDS_REVIEW' || uncertain}><legend className="creative-sr-only">建议内容</legend><details><summary>审核视觉目标</summary><DirectorTargetPanel prefix="建议审核 " value={goal} onChange={value => edit(() => { setGoal(value); setReviewed(false); setReviewDirty(true); setDiscardConfirmed(false); })} /></details><CreativeField label="采用后的导演文档标题"><input maxLength={240} value={title} onChange={e => edit(() => { setTitle(e.target.value); setReviewed(false); setReviewDirty(true); setDiscardConfirmed(false); })} /></CreativeField>{notes.map((note, index) => <details key={note.id}><summary>{proposal.provenance?.source_mode === 'STORYBOARD' ? `分镜调度 #${note.number}` : `场景调度 ${index + 1}`}</summary><DirectorFields value={note} prefix={`建议 ${index + 1} `} onChange={next => edit(() => { setNotes(rows => rows.map(row => row.id === next.id ? next : row)); setReviewed(false); setReviewDirty(true); setDiscardConfirmed(false); })} /></details>)}<label className="creative-review-check"><input type="checkbox" checked={reviewed} onChange={e => edit(() => { setReviewed(e.target.checked); setDiscardConfirmed(false); })} />已核对来源、场面调度与导演建议；创建独立导演文档</label><div className="creative-actions"><Button variant="primary" disabled={!reviewed || !title.trim() || !validDirectorGenre(goal)} onClick={() => { if (!validDirectorGenre(goal)) return; void run(async () => { const result = await client.review(proposal, title, notes, goal ?? (proposal.visual_target ? null : undefined)); if (live.current) { setProposal(result.proposal); setReviewed(false); setReviewDirty(false); setOpened({ id: result.document.id, version: result.document.version, status: result.document.status }); setProposals(rows => rows.map(row => row.id === result.proposal.id ? result.proposal : row)); setNotice('已创建导演文档。小说正文保持原有保存与审核流程。'); onDocument(result.document); } }); }}>审核并采用</Button><Button onClick={() => void run(async () => { const result = await client.cancelProposal(proposal); if (live.current) { setProposal(result); setReviewed(false); setReviewDirty(false); setProposals(rows => rows.map(row => row.id === result.id ? result : row)); setNotice('建议已取消。'); } })}>取消建议</Button></div></fieldset></section>}
    </Panel>{environment}<Panel title="模型与执行能力"><p>模型调用需要已配置且可用的 Provider。此工作区不会自动启动模型或渲染音视频。</p>{onOpenModels && <Button onClick={onOpenModels}>打开模型控制中心</Button>}</Panel>
  </div>;
}
