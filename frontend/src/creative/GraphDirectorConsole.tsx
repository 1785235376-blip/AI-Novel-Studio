import { useDirectorAuthorRecovery } from './useDirectorAuthorRecovery';
import { DirectorAuthorRecoveryPanel } from './DirectorAuthorRecoveryPanel';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import { DirectorImageReviewPanel } from './DirectorImageReviewPanel';
import { DirectorSceneScopePanel } from './DirectorSceneScopePanel';
import {DirectorSheetExportPanel} from './DirectorSheetExportPanel';
import {directorDraftBackup} from './directorDraftBackup';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
import { reviewedDirectorSnapshot, type ReviewedDirectorReceipt, type ReviewedDirectorCanvasHandoff } from './directorCanvasHandoff';
import type { OpenStoryboardEditor } from './storyboardEditorHandoff';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { GraphDirectorProposalReview, hasDirectorProposalReview, type GraphDirectorReviewSource } from './GraphDirectorProposalReview';
import { ApiError, apiErrorView } from '../api';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { GraphDirectorSourceImpact } from './GraphDirectorSourceImpact';
import type { StudioGraphDefinition } from './studioGraphTypes';
import { GraphDirectorStoryboardHandoff } from './GraphDirectorStoryboardHandoff';
import { CreativeCanvas } from './CreativeCanvas';
import { DirectorDraftComparison } from './DirectorDraftComparison';
import type { creativeClient } from './client';
import { creativeAuthoringProblems, documentInput, newDocument, type CreativeDocument, type CreativeInput } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import './creative.css';

export type GraphDirectorSource = Pick<ReturnType<typeof creativeClient>, 'create' | 'update' | 'export' | 'capabilities' | 'list' | 'derive' | 'history'> & GraphDirectorReviewSource & Partial<Pick<ReturnType<typeof creativeClient>, 'directorSheetExport' | 'deriveDirectorScope' | 'imageDirector'>>;
type Props = {
  client: GraphDirectorSource;
  draftOwner?: StudioGraphDraftOwner;
  verifyDraftOwner?: () => Promise<void>;
  registerRecoveryDiscard?: (discard: (() => void) | undefined) => void;
  canvasHandoff?: ReviewedDirectorCanvasHandoff;
  pin?: PlanningSnapshot;
  selectionKey?: string;
  graph?: StudioGraphDefinition;
  selectedNodeId?: string;
  active: boolean;
  canMutate: boolean;
  busy: boolean;
  isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>;
  mutate: <T>(work: () => Promise<T>) => Promise<T>;
  onDirtyChange: (dirty: boolean) => void;
  onImagePendingChange?: (pending: boolean) => void;
  onOpenModels?: () => void;
  onOpenBroker?: () => void;
  onOpenStoryboard?: OpenStoryboardEditor;
};
const empty = (): CreativeInput => ({ ...newDocument('DIRECTOR'), source_independent: true });
const samePin = (a: PlanningSnapshot, b: PlanningSnapshot) => a.id === b.id && a.version === b.version && a.digest === b.digest;

/** A mounted view of the original Creative owner. Only author drafts live here;
 * Graph retains its exact pin and all execution/review remains with its owners. */
export function GraphDirectorConsole({ draftOwner, verifyDraftOwner, registerRecoveryDiscard, client, canvasHandoff, pin, selectionKey, graph, selectedNodeId, active, canMutate, busy, isCurrent, read, mutate, onDirtyChange, onImagePendingChange, onOpenModels, onOpenBroker, onOpenStoryboard }: Props) {
  const imageClient = useMemo(() => client.imageDirector?.(), [client]);
  const [imagePending, setImagePending] = useState(false);
  const imagePendingCallback = useRef(onImagePendingChange); imagePendingCallback.current = onImagePendingChange;
  const imageChanged = useCallback((value: boolean) => { imagePendingCallback.current?.(value); setImagePending(value); }, []);
  const [reviewed, setReviewed] = useState<ReviewedDirectorReceipt>();
  const [reviewedPin, setReviewedPin] = useState<PlanningSnapshot>();
  const verifiedIntent = useRef<{ pin: PlanningSnapshot; canvasScope: object | undefined; authored: number; selected: number; generation: number; canvasGeneration: number; receipt: ReviewedDirectorReceipt; isCanvasCurrent?: () => boolean; consumed: boolean }>();
  const reviewedRef = useRef(reviewed); reviewedRef.current = reviewed;
  const canvasLifetime = useRef({ scope: canvasHandoff?.verificationScope, generation: 0 });
  if (canvasLifetime.current.scope !== canvasHandoff?.verificationScope) {
    canvasLifetime.current = { scope: canvasHandoff?.verificationScope, generation: canvasLifetime.current.generation + 1 };
  }
  const composing = useRef(false);
  const canvasRef = useRef(canvasHandoff); canvasRef.current = canvasHandoff;
  const [proposalPending, setProposalPending] = useState(false);
  const [scopePending, setScopePending] = useState(false);
  const [handoffPending, setHandoffPending] = useState(false), [storyboardAllowed, setStoryboardAllowed] = useState(false);
  const [authorityDenied, setAuthorityDenied] = useState(false);
  const [open, setOpen] = useState(false), [authorized, setAuthorized] = useState(false);
  const [draft, setDraft] = useState<CreativeInput>(empty), [base, setBase] = useState<CreativeDocument>();
  const [dirty, setDirty] = useState(false), [blocked, setBlocked] = useState(false), [working, setWorking] = useState(false), [saving, setSaving] = useState(false);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [candidate, setCandidate] = useState<{ document: CreativeDocument; pin: PlanningSnapshot }>();
  const [snapshot, setSnapshot] = useState<PlanningSnapshot>(), [discardConfirmed, setDiscardConfirmed] = useState(false);
  const [documents, setDocuments] = useState<Pick<CreativeDocument, 'id' | 'title' | 'version'>[]>([]), [choice, setChoice] = useState('');
  const [scene, setScene] = useState<string>(), [shot, setShot] = useState<string>();
  const alive = useRef(true), lock = useRef(false), epoch = useRef(0);
  const selectedPinRef = useRef(pin); selectedPinRef.current = pin;
  const scope = useRef({ active, isCurrent, client, generation: 0 });
  if (scope.current.active !== active || scope.current.client !== client) scope.current.generation++;
  scope.current = { active, isCurrent, client, generation: scope.current.generation };
  const selection = useRef({ key: '', generation: 0 });
  const selectedKey = JSON.stringify([selectionKey, pin]);
  if (selection.current.key !== selectedKey) selection.current = { key: selectedKey, generation: selection.current.generation + 1 };
  const ownerClient = useRef(client);
  const current = () => alive.current && scope.current.active && scope.current.isCurrent() && ownerClient.current === scope.current.client;
  const owns = (generation: number) => current() && scope.current.generation === generation;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; }; }, []);
  useEffect(() => { if (!active) epoch.current++; }, [active]);
  const recovery = useDirectorAuthorRecovery({ owner: draftOwner, available: authorized && canMutate && active && !!verifyDraftOwner,
    isCurrent: current, draft, base, pin: snapshot, dirty, uncertain: blocked });
  useEffect(() => { registerRecoveryDiscard?.(recovery.clear); return () => registerRecoveryDiscard?.(undefined); }, [registerRecoveryDiscard, recovery.clear]);
  const pending = !!recovery.candidate || dirty || blocked || handoffPending || proposalPending || scopePending || imagePending;
  const pendingInputs = useRef({ recoveryPending: !!recovery.candidate, dirty, blocked, handoffPending, scopePending, imagePending, onDirtyChange });
  pendingInputs.current = { recoveryPending: !!recovery.candidate, dirty, blocked, handoffPending, scopePending, imagePending, onDirtyChange };
  const proposalChanged = useCallback((value: boolean) => {
    setProposalPending(value);
    const input = pendingInputs.current;
    input.onDirtyChange(value || input.recoveryPending || input.dirty || input.blocked || input.handoffPending || input.scopePending || input.imagePending);
  }, []);
  const reportedPending = useRef(false);
  useEffect(() => { if (reportedPending.current !== pending) { reportedPending.current = pending; onDirtyChange(pending); } }, [pending, onDirtyChange]);
  const editing = authorized && canMutate && active && !busy && !working && !blocked && !handoffPending && !proposalPending && !scopePending && !imagePending && !recovery.candidate && isCurrent();
  const authorEpoch = useRef(0);
  const renderedAuthorEpoch = authorEpoch.current;
  const mark = (value: boolean) => { authorEpoch.current++; setDirty(value); onDirtyChange(value || blocked || handoffPending || proposalPending || scopePending || imagePending); };
  const fail = (reason: unknown) => {
    setError(apiErrorView(reason, '导演文档操作未完成，请核对连接与原文档。').message);
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
      setAuthorityDenied(true);
      setReviewed(undefined); setReviewedPin(undefined); setAuthorized(false); setBase(undefined); setSnapshot(undefined); setCandidate(undefined); setDocuments([]); setChoice('');
    }
  };
  async function reveal() {
    if (!current() || lock.current || busy) return;
    const generation = scope.current.generation, ticket = ++epoch.current;
    lock.current = true; setWorking(true); setOpen(true); setError('');
    try {
      const caps = await read(() => client.capabilities());
      if (owns(generation) && ticket === epoch.current) { setAuthorized(caps.enabled && caps.can_mutate && caps.modes.includes('DIRECTOR')); setStoryboardAllowed(caps.enabled && caps.can_mutate && caps.modes.includes('STORYBOARD')); }
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  async function listDocuments() {
    if (!current() || lock.current || busy || imagePending) return;
    lock.current = true; setWorking(true); setError('');
    const ticket = ++epoch.current, generation = scope.current.generation;
    try {
      const value = await read(() => client.list());
      if (!owns(generation) || ticket !== epoch.current) return;
      setDocuments(value.items.filter(row => row.mode === 'DIRECTOR').map(({ id, title, version }) => ({ id, title, version })));
      setChoice('');
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function change(value: CreativeInput) {
    if (!editing || lock.current || value.mode !== 'DIRECTOR') return;
    setReviewedPin(undefined); setDraft(value); mark(true); setNotice(''); setCandidate(undefined); setDiscardConfirmed(false);
  }
  function fresh() {
    if (!editing || lock.current || pending) return;
    authorEpoch.current++; reviewedRef.current = undefined; setReviewed(undefined); setReviewedPin(undefined); setDraft(empty()); setBase(undefined); setSnapshot(undefined); setCandidate(undefined); setScene(undefined); setShot(undefined); setNotice('');
  }
  async function save() {
    if (!editing || lock.current || !dirty || !draft.title.trim() || creativeAuthoringProblems(draft).length) return;
    lock.current = true; setWorking(true); setSaving(true); setError('');
    const input = documentInput(draft), origin = base, generation = scope.current.generation, ticket = ++epoch.current;
    try {
      const protectedSave = draftOwner ? await recovery.prepareSave(draft, base, snapshot) : true;
      if (!owns(generation) || ticket !== epoch.current) return;
      if (!protectedSave) { setError('本机恢复保护未完成，未提交服务器保存。输入仍保留，请下载备份后核对恢复状态。'); return; }
      setBlocked(true); setNotice('保存请求已提交，结果核对完成前不会重复写入。');
      const row = await mutate(() => origin ? client.update(origin.id, origin.version, input) : client.create(input));
      if (!owns(generation) || ticket !== epoch.current) return;
      if (row.mode !== 'DIRECTOR' || typeof row.id !== 'string' || !row.id.trim() || !Number.isSafeInteger(row.version) || row.version < 1 || origin && (row.id !== origin.id || row.version !== origin.version + 1)) throw new Error('导演保存回执不匹配。');
      reviewedRef.current = undefined; setReviewed(undefined); setReviewedPin(undefined); setBase(row); setDraft(documentInput(row)); setSnapshot(undefined); setBlocked(false); mark(false);
      setNotice(`导演原文档已保存 · v${row.version}。请读取原文档核对摘要；图绑定保持原版本。保存不批准、不调用模型。`);
    } catch (reason) {
      if (!owns(generation) || ticket !== epoch.current) return;
      fail(reason);
      if (!(reason instanceof ApiError) || reason.status >= 500 || reason.status === 409) {
        setBlocked(true); onDirtyChange(true);
        setNotice('保存冲突或回执不确定，草稿保留，禁止重复写入。核对原文档后明确采用，或到原文档目录核对首次创建结果。');
      } else setBlocked(false);
    } finally { lock.current = false; if (alive.current) { setWorking(false); setSaving(false); } }
  }
  async function inspect(target: string, selectedPin?: PlanningSnapshot) {
    if (!current() || lock.current || busy || imagePending || !target || renderedAuthorEpoch !== authorEpoch.current || reviewed !== reviewedRef.current) return;
    lock.current = true; setWorking(true); setError(''); setCandidate(undefined); setDiscardConfirmed(false);
    const ticket = ++epoch.current, generation = scope.current.generation, selectedGeneration = selection.current.generation, authored = authorEpoch.current, canvasScope = canvasHandoff?.verificationScope, canvasGeneration = canvasLifetime.current.generation;
    verifiedIntent.current = undefined; setReviewedPin(undefined);
    try {
      const value = await read(() => client.export(target));
      if (!owns(generation) || ticket !== epoch.current || reviewed !== reviewedRef.current || authored !== authorEpoch.current || composing.current || canvasGeneration !== canvasLifetime.current.generation || canvasHandoff && !canvasHandoff.isVerificationCurrent() || canvasScope !== canvasRef.current?.verificationScope || selectedGeneration !== selection.current.generation || selectedPin && (!selectedPinRef.current || !samePin(selectedPin, selectedPinRef.current))) return;
      if (value.document.id !== target || value.document.mode !== 'DIRECTOR' || !Number.isSafeInteger(value.document.version)
        || value.document.version < 1 || !/^[a-f0-9]{64}$/.test(value.document_digest)) throw new Error('导演来源回执不完整。');
      const verified = { id: target, version: value.document.version, digest: value.document_digest };
      if (reviewed?.id === target) {
        const exact = reviewedDirectorSnapshot(reviewed, value.document, value.document_digest,
          reviewed.expectedSnapshot ?? (snapshot?.id === reviewed.id && snapshot.version === reviewed.version ? snapshot : undefined));
        if (!pending) {
          verifiedIntent.current = { pin: exact, canvasScope, authored, selected: selectedGeneration, generation, canvasGeneration, receipt: reviewed, isCanvasCurrent: canvasHandoff?.isVerificationCurrent, consumed: false };
          setReviewedPin(exact);
        }
      }
      if (pending) setCandidate({ document: value.document, pin: verified });
      else { setBase(value.document); setDraft(documentInput(value.document)); setSnapshot(verified); setScene(undefined); setShot(undefined); }
      setNotice(selectedPin && !samePin(selectedPin, verified)
        ? '来源已变化：这里是当前原文档，不能当作节点绑定的旧版本。旧图绑定保持不变，请另建明确绑定当前版本的节点／图。'
        : '已从原 Creative owner 读取当前版本与摘要；没有执行或批准内容。');
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function discard() {
    if (!current() || busy || lock.current || !discardConfirmed) return;
    recovery.clear();
    setDraft(candidate ? documentInput(candidate.document) : base ? documentInput(base) : empty());
    if (candidate) { setBase(candidate.document); setSnapshot(candidate.pin); }
    if (blocked && !candidate) setNotice('仅放弃了本地草稿；远端保存结果仍未知。再次创建前先核对原文档目录，避免重复创建。');
    setCandidate(undefined); setBlocked(false); mark(false); setDiscardConfirmed(false); setError('');
  }
  async function restoreAuthorDraft() {
    const cached = recovery.candidate;
    if (!cached || !verifyDraftOwner || !current() || !authorized || !canMutate || busy || lock.current
      || dirty || blocked || handoffPending || proposalPending || scopePending || imagePending || composing.current) return;
    const generation = scope.current.generation, ticket = ++epoch.current, authored = authorEpoch.current, selected = selection.current.generation;
    const verifier = verifyDraftOwner;
    lock.current = true; setWorking(true); setError('');
    try {
      recovery.verifyCandidate(cached);
      const result = await read(async () => {
        await verifier();
        if (!owns(generation) || ticket !== epoch.current) throw new Error('导演恢复身份已改变。');
        recovery.verifyCandidate(cached);
        const caps = await client.capabilities();
        if (!caps.enabled || !caps.can_mutate || !caps.modes.includes('DIRECTOR')) throw new Error('当前身份没有导演作者权限，草稿未恢复。');
        if (!owns(generation) || ticket !== epoch.current) throw new Error('导演恢复身份已改变。');
        recovery.verifyCandidate(cached);
        if (!cached.base) return undefined;
        const value = await client.export(cached.base.id);
        if (value.document.mode !== 'DIRECTOR' || value.document.status !== 'DRAFT' || value.document.id !== cached.base.id
          || value.document.version !== cached.base.version || !/^[a-f0-9]{64}$/.test(value.document_digest)
          || cached.base.digest && value.document_digest !== cached.base.digest) throw new Error('导演原文档版本或摘要已变化，恢复草稿保持；请先核对原文档。');
        return value;
      });
      if (!owns(generation) || ticket !== epoch.current || authored !== authorEpoch.current || selected !== selection.current.generation || composing.current) return;
      recovery.consume(cached);
      reviewedRef.current = undefined; setReviewed(undefined); setReviewedPin(undefined); verifiedIntent.current = undefined;
      setBase(result?.document); setSnapshot(result ? { id: result.document.id, version: result.document.version, digest: result.document_digest } : undefined);
      setDraft(cached.draft); setCandidate(undefined); setScene(undefined); setShot(undefined); setDiscardConfirmed(false);
      setBlocked(cached.uncertain); mark(true);
      setNotice(cached.uncertain ? '已恢复作者输入；原保存结果仍未知，禁止重新提交。请核对原文档或目录后明确处理。' : '已恢复导演作者输入，尚未保存到服务端。原审批、任务和图绑定没有恢复或改变。');
    } catch (reason) { if (owns(generation) && ticket === epoch.current) fail(reason); }
    finally { lock.current = false; if (alive.current) setWorking(false); }
  }
  function proofCurrent() {
    const proof = verifiedIntent.current;
    return !!proof && !proof.consumed && proof.receipt === reviewedRef.current && proof.receipt.id === proof.pin.id && proof.receipt.version === proof.pin.version
      && proof.canvasGeneration === canvasLifetime.current.generation && (!proof.isCanvasCurrent || proof.isCanvasCurrent()) && proof.pin === reviewedPin && proof.canvasScope === canvasRef.current?.verificationScope
      && proof.authored === authorEpoch.current && proof.selected === selection.current.generation && owns(proof.generation);
  }
  function placeReviewed() {
    if (!current() || !editing || lock.current || pending || composing.current || !proofCurrent() || !reviewedPin
      || !base || base.status !== 'DRAFT' || base.id !== reviewedPin.id || base.version !== reviewedPin.version
      || !canvasHandoff?.available) return;
    lock.current = true; verifiedIntent.current!.consumed = true;
    try {
      if (!canvasHandoff.insert({ id: reviewedPin.id, version: reviewedPin.version, digest: reviewedPin.digest }, canvasHandoff.scope)) {
        setError('画布目标或编辑状态已变化，请重新核对导演原文档版本后重试。'); return;
      }
      setError('');
      setNotice('已添加审核后的导演草稿绑定，尚未保存创作图。请明确保存；没有自动连接、运行或修改原导演文档。');
    } finally { lock.current = false; }
  }
  if (!active || !isCurrent()) return null;
  if (authorityDenied || recovery.retired) return <StatusMessage tone="warning">导演作者身份或权限已改变，内容已隐藏；本机恢复副本未删除。请重新打开工作区核对权限。</StatusMessage>;
  if (ownerClient.current !== client) return <StatusMessage tone="warning">导演来源连接已改变，请重新打开工作区。</StatusMessage>;
  return <Panel title="画布导演总控台 · 可选">
    <p>人工编排：复用原导演文档、版本与审核。此面板可关闭；不要求其它模块先经过导演。</p>
    {!open ? <Button disabled={busy || working} onClick={() => void reveal()}>打开导演总控台</Button> : <>
      <Button disabled={pending || busy || working} onClick={() => setOpen(false)}>折叠导演总控台</Button>
      {!authorized && !working && <StatusMessage tone="warning">原 Creative owner 尚未授予导演编辑能力；仍可核对当前选中节点的来源。</StatusMessage>}
      <Button disabled={busy || working || imagePending} onClick={() => void listDocuments()}>读取导演原文档目录</Button>
      <label>总控台原导演文档<select value={choice} disabled={busy || working || imagePending} onChange={event => { authorEpoch.current++; setReviewedPin(undefined); setChoice(event.target.value); }}>
        <option value="">明确选择原文档</option>{documents.map(row => <option key={row.id} value={row.id}>{row.title} · v{row.version}</option>)}
      </select></label>
      <Button disabled={!choice || busy || working || imagePending} onClick={() => void inspect(choice, pin?.id === choice ? pin : undefined)}>读取所选导演原文档</Button>
      <Button disabled={!pin || pending || busy || working} onClick={() => pin && void inspect(pin.id, pin)}>读取选中导演节点原文档</Button>
      <Button disabled={!base || busy || working || imagePending} onClick={() => base && void inspect(base.id, pin?.id === base.id ? pin : undefined)}>核对导演原文档版本</Button>
      {pin && <p>选中节点绑定：{pin.id} · v{pin.version} · {pin.digest}</p>}
      {snapshot && <p>当前原文档：{snapshot.id} · v{snapshot.version} · {snapshot.digest}</p>}
      {pin && base?.id === pin.id && (base.version !== pin.version || snapshot && !samePin(pin, snapshot)) && <StatusMessage tone="warning">节点来源已变更，原绑定没有自动更新；请核对下游影响。</StatusMessage>}
      {pin && <GraphDirectorSourceImpact key={JSON.stringify([selectedKey, base?.id, base?.version])} client={client} pin={pin} graph={graph} selectedNodeId={selectedNodeId} active={active && !imagePending} busy={busy || working} isCurrent={isCurrent} read={read} />}
      {authorized && <DirectorAuthorRecoveryPanel candidate={recovery.candidate} notice={recovery.notice} savedAt={recovery.savedAt}
        enabled={recovery.enabled && !!verifyDraftOwner} busy={busy || working || imagePending} canRestore={!!verifyDraftOwner && canMutate && !dirty && !blocked && !handoffPending && !proposalPending && !scopePending && !imagePending}
        onRestore={() => void restoreAuthorDraft()} onDiscard={recovery.clear} />}
      {notice && <StatusMessage>{notice}</StatusMessage>}{error && <StatusMessage tone="error">{error}</StatusMessage>}
      {working && <StatusMessage>正在读取或保存原导演文档…</StatusMessage>}
      {authorized && hasDirectorProposalReview(client) && <GraphDirectorProposalReview client={client}
        active={active && !imagePending} canMutate={canMutate && !recovery.candidate && !dirty && !blocked && !handoffPending && !scopePending && !imagePending} busy={busy || working}
        isCurrent={isCurrent} read={read} mutate={mutate} onPendingChange={proposalChanged} onOpenModels={onOpenModels}
        onDenied={() => fail(new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: '导演审核来源当前不可读取。' }))}
        onDocument={(row, expectedSnapshot) => {
          if (!current() || recovery.candidate || dirty || blocked || handoffPending || imagePending || lock.current) return;
          if (row.mode !== 'DIRECTOR' || row.status !== 'DRAFT' || !row.id || !Number.isSafeInteger(row.version) || row.version < 1)
            throw new Error('审核后的导演文档回执无效，请读取原建议状态。');
          const expected = expectedSnapshot ? reviewedDirectorSnapshot({ id: row.id, version: row.version }, row, expectedSnapshot.digest, expectedSnapshot) : undefined;
          authorEpoch.current++; const receipt = { id: row.id, version: row.version, ...(expected ? { expectedSnapshot: expected } : {}) }; reviewedRef.current = receipt; setReviewed(receipt); setReviewedPin(undefined);
          setBase(row); setDraft(documentInput(row)); setSnapshot(undefined); setCandidate(undefined);
          setScene(undefined); setShot(undefined); setDiscardConfirmed(false); setError('');
          setNotice(`已读取人工审核后的原导演草稿“${row.title}” · v${row.version}。请核对原文档摘要，再明确添加并保存画布节点；原图绑定保持不变。`);
        }} />}
      {reviewed && canvasHandoff && <section aria-label="审核导演草稿画布放置">
        <p>先核对导演原文档版本，再添加精确绑定。请在原节点目录明确选择支持导演节点的图格式，或明确新建图；这里不会升级或替换当前图。</p>
        <Button disabled={!editing || pending || !proofCurrent() || !reviewedPin || !canvasHandoff.available}
          onClick={placeReviewed}>将此审核草稿添加到画布</Button>
      </section>}
      <div onCompositionStartCapture={() => { composing.current = true; authorEpoch.current++; setReviewedPin(undefined); }}
        onCompositionEndCapture={() => { composing.current = false; authorEpoch.current++; }}>
      <CreativeCanvas draft={draft} version={base?.version} dirty={dirty} canEdit={editing} busy={busy || working} saving={saving}
        selectedSceneId={scene} selectedShotId={shot} onScene={setScene} onShot={setShot} onChange={change}
        onSave={() => void save()} onNew={fresh} />
      </div>
      {base && snapshot && imageClient && <DirectorImageReviewPanel client={imageClient} source={base} snapshot={snapshot} selectionKey={selectedKey}
        active={active} available={authorized && canMutate && base.status === 'DRAFT' && !dirty && !blocked && !handoffPending && !proposalPending && !scopePending && !working}
        busy={busy || working} isCurrent={current} read={read} mutate={mutate} onPending={imageChanged} onOpenModels={onOpenModels} onOpenBroker={onOpenBroker}
        onDenied={() => fail(new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: '图像导演当前不可读取。' }))}
        onAdopted={receipt => {
          if (!current()) return;
          authorEpoch.current++; setReviewed(undefined); reviewedRef.current = undefined; setReviewedPin(undefined);
          setSnapshot(undefined); setBlocked(true); imageChanged(false); onDirtyChange(true);
          setNotice(`图像审核备注已保存到原导演文档 v${receipt.target.version}。请核对原文档版本并明确采用已核对内容，再继续编辑；原图绑定未改变。`);
        }} />}
      {base && snapshot && client.deriveDirectorScope && <DirectorSceneScopePanel source={base} snapshot={snapshot} request={client.deriveDirectorScope}
        available={authorized && active && canMutate && !dirty && !blocked && !handoffPending && !proposalPending && !imagePending && !working}
        busy={busy || working} isCurrent={current} mutate={mutate} onPending={setScopePending} onOpen={id => { if (current() && !pending) void inspect(id); }} />}
      {base && client.directorSheetExport && <DirectorSheetExportPanel document={base} available={authorized && active && !pending && !busy && !working} isCurrent={current} request={client.directorSheetExport} onDenied={() => fail(new ApiError({status:403,code:'PROJECT_SCOPE_FORBIDDEN',message:'当前导演文档不可导出。'}))}/>}
      {base && <GraphDirectorStoryboardHandoff canOpen={!dirty && !blocked && !proposalPending && !imagePending && storyboardAllowed} onOpenStoryboard={onOpenStoryboard ? (request, originCurrent) => {
        const authored = authorEpoch.current, selected = selection.current.generation, generation = scope.current.generation;
        onOpenStoryboard(request, () => originCurrent() && current() && authored === authorEpoch.current && selected === selection.current.generation && owns(generation));
      } : undefined} client={client} source={base} snapshot={snapshot} active={active && authorized && !imagePending} canCreate={editing && !dirty && storyboardAllowed} busy={busy || working} isCurrent={isCurrent} read={read} mutate={mutate} onPending={setHandoffPending} />}
      {(dirty || blocked) && <section aria-label="导演草稿处理"><p>导演草稿尚未保存或待核对，图编辑与运行暂时锁定。本机恢复状态见上方；未确认保留时，关闭页面可能丢失输入。</p>
        <Button disabled={!authorized || !canMutate || busy || working} onClick={() => {
          if (!current() || !authorized || !canMutate || busy || working || lock.current || composing.current || renderedAuthorEpoch !== authorEpoch.current) return;
          try { downloadPortableBlob(directorDraftBackup(draft, base, snapshot, blocked), 'director-author-draft-backup.json');
            setNotice('已发起本地作者草稿备份下载。原草稿、未保存状态与图绑定保持不变；这不是服务端保存回执。');
          } catch (reason) { setError(reason instanceof Error ? reason.message : '本地草稿备份未完成，原输入保持不变。'); }
        }}>下载导演未保存草稿备份</Button>
        <p>备份是可阅读的 JSON 作者副本，不含会话凭证，不会自动导入、重试保存或运行；请自行保管其中的创作内容。</p>
        {candidate && <><p>已核对服务端：{candidate.document.title} · v{candidate.document.version} · {candidate.pin.digest}</p><DirectorDraftComparison local={draft} server={candidate.document} /></>}
        <label><input type="checkbox" checked={discardConfirmed} disabled={busy || working} onChange={event => setDiscardConfirmed(event.target.checked)} />{blocked && !candidate ? '确认仅放弃导演本地草稿，远端结果仍未知；再次创建前先核对目录' : '确认放弃导演本地草稿'}{candidate ? '并采用已核对原版本' : ''}</label>
        <Button disabled={!discardConfirmed || busy || working} onClick={discard}>处理导演本地草稿</Button>
      </section>}
      <p>保存后，在原“导演、分镜与视觉制作节点目录”中读取文档并添加导演节点，再保存创作图。节点只保存 ID、版本与摘要；连接与执行仍走原图及人工审核。</p>
    </>}
  </Panel>;
}
