import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { assertCanvasImageNodeJob, assertSavedImageNode, canonicalImageNode, checkedCanvasImageNodeBinding, imageNodeApprovedPin,
  imageNodePromptDigest, canvasImageNodeInCommand, verifyCanvasImageNodePrompt, type CanvasImageNodeBinding } from './canvasImageNode';
import type { CanvasAssetReference, CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioAsset, StudioClient } from './studioClient';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';

export type CanvasImageNodeTaskProps = { projectId: string; node: { id: string; title: string; prompt: string; x: number; y: number };
  client: StudioClient; production: StudioProductionClient; owner: StudioGraphDraftOwner;
  canMutate: boolean; canReview: boolean; isCurrent: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; mutate: <T>(work: () => Promise<T>) => Promise<T>; onClose?: () => void };
type Proof = { canvas: CanvasViewRecord; job: ProductionJob; asset: StudioAsset; pin: CanvasAssetReference };
const scopeFor = (owner: StudioGraphDraftOwner) => owner.mode === 'local'
  ? { mode: 'local' as const, novel_id: owner.projectId }
  : { mode: 'collaboration' as const, novel_id: owner.projectId, workspace_id: owner.workspaceId, storyline_id: owner.storylineId, branch_id: owner.branchId };
/** A one-node intent; it never serializes the browser graph or owns production state. */
export function CanvasImageNodeTask(props: CanvasImageNodeTaskProps) {
  const [base, setBase] = useState<CanvasViewRecord>(), [binding, setBinding] = useState<CanvasImageNodeBinding>(), [job, setJob] = useState<ProductionJob>();
  const [saved, setSaved] = useState<CanvasViewRecord>(), [proof, setProof] = useState<Proof>(), [ack, setAck] = useState(false), [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState(''), [childDirty, setChildDirty] = useState(false);
  const [recovery, setRecovery] = useState<{ record: CanvasViewRecord; binding: CanvasImageNodeBinding; job: ProductionJob }[]>([]);
  const alive = useRef(true), running = useRef(false), unknown = useRef(false), live = useRef(props), proofRef = useRef(proof), ackRef = useRef<Proof>();
  const baseRef = useRef(base), bindingRef = useRef(binding), jobRef = useRef(job), childDirtyRef = useRef(childDirty);
  live.current = props; proofRef.current = proof; baseRef.current = base; bindingRef.current = binding; jobRef.current = job; childDirtyRef.current = childDirty;
  const values = [props.projectId, props.client, props.production, canonicalImageNode(props.owner), canonicalImageNode(props.node), props.canMutate, props.canReview];
  const fence = useRef({ values, token: {} }), first = useRef(fence.current.token);
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const current = () => { try { return alive.current && first.current === fence.current.token && live.current.isCurrent(); } catch { return false; } };
  const requestId = useRef(`node-${crypto.randomUUID()}`);
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  function requireCurrent(write = false) {
    if (!current() || live.current.owner.projectId !== live.current.projectId || write && (!live.current.canMutate || unknown.current))
      throw new Error('原节点、项目、权限或未确认操作已改变，请关闭后重新核对；不会重新发送。');
  }
  const read = async <T,>(work: () => Promise<T>): Promise<T> => {
    requireCurrent(); const result = await live.current.read(() => { requireCurrent(); return work(); }); requireCurrent(); return result;
  };
  const mutate = async <T,>(work: () => Promise<T>): Promise<T> => {
    requireCurrent(true); return live.current.mutate(() => { requireCurrent(true); return work(); });
  };
  async function verifyOwner(write = false) {
    requireCurrent(write); const overview = await read(() => live.current.client.overview());
    if (overview.project.id !== props.projectId || overview.project.incarnation !== props.owner.incarnation || write && !overview.capabilities.can_mutate)
      throw new Error('当前项目代次或写入权限未确认，原草稿保留。');
    return overview;
  }
  function clearProof() { proofRef.current = undefined; ackRef.current = undefined; setProof(undefined); setAck(false); }
  function markUnknown(message: string) { unknown.current = true; clearProof(); setUncertain(true); setError(message); }
  function start(write = false) { if (running.current || childDirtyRef.current || !current() || write && unknown.current) return false; running.current = true; setBusy(true); setError(''); clearProof(); return true; }
  function finish() { running.current = false; if (alive.current) setBusy(false); }
  async function prepare() {
    if (baseRef.current || bindingRef.current || !start(true)) return;
    let dispatched = false;
    try {
      await verifyOwner(true);
      const node = props.node, promptDigest = await imageNodePromptDigest(node.prompt); requireCurrent(true);
      // Validate the complete non-authoritative placement before creating any view.
      checkedCanvasImageNodeBinding({ contract: 'studio-canvas-image-node/1', project_id: props.projectId, scope: scopeFor(props.owner), incarnation: props.owner.incarnation,
        canvas_id: 'syntax-check-only', canvas_version: 1, canvas_digest: '0'.repeat(64), node_id: node.id, title: node.title,
        position: { x: node.x, y: node.y }, prompt_digest: promptDigest });
      if (!node.prompt.trim() || node.prompt.length > 16000) throw new Error('请先填写有效的原节点提示词。');
      const canvas = await mutate(() => { dispatched = true; return props.client.graphs.canvasViews!.create({ schema_version: 1, title: node.title, cards: [], viewport: { x: 0, y: 0, zoom: 1 } }, requestId.current); });
      requireCurrent();
      if (canvas.project_id !== props.projectId || canonicalImageNode(canvas.scope) !== canonicalImageNode(scopeFor(props.owner)) || canvas.definition.cards.length || canvas.definition.image_node_origin)
        throw new Error('新建位置回执与原节点不一致，需读取原记录核对。');
      const target = checkedCanvasImageNodeBinding({ contract: 'studio-canvas-image-node/1', project_id: props.projectId, scope: canvas.scope,
        incarnation: props.owner.incarnation, canvas_id: canvas.id, canvas_version: canvas.version, canvas_digest: canvas.definition_digest,
        node_id: node.id, title: node.title, position: { x: node.x, y: node.y }, prompt_digest: promptDigest });
      bindingRef.current = target; baseRef.current = canvas; setBinding(target); setBase(canvas); setNotice('已保存空白作品位置；尚未入队或生成，节点图与连线仍是浏览器草稿。');
    } catch (reason) {
      if (dispatched) markUnknown('空白位置保存结果待核对；保留原请求 ID，不会自动新建或重发。');
      else if (current()) setError(reason instanceof Error ? reason.message : '正式节点位置准备失败。');
    } finally { finish(); }
  }
  async function checkApproved(expected: ProductionJob, target: CanvasImageNodeBinding): Promise<Proof> {
    await verifyOwner(true);
    const actualJob = await read(() => props.production.get('image', expected.id));
    assertCanvasImageNodeJob(target, actualJob); await verifyCanvasImageNodePrompt(actualJob.command!); requireCurrent(true);
    if (actualJob.version !== expected.version || actualJob.request_digest !== expected.request_digest || !actualJob.output_candidate)
      throw new Error('原审核任务版本已改变，请重新读取后核对。');
    const asset = await read(() => props.client.asset(actualJob.output_candidate!.id)), pin = imageNodeApprovedPin(target, actualJob, asset);
    const canvas = await read(() => props.client.graphs.canvasViews!.get(target.canvas_id));
    const history = await read(() => props.client.graphs.canvasViews!.history(target.canvas_id));
    if (history.incarnation !== target.incarnation || canvas.project_id !== target.project_id || canonicalImageNode(canvas.scope) !== canonicalImageNode(target.scope)
      || canvas.version !== target.canvas_version || canvas.definition_digest !== target.canvas_digest || canvas.definition.cards.length || canvas.definition.image_node_origin
      || history.current_version !== canvas.version || history.current_definition_digest !== canvas.definition_digest)
      throw new Error('原空白作品位置或代次已变化，候选保留；不会采用到其他位置。');
    return { canvas, job: actualJob, asset, pin };
  }
  async function inspect() {
    const expected = jobRef.current, target = bindingRef.current; if (!expected || !target || !start(true)) return;
    try { const result = await checkApproved(expected, target); requireCurrent(true); proofRef.current = result; setProof(result); }
    catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : '正式审核来源核对失败。'); }
    finally { finish(); }
  }
  async function adopt() {
    const captured = proofRef.current, target = bindingRef.current;
    if (!captured || !target || ackRef.current !== captured || !ack || !start(true)) return;
    let dispatched = false;
    try {
      const fresh = await checkApproved(captured.job, target);
      if (canonicalImageNode(fresh.pin) !== canonicalImageNode(captured.pin)) throw new Error('正式资产 pin 已改变，请重新核对。');
      const row = await mutate(() => { requireCurrent(true); dispatched = true; return props.client.graphs.canvasViews!.imageNodeResult(fresh.canvas, target.incarnation, fresh.job, fresh.pin); });
      requireCurrent(); assertSavedImageNode(row, target, fresh.job, fresh.pin, true); setSaved(row); baseRef.current = row; setBase(row);
      setNotice('已保存正式节点资产位置。可显式读取已保存位置核对；浏览器草稿没有升级成共享画布。');
    } catch (reason) {
      if (dispatched) markUnknown('节点采用结果待核对；只能读取原记录，不会自动采用或重发。');
      else if (current()) setError(reason instanceof Error ? reason.message : '正式节点采用未完成。');
    } finally { finish(); }
  }
  async function reopen() {
    if (!start()) return;
    try {
      await verifyOwner(); const digest = await imageNodePromptDigest(props.node.prompt); requireCurrent();
      const candidates = await read(() => props.production.list()); const found: {record:CanvasViewRecord;binding:CanvasImageNodeBinding;job:ProductionJob}[] = [];
      for (const candidate of candidates) {
        const target = canvasImageNodeInCommand(candidate.command);
        if (!target || target.node_id !== props.node.id || target.project_id !== props.projectId || target.incarnation !== props.owner.incarnation
          || canonicalImageNode(target.scope) !== canonicalImageNode(scopeFor(props.owner))) continue;
        if(found.length>=32)throw new Error('相同节点记录较多，请从原任务列表按任务 ID 核对；不会猜测位置。');
        const actual = await read(() => props.production.get('image', candidate.id)); assertCanvasImageNodeJob(target, actual);
        await verifyCanvasImageNodePrompt(actual.command!); requireCurrent();
        const canvas = await read(() => props.client.graphs.canvasViews!.get(target.canvas_id));
        const history = await read(() => props.client.graphs.canvasViews!.history(target.canvas_id));
        if (history.incarnation !== target.incarnation || history.current_version !== canvas.version || history.current_definition_digest !== canvas.definition_digest) throw new Error('原保存位置的代次或当前版本未确认。');
        if (canvas.definition.image_node_origin) {
          if(canvas.definition.image_node_origin.job_id!==actual.id)continue;
          const asset = await read(() => props.client.asset(canvas.definition.image_node_origin!.asset.asset_id));
          const pin = imageNodeApprovedPin(target, actual, asset); assertSavedImageNode(canvas, target, actual, pin);
          found.push({record:canvas,binding:target,job:actual});
        } else if (target.prompt_digest === digest && target.title === props.node.title && canonicalImageNode(target.position) === canonicalImageNode({x:props.node.x,y:props.node.y})
          && canvas.version === target.canvas_version && canvas.definition_digest === target.canvas_digest && canvas.definition.cards.length === 0) {
          found.push({record:canvas,binding:target,job:actual});
        }
      }
      requireCurrent(); setRecovery(found);
      setNotice(found.length?'已读取原节点记录，请明确选择一条查看；没有执行、审核或重新采用。':'读取已完成；没有可恢复的相同节点任务。已保存位置仅以明确展示的服务端回执为准。');
    } catch (reason) { if (current()) setError(reason instanceof Error ? reason.message : '原节点位置读取失败；不会重新发送。'); }
    finally { finish(); }
  }
  const task = useMemo(() => binding ? { binding, initialPrompt: props.node.prompt, isCurrent: () => current() && bindingRef.current === binding } : undefined, [binding]);
  const approved = job?.status === 'APPROVED';
  return <section aria-label="正式图片节点与保存位置">
    <Panel title="正式图片节点任务" actions={props.onClose && <Button onClick={props.onClose}>关闭正式节点任务</Button>}>
      <p>节点 {props.node.id} · {props.node.title} · 坐标 ({props.node.x}, {props.node.y})。只为此节点创建原生产任务；提示词、连线和其他节点仍是浏览器草稿。</p>
      <p>先显式保存空白作品位置，再分别预览、入队、执行和人工审核。审核成功后还需单独确认采用；不兼容的旧队列结果不会变成正式来源。</p>
      {!base && <Button disabled={!current() || !props.canMutate || busy || uncertain} onClick={() => void prepare()}>为此节点保存正式空白位置</Button>}
      <Button disabled={!current() || busy || childDirty} onClick={() => void reopen()}>读取此节点已保存位置与任务</Button>
      <p>原位置请求 ID：<code>{requestId.current}</code></p>
      {base && <p>原服务端画布 {base.id} · v{base.version} · {saved ? '已保存正式资产关联' : '空白位置，尚未采用资产'}</p>}
      {!current() && <StatusMessage tone="warning">原身份、权限或节点已改变。请取消选择后重新选择节点并打开入口；旧确认不会恢复。</StatusMessage>}
      {uncertain && <StatusMessage tone="warning">操作结果待核对。当前实例只可读取，不会自动重发；原输入与请求 ID 保留。</StatusMessage>}
      {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
      {recovery.map(row => <Button key={row.job.id} disabled={!current() || busy || uncertain&&!row.record.definition.image_node_origin || childDirty} onClick={() => {
        if (!current() || running.current || unknown.current&&!row.record.definition.image_node_origin || childDirtyRef.current) return; clearProof();
        if(row.record.definition.image_node_origin){
          if(unknown.current&&jobRef.current?.id===row.job.id&&canonicalImageNode(bindingRef.current)===canonicalImageNode(row.binding)){unknown.current=false;setUncertain(false);}
          setSaved(row.record);
        }else setSaved(undefined); bindingRef.current=row.binding;baseRef.current=row.record;jobRef.current=row.job;setBinding(row.binding);setBase(row.record);setJob(row.job);setNotice(row.record.definition.image_node_origin?'已从原服务端画布读回节点、当前坐标、正式任务来源与精确资产 pin；未执行、审核或重新采用。':'已打开原节点任务，只读恢复没有执行或采用。');
      }}>{row.record.definition.image_node_origin?'查看已保存节点位置':'打开原正式节点任务'} {row.job.id} · {row.job.status}</Button>)}
      {saved && <dl aria-label="服务端节点资产关联"><dt>画布及节点</dt><dd>{saved.id} / {saved.definition.image_node_origin?.target.node_id}</dd>
        <dt>保存坐标</dt><dd>{canonicalImageNode(saved.definition.cards.find(card=>card.id===saved.definition.image_node_origin?.target.node_id)?.position)}</dd><dt>正式资产 pin</dt><dd>{canonicalImageNode(saved.definition.image_node_origin?.asset)}</dd>
        <dt>保存来源提示词摘要</dt><dd>{saved.definition.image_node_origin?.target.prompt_digest}（当前浏览器草稿可能已改变）</dd>
        <dt>原生产任务</dt><dd>{saved.definition.image_node_origin?.job_id} · v{saved.definition.image_node_origin?.job_version}</dd></dl>}
    </Panel>
    {task && !saved && !uncertain && <StudioMediaExecutionPanel key={canonicalImageNode(task.binding)} client={props.production} assets={[]} canvasNodeTask={task}
      canMutate={props.canMutate && current()} canReview={props.canReview && current()} busy={busy} isBusy={() => running.current} isCurrent={current}
      read={read} mutate={mutate} onDirtyChange={value => { childDirtyRef.current=value;setChildDirty(value); }}
      externalJob={job} onUnavailable={() => { first.current={};setError('原生产任务权限或身份已改变，请重新打开项目。'); }}
      onJob={value => { if (!current() || !bindingRef.current) return; assertCanvasImageNodeJob(bindingRef.current,value);clearProof();jobRef.current=value;setJob(value); }}
      onApproved={value => { if (!current() || !bindingRef.current) return;assertCanvasImageNodeJob(bindingRef.current,value);clearProof();jobRef.current=value;setJob(value); }}/>}
    {approved && task && !saved && <Panel title="采用到原节点作品位置">
      <p>原生产 owner 已记录人工审核。这里重新核对来源元数据，不代替候选预览或审核；保存后固定回到原节点坐标。</p>
      <Button disabled={!current() || !props.canMutate || busy || uncertain || childDirty} onClick={() => void inspect()}>核对正式结果与原节点位置</Button>
      {proof && <><p>仅采用资产 {proof.pin.asset_id} · v{proof.pin.version} 到节点 {task.binding.node_id}。</p>
        <label><input type="checkbox" checked={ack} disabled={busy || uncertain || !current()} onChange={event => {if (!current() || proofRef.current!==proof || running.current || unknown.current)return;ackRef.current=event.target.checked?proof:undefined;setAck(event.target.checked);}}/>确认采用此正式资产到原节点位置</label>
        <Button disabled={!ack || busy || uncertain || !current()} onClick={() => void adopt()}>确认采用并保存节点位置</Button></>}
    </Panel>}
  </section>;
}
