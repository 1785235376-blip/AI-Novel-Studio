import { useLayoutEffect, useMemo, useRef, useState } from 'react';
import { Button, Panel, StatusMessage } from '../ui/primitives';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { assertCanvasImageNodeJob, assertSavedImageNode, canonicalImageNode, checkedCanvasImageNodeBinding, imageNodeApprovedPin,
  imageNodePromptDigest, canvasImageNodeInCommand, verifyCanvasImageNodePrompt, type CanvasImageNodeBinding } from './canvasImageNode';
import type { CanvasAssetReference, CanvasViewRecord } from './studioCanvasViewClient';
import type { StudioAsset, StudioClient } from './studioClient';
import type { StudioGraphDraftOwner } from './studioGraphLocalDraft';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import { assertCanvasImageNodeQueueReceipt, canvasImageNodeQueueHintKey, clearCanvasImageNodeQueueHint, persistCanvasImageNodeQueueHint,
  readCanvasImageNodeQueueHint, type CanvasImageNodeQueueHintState } from './canvasImageNodeQueueIntent';
import type { MediaCommand, ProductionPreview } from './studioProductionClient';
import { checkedCanvasImageNodeCreateIntent, emptyImageNodeDefinition, canvasImageNodeCreateHintKey,
  readCanvasImageNodeCreateHint, persistCanvasImageNodeCreateHint, clearCanvasImageNodeCreateHint,
  type CanvasImageNodeCreateIntent, type CanvasImageNodeCreateHintState } from './canvasImageNodeCreateIntent';

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
  const [createHint, setCreateHint] = useState<CanvasImageNodeCreateHintState>(() => readCanvasImageNodeCreateHint(props.owner, props.node.id));
  const hintRef=useRef(createHint);hintRef.current=createHint;
  const [queueHint,setQueueHint]=useState<CanvasImageNodeQueueHintState>(()=>readCanvasImageNodeQueueHint(props.owner,props.node.id));
  const queueHintRef=useRef(queueHint);queueHintRef.current=queueHint;
  const [queueInput,setQueueInput]=useState<{command:MediaCommand;requestDigest:string}>();
  const [base, setBase] = useState<CanvasViewRecord>(), [binding, setBinding] = useState<CanvasImageNodeBinding>(), [job, setJob] = useState<ProductionJob>();
  const [saved, setSaved] = useState<CanvasViewRecord>(), [proof, setProof] = useState<Proof>(), [ack, setAck] = useState(false), [busy, setBusy] = useState(false);
  const [uncertain, setUncertain] = useState(createHint.state!=='absent'||queueHint.state!=='absent'), [error, setError] = useState(''), [notice, setNotice] = useState(''), [childDirty, setChildDirty] = useState(false);
  const [recovery, setRecovery] = useState<{ record: CanvasViewRecord; binding: CanvasImageNodeBinding; job: ProductionJob }[]>([]);
  const alive = useRef(true), running = useRef(false), unknown = useRef(createHint.state!=='absent'||queueHint.state!=='absent'), live = useRef(props), proofRef = useRef(proof), ackRef = useRef<Proof>();
  const baseRef = useRef(base), bindingRef = useRef(binding), jobRef = useRef(job), childDirtyRef = useRef(childDirty);
  live.current = props; proofRef.current = proof; baseRef.current = base; bindingRef.current = binding; jobRef.current = job; childDirtyRef.current = childDirty;
  const values = [props.projectId, props.client, props.production, canonicalImageNode(props.owner), canonicalImageNode(props.node), props.canMutate, props.canReview];
  const fence = useRef({ values, token: {} }), first = useRef(fence.current.token);
  if (values.some((value, index) => !Object.is(value, fence.current.values[index]))) fence.current = { values, token: {} };
  const current = () => { try { return alive.current && first.current === fence.current.token && live.current.isCurrent(); } catch { return false; } };
  const requestId = useRef(createHint.state==='present'?createHint.hint.request_id:`node-${crypto.randomUUID()}`);
  const activeRequest=useRef<{active:boolean;controller:AbortController}>();
  useLayoutEffect(() => {
    alive.current = true;
    const storageChanged=(event:StorageEvent)=>{
      if(event.key!==null&&event.key!==canvasImageNodeCreateHintKey(props.owner,props.node.id)&&event.key!==canvasImageNodeQueueHintKey(props.owner,props.node.id))return;
      const actual=readCanvasImageNodeCreateHint(props.owner,props.node.id),expected=hintRef.current;
      if(actual.state!==expected.state||actual.state==='blocked'||actual.state==='present'&&(expected.state!=='present'||actual.raw!==expected.raw)||!queueHintIsCurrent()){
        first.current={};unknown.current=true;setUncertain(true);setError('创建记录已由其他窗口改变；保留原请求，不会创建或入队。');
      }
    };
    window.addEventListener('storage',storageChanged);
    return () => { alive.current = false;window.removeEventListener('storage',storageChanged);if(activeRequest.current){activeRequest.current.active=false;activeRequest.current.controller.abort();} };
  }, []);
  function requireCurrent(write = false) {
    if (!current() || live.current.owner.projectId !== live.current.projectId || write && (!live.current.canMutate || unknown.current || !hintIsCurrent() ||!queueHintIsCurrent()||queueHintRef.current.state!=='absent'))
      throw new Error('原节点、项目、权限或未确认操作已改变，请关闭后重新核对；不会重新发送。');
  }
  const read = async <T,>(work: () => Promise<T>): Promise<T> => {
    requireCurrent(); const result = await live.current.read(() => { requireCurrent(); return work(); }); requireCurrent(); return result;
  };
  const mutate = async <T,>(work: () => Promise<T>): Promise<T> => {
    requireCurrent(true); return live.current.mutate(() => { requireCurrent(true); return work(); });
  };
  async function verifyOwner(write = false, signal?:AbortSignal) {
    requireCurrent(write); const overview = await read(() => live.current.client.overview(signal));
    if (overview.project.id !== props.projectId || overview.project.incarnation !== props.owner.incarnation || write && !overview.capabilities.can_mutate)
      throw new Error('当前项目代次或写入权限未确认，原草稿保留。');
    return overview;
  }
  function clearProof() { proofRef.current = undefined; ackRef.current = undefined; setProof(undefined); setAck(false); }
  function markUnknown(message: string) { unknown.current = true; clearProof(); setUncertain(true); setError(message); }
  function start(write = false) { if (running.current || childDirtyRef.current || !current() || write && unknown.current) return false; running.current = true; setBusy(true); setError(''); clearProof(); return true; }
  function finish() { running.current = false; if (alive.current) setBusy(false); }
  function rememberHint(value:CanvasImageNodeCreateHintState){hintRef.current=value;setCreateHint(value);}
  function rememberQueueHint(value:CanvasImageNodeQueueHintState){queueHintRef.current=value;setQueueHint(value);}
  function queueHintIsCurrent(){
    const actual=readCanvasImageNodeQueueHint(props.owner,props.node.id),expected=queueHintRef.current;
    return actual.state===expected.state&&actual.state!=='blocked'&&(actual.state!=='present'||expected.state==='present'&&actual.raw===expected.raw);
  }
  function requireQueueHint(expected:Extract<CanvasImageNodeQueueHintState,{state:'present'}>){
    if(!queueHintIsCurrent()||queueHintRef.current.state!=='present'||queueHintRef.current.raw!==expected.raw)throw new Error('原任务入队意图已改变，不能恢复其他请求。');
  }
  function hintIsCurrent(){
    const actual=readCanvasImageNodeCreateHint(props.owner,props.node.id),expected=hintRef.current;
    return actual.state==='absent'&&expected.state==='absent'||actual.state==='present'&&expected.state==='present'&&actual.raw===expected.raw;
  }
  function requireHint(expected:Extract<CanvasImageNodeCreateHintState,{state:'present'}>){
    const actual=readCanvasImageNodeCreateHint(props.owner,props.node.id);
    if(actual.state!=='present'||actual.raw!==expected.raw)throw new Error('本浏览器的创建意图已改变，不能继续原请求。');
  }
  async function bounded<T,>(work:(signal:AbortSignal,check:()=>void)=>Promise<T>):Promise<T>{
    const request={active:true,controller:new AbortController()};activeRequest.current=request;
    const check=()=>{requireCurrent();if(!request.active||activeRequest.current!==request||request.controller.signal.aborted)throw new Error('原创建请求或读取已退役。');};
    let timer:ReturnType<typeof setTimeout>|undefined;
    const timeout=new Promise<never>((_resolve,reject)=>{timer=setTimeout(()=>{request.active=false;request.controller.abort();reject(new Error('读取或创建超时，结果仍待核对；不会重发。'));},15000);});
    try{return await Promise.race([work(request.controller.signal,check),timeout]);}
    finally{if(timer!==undefined)clearTimeout(timer);request.active=false;request.controller.abort();if(activeRequest.current===request)activeRequest.current=undefined;}
  }
  function nodeIntent(promptDigest:string):CanvasImageNodeCreateIntent{
    return checkedCanvasImageNodeCreateIntent({contract:'studio-canvas-image-node-create/1',project_id:props.projectId,
      scope:scopeFor(props.owner),incarnation:props.owner.incarnation,node_id:props.node.id,title:props.node.title,
      position:{x:props.node.x,y:props.node.y},prompt_digest:promptDigest});
  }
  function acceptEmpty(canvas:CanvasViewRecord,intent:CanvasImageNodeCreateIntent){
    if(canvas.project_id!==intent.project_id||canonicalImageNode(canvas.scope)!==canonicalImageNode(intent.scope)||canvas.version!==1
      ||canvas.capacity.history_used!==0||canonicalImageNode(canvas.definition)!==canonicalImageNode(emptyImageNodeDefinition(intent)))throw new Error('原空白位置的回执或版本不一致，结果仍待核对。');
    const {contract:_contract,...origin}=intent;
    const target=checkedCanvasImageNodeBinding({...origin,contract:'studio-canvas-image-node/1',canvas_id:canvas.id,
      canvas_version:canvas.version,canvas_digest:canvas.definition_digest});
    bindingRef.current=target;baseRef.current=canvas;setBinding(target);setBase(canvas);unknown.current=false;setUncertain(false);
  }
  async function prepare() {
    if (baseRef.current || bindingRef.current || hintRef.current.state!=='absent' ||queueHintRef.current.state!=='absent'|| !start(true)) return;
    let dispatched = false;
    let attemptedIntent:CanvasImageNodeCreateIntent|undefined;
    try {
      await bounded(async(signal,check)=>{
        await verifyOwner(true,signal);check();
        const promptDigest=await imageNodePromptDigest(props.node.prompt);check();requireCurrent(true);
        const intent=nodeIntent(promptDigest);
        if(!props.node.prompt.trim()||props.node.prompt.length>16000)throw new Error('请先填写有效的原节点提示词。');
        const canvas=await mutate(()=>{
          check();
          attemptedIntent=intent;
          const hint=persistCanvasImageNodeCreateHint(props.owner,props.node.id,requestId.current,intent);rememberHint(hint);requireHint(hint);
          unknown.current=true;setUncertain(true);dispatched=true;
          return props.client.graphs.canvasViews!.create(emptyImageNodeDefinition(intent),requestId.current,intent,signal);
        });
        check();const hint=hintRef.current;if(hint.state!=='present')throw new Error('原创建记录缺失。');requireHint(hint);
        acceptEmpty(canvas,intent);setNotice('已保存空白作品位置；尚未入队或生成，节点图与连线仍是浏览器草稿。');
      });
    } catch (reason) {
      if(current()){
        if(dispatched||hintRef.current.state!=='absent')markUnknown('空白位置保存结果待核对；保留原请求 ID，不会自动新建或重发。');
        else{
          const state=readCanvasImageNodeCreateHint(props.owner,props.node.id);
          if(state.state==='present'&&attemptedIntent&&state.hint.request_id===requestId.current
            &&canonicalImageNode(state.hint.intent)===canonicalImageNode(attemptedIntent)){
            rememberHint(state);markUnknown('创建意图已保留，但尚未确认请求派发；只能核对原请求，不会再次创建。');
          }else if(state.state!=='absent'){
            rememberHint({state:'blocked',message:'本浏览器创建记录已改变或无法核对，未发送创建请求；不会改用其他请求。'});
            first.current={};markUnknown('创建意图保存失败或与其他窗口冲突；原输入保留，未发送创建请求。');
          }else setError(reason instanceof Error?reason.message:'正式节点位置准备失败。');
        }
      }
    } finally { finish(); }
  }
  async function resolveCreate(){
    const hint=hintRef.current;
    if(baseRef.current||bindingRef.current||hint.state!=='present'||queueHintRef.current.state!=='absent'||!start())return;
    try{
      await bounded(async(signal,check)=>{
        const overview=await verifyOwner(false,signal);check();requireHint(hint);
        if(!props.canMutate||!overview.capabilities.can_mutate)throw new Error('当前写入权限未确认；保留原创建意图，不会恢复排队入口。');
        const digest=await imageNodePromptDigest(props.node.prompt);check();
        if(canonicalImageNode(nodeIntent(digest))!==canonicalImageNode(hint.hint.intent))throw new Error('当前节点与保留的创建意图不一致，不能恢复关联。');
        const canvas=await read(()=>{check();requireHint(hint);return props.client.graphs.canvasViews!.resolveImageNodeCreate(hint.hint.request_id,hint.hint.intent,signal);});
        check();requireHint(hint);acceptEmpty(canvas,hint.hint.intent);setNotice('已由原服务端唯一创建记录恢复空白位置；尚未入队、执行或审核。');
      });
    }catch(reason){if(current())markUnknown('未确认唯一且未改变的原创建结果；仍保留原请求，不会再次创建或入队。'+(reason instanceof Error?reason.message:''));}
    finally{finish();}
  }
  function clearHintAfterJob(value:ProductionJob){
    const hint=hintRef.current,target=bindingRef.current;if(hint.state==='absent')return true;if(hint.state!=='present'||!target)return false;
    assertCanvasImageNodeJob(target,value);
    const {contract:_contract,...origin}=hint.hint.intent;
    if(canonicalImageNode({...origin,contract:'studio-canvas-image-node/1',canvas_id:target.canvas_id,canvas_version:target.canvas_version,canvas_digest:target.canvas_digest})!==canonicalImageNode(target))return false;
    if(clearCanvasImageNodeCreateHint(props.owner,props.node.id,hint.raw)){rememberHint({state:'absent'});return true;}
    const actual=readCanvasImageNodeCreateHint(props.owner,props.node.id);if(actual.state!=='present'||actual.raw!==hint.raw)first.current={};
    markUnknown('原创建记录未确认清理，任务保留在原队列；请重新打开核对。');return false;
  }
  function beforeNodeQueue(command:MediaCommand,preview:ProductionPreview){
    requireCurrent(true);const target=bindingRef.current;
    if(!target||canonicalImageNode(canvasImageNodeInCommand(command))!==canonicalImageNode(target)||command.request_id!==preview.request_id)throw new Error('原节点任务预览已改变，未派发。');
    setQueueInput({command:structuredClone(command),requestDigest:preview.request_digest});
    try{
      const hint=persistCanvasImageNodeQueueHint(props.owner,props.node.id,command.request_id,preview.request_digest,target);
      rememberQueueHint(hint);requireQueueHint(hint);
    }catch(reason){
      const actual=readCanvasImageNodeQueueHint(props.owner,props.node.id);
      if(actual.state==='present'&&actual.hint.request_id===command.request_id&&actual.hint.request_digest===preview.request_digest
        &&canonicalImageNode(actual.hint.binding)===canonicalImageNode(target))rememberQueueHint(actual);
      else if(actual.state!=='absent')rememberQueueHint({state:'blocked',message:'入队记录保存失败或已被其他窗口改变；未派发，不能改用其他请求。'});
      throw reason;
    }
  }
  function nodeQueueUnknown(){
    if(!current())return;
    if(queueHintRef.current.state!=='absent'){childDirtyRef.current=false;setChildDirty(false);markUnknown('原图片任务入队结果待核对；保留原请求身份，不会重复创建或执行。');}
    else setError('入队恢复记录未保存，未继续派发；请保留原输入并重新打开核对存储。');
  }
  function acceptJob(value:ProductionJob){
    try{return acceptJobChecked(value);}catch{
      if(current())markUnknown('原任务回执或恢复记录不匹配，未关联其他请求；请显式重新核对。');return false;
    }
  }
  function acceptJobChecked(value:ProductionJob){
    if(!current()||!bindingRef.current)return false;assertCanvasImageNodeJob(bindingRef.current,value);
    const hint=queueHintRef.current;
    if(hint.state==='blocked'){markUnknown('入队记录无法核对，原任务保留；不会关联其他请求。');return false;}
    if(hint.state==='present'){
      assertCanvasImageNodeQueueReceipt(hint.hint,value);requireQueueHint(hint);
    }
    if(!clearHintAfterJob(value)||!current()||unknown.current)return false;
    if(hint.state==='present'){
      requireQueueHint(hint);
      if(!clearCanvasImageNodeQueueHint(props.owner,props.node.id,hint.raw)){markUnknown('原任务回执已读取，但恢复记录未确认清理；不会重复入队。');return false;}
      rememberQueueHint({state:'absent'});
    }
    if(!hintIsCurrent()||!queueHintIsCurrent())throw new Error('原恢复记录已改变，不能发布任务关联。');
    clearProof();jobRef.current=value;setJob(value);return true;
  }
  async function resolveQueue(){
    const hint=queueHintRef.current;
    if(hint.state!=='present'||running.current||!current())return;
    running.current=true;setBusy(true);setError('');childDirtyRef.current=false;setChildDirty(false);markUnknown('正在核对原图片任务入队结果；不会再次创建或派发。');
    try{
      await bounded(async(signal,check)=>{
        const overview=await verifyOwner(false,signal);check();requireQueueHint(hint);
        if(!props.canMutate||!overview.capabilities.can_mutate)throw new Error('当前写入权限未确认，不能恢复任务入口。');
        const target=hint.hint.binding,digest=await imageNodePromptDigest(props.node.prompt);check();
        const {contract:_contract,canvas_id:_id,canvas_version:_version,canvas_digest:_digest,...intent}=target;
        if(canonicalImageNode(nodeIntent(digest))!==canonicalImageNode({...intent,contract:'studio-canvas-image-node-create/1'}))throw new Error('当前节点与原入队意图不符。');
        const resolve=props.production.resolveImageNodeCreate;if(typeof resolve!=='function')throw new Error('当前制作客户端不支持原入队请求读取；请保留原记录。');
        const actual=await read(()=>{check();requireQueueHint(hint);return resolve(hint.hint.request_id,hint.hint.request_digest,target,signal);});
        check();requireQueueHint(hint);assertCanvasImageNodeQueueReceipt(hint.hint,actual);await verifyCanvasImageNodePrompt(actual.command!);check();
        const creation=hintRef.current;
        if(creation.state==='blocked')throw new Error('原空白位置创建记录损坏，不能替换其关联。');
        const canvas=await read(()=>{check();requireQueueHint(hint);return creation.state==='present'
          ?props.client.graphs.canvasViews!.resolveImageNodeCreate(creation.hint.request_id,creation.hint.intent,signal)
          :props.client.graphs.canvasViews!.get(target.canvas_id,signal);});
        const history=await read(()=>{check();requireQueueHint(hint);return props.client.graphs.canvasViews!.history(target.canvas_id,signal);});
        check();requireQueueHint(hint);
        if(canvas.id!==target.canvas_id||canvas.version!==target.canvas_version||canvas.definition_digest!==target.canvas_digest
          ||history.incarnation!==target.incarnation||history.current_version!==canvas.version||history.current_definition_digest!==canvas.definition_digest)throw new Error('原画布版本已改变，不能恢复到其他位置。');
        acceptEmpty(canvas,{...intent,contract:'studio-canvas-image-node-create/1'});if(!acceptJob(actual))throw new Error('原任务关联未确认保存。');
        if(queueHintRef.current.state!=='absent')throw new Error('原入队恢复记录未确认完成。');
        unknown.current=false;setUncertain(false);setNotice('已恢复原生产任务的当前记录；没有重新入队、执行或审核，执行需重新核对并确认。');
      });
    }catch(reason){if(current())markUnknown('原入队结果仍待核对；未找到或已改变不允许重发。'+(reason instanceof Error?reason.message:''));}
    finally{finish();}
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
    if(queueHintRef.current.state!=='absent'){setError('已有待核对的原入队请求，请使用原请求核对入口；不会猜测列表中的任务。');return;}
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
  const task = useMemo(() => binding ? { binding, initialPrompt: props.node.prompt, isCurrent: () => current() && hintIsCurrent() &&queueHintIsCurrent()&& bindingRef.current === binding } : undefined, [binding]);
  const approved = job?.status === 'APPROVED';
  return <section aria-label="正式图片节点与保存位置">
    <Panel title="正式图片节点任务" actions={props.onClose && <Button onClick={props.onClose}>关闭正式节点任务</Button>}>
      <p>节点 {props.node.id} · {props.node.title} · 坐标 ({props.node.x}, {props.node.y})。只为此节点创建原生产任务；提示词、连线和其他节点仍是浏览器草稿。</p>
      <p>先显式保存空白作品位置，再分别预览、入队、执行和人工审核。审核成功后还需单独确认采用；不兼容的旧队列结果不会变成正式来源。</p>
      {!base && <Button disabled={!current() || !props.canMutate || busy || uncertain} onClick={() => void prepare()}>为此节点保存正式空白位置</Button>}
      {createHint.state==='present'&&!base&&queueHint.state==='absent'&&<Button disabled={!current()||busy||childDirty} onClick={()=>void resolveCreate()}>重新核对此次空白位置创建</Button>}
      {queueHint.state==='present'&&<><p>待核对的原入队请求：<code>{queueHint.hint.request_id}</code></p><Button disabled={!current()||busy||!props.production.resolveImageNodeCreate} onClick={()=>void resolveQueue()}>核对原图片任务入队结果</Button>
        {!props.production.resolveImageNodeCreate&&<StatusMessage tone="warning">当前制作客户端缺少原请求读取能力；请保留原记录，不会改用列表猜测或重新入队。</StatusMessage>}</>}
      {current()&&queueHint.state==='present'&&queueInput?.command.request_id===queueHint.hint.request_id&&queueInput.requestDigest===queueHint.hint.request_digest&&<details><summary>当前会话保留的入队输入</summary>
        <p>{queueInput.command.provider_id} · {queueInput.command.model_id}（只读；不会从此处重发）</p>
        <label>入队时原提示词<textarea readOnly value={queueInput.command.prompt}/></label><pre>{JSON.stringify(queueInput.command.parameters,null,2)}</pre>
        <p>这些输入仅保留在当前会话；浏览器恢复提示只保存身份和摘要。</p></details>}
      {queueHint.state==='blocked'&&<StatusMessage tone="warning">{queueHint.message}</StatusMessage>}
      {createHint.state==='blocked'&&<StatusMessage tone="warning">{createHint.message}</StatusMessage>}
      <Button disabled={!current() || busy || childDirty} onClick={() => void reopen()}>读取此节点已保存位置与任务</Button>
      <p>原位置请求 ID：<code>{requestId.current}</code></p>
      {base && <p>原服务端画布 {base.id} · v{base.version} · {saved ? '已保存正式资产关联' : '空白位置，尚未采用资产'}</p>}
      {!current() && <StatusMessage tone="warning">原身份、权限或节点已改变。请取消选择后重新选择节点并打开入口；旧确认不会恢复。</StatusMessage>}
      {uncertain && <StatusMessage tone="warning">操作结果待核对。当前实例只可读取，不会自动重发；原输入与请求 ID 保留。</StatusMessage>}
      {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <StatusMessage>{notice}</StatusMessage>}
      {recovery.map(row => <Button key={row.job.id} disabled={!current() || busy ||queueHint.state!=='absent'|| uncertain&&!row.record.definition.image_node_origin || childDirty} onClick={() => {
        if (!current() || running.current ||queueHintRef.current.state!=='absent'|| unknown.current&&!row.record.definition.image_node_origin || childDirtyRef.current) return; clearProof();
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
      beforeNodeQueue={beforeNodeQueue} onNodeQueueUnknown={nodeQueueUnknown}
      externalJob={job} onUnavailable={() => { first.current={};setError('原生产任务权限或身份已改变，请重新打开项目。'); }}
      onJob={acceptJob}
      onApproved={value=>{acceptJob(value);}}/>}
    {approved && task && !saved && <Panel title="采用到原节点作品位置">
      <p>原生产 owner 已记录人工审核。这里重新核对来源元数据，不代替候选预览或审核；保存后固定回到原节点坐标。</p>
      <Button disabled={!current() || !props.canMutate || busy || uncertain || childDirty} onClick={() => void inspect()}>核对正式结果与原节点位置</Button>
      {proof && <><p>仅采用资产 {proof.pin.asset_id} · v{proof.pin.version} 到节点 {task.binding.node_id}。</p>
        <label><input type="checkbox" checked={ack} disabled={busy || uncertain || !current()} onChange={event => {if (!current() || proofRef.current!==proof || running.current || unknown.current)return;ackRef.current=event.target.checked?proof:undefined;setAck(event.target.checked);}}/>确认采用此正式资产到原节点位置</label>
        <Button disabled={!ack || busy || uncertain || !current()} onClick={() => void adopt()}>确认采用并保存节点位置</Button></>}
    </Panel>}
  </section>;
}
