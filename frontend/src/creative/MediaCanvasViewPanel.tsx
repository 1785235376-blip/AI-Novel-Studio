import { captureCanvasVideoTrimTask } from './canvasVideoTrimTask';
import { useMediaCanvasRecovery } from './useMediaCanvasRecovery';
import { focusCanvasCard, searchCanvasCards } from './mediaCanvasSearch';
import { MediaCanvasGraphHandoff } from './MediaCanvasGraphHandoff';
import { MediaCanvasImageGraphStarter } from './MediaCanvasImageGraphStarter';
import { CanvasImageTaskReturn } from './CanvasImageTaskReturn';
import { MediaCanvasHistoryPanel } from './MediaCanvasHistoryPanel';
import { CanvasImageTaskRecovery } from './CanvasImageTaskRecovery';
import { captureCanvasAudioTrimTask } from './canvasAudioTrimTask';
import { captureCanvasImageTask, type CanvasImageTaskOrigin, type CanvasImageTaskSession } from './canvasImageTask';
import type { ProductionJob, StudioProductionClient } from './studioProductionClient';
import type { CanvasImageGraphHandoff } from './canvasImageGraphStarter';
import { GraphImageOutputStarterPanel } from './GraphImageOutputStarterPanel';
import type { ImageOutputHandoff } from './graphImageOutputStarter';
import type { CanvasGraphAssetHandoff } from './mediaCanvasGraphHandoffHelpers';
import { alignCanvasCards } from './mediaCanvasSelection';
import { emptyCanvasHistory, recordCanvasEdit, travelCanvasEdit } from './mediaCanvasHistory';
import { MediaCanvasGroupTools } from './MediaCanvasGroupTools';
import { removeCanvasCard } from './mediaCanvasGroups';
import { CanvasAssetPreview } from './CanvasAssetPreview';
import { MediaCardViewport } from './MediaCardViewport';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { apiErrorView } from '../api';
import type { StudioGraphEditorProps } from './useStudioGraphEditorController';
import { checkedCanvasDefinition, type CanvasDefinition, type CanvasViewRecord, type CanvasViewSummary } from './studioCanvasViewClient';
import type { StudioAsset } from './studioClient';
import { clampGraphPosition, clampGraphZoom } from './graphCanvasGeometry';
import { mediaViewportCenter } from './mediaCanvasGeometry';
import './mediaCanvas.css';
const blank = (): CanvasDefinition => ({ schema_version: 1, title: '媒体素材画布', cards: [], viewport: { x: 0, y: 0, zoom: 1 } });
type Props = Pick<StudioGraphEditorProps, 'active' | 'denied' | 'identity' | 'client' | 'canMutate' | 'busy' | 'externalDirty' | 'isCurrent' | 'read' | 'mutate' | 'isBusy' | 'draftOwner'> & { onDirtyChange: (dirty: boolean) => void; graphHandoff?: CanvasGraphAssetHandoff; imageGraphHandoff?: CanvasImageGraphHandoff; imageOutputHandoff?: ImageOutputHandoff;
  onBeginImageTask?:(origin:CanvasImageTaskOrigin,asset:StudioAsset,isOriginCurrent:()=>boolean)=>void;
  onResumeImageTask?:(origin:CanvasImageTaskOrigin,asset:StudioAsset,isOriginCurrent:()=>boolean,job:ProductionJob)=>void;
  canvasTask?:CanvasImageTaskSession;canvasTaskApproved?:ProductionJob;taskProduction?:StudioProductionClient;onTaskReturned?:()=>void };

/** Display metadata only; generation, media download and execution keep their original owners. */
export function MediaCanvasViewPanel(props: Props) {
  const createRequest = useRef(`view-${crypto.randomUUID()}`), recoveryBusy = useRef(false);
  const history = useRef(emptyCanvasHistory()); const [, setHistoryRevision] = useState(0);
  const resetHistory = () => { history.current = emptyCanvasHistory(); setHistoryRevision(v => v + 1); };
  const [draft, setDraft] = useState(blank), [base, setBase] = useState<CanvasViewRecord>();
  const [rows, setRows] = useState<CanvasViewSummary[]>([]), [assets, setAssets] = useState<StudioAsset[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const selectionEpoch = useRef(0), selectionGeneration = selectionEpoch.current;
  const [selected, setSelected] = useState(''), [assetId, setAssetId] = useState(''), [query, setQuery] = useState('');
  const [pending, setPending] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [discard, setDiscard] = useState(false), [size, setSize] = useState({ width: 800, height: 480 });
  const alive = useRef(true), pendingRef = useRef(false), draftRef = useRef(draft), live = useRef(props);
  const sourceEpoch = useRef(0), baseRef = useRef(base), dirtyRef = useRef(false);
  const originOwner=JSON.stringify(props.draftOwner),originOwnerRef=useRef(originOwner);
  if(originOwnerRef.current!==originOwner){originOwnerRef.current=originOwner;sourceEpoch.current++;}
  baseRef.current=base;
  draftRef.current = draft; live.current = props;
  const dirty = uncertain || JSON.stringify(draft) !== JSON.stringify(base?.definition ?? blank());
  dirtyRef.current=dirty;
  const client = props.client.graphs.canvasViews;
  const authority = [props.identity, props.client, props.active, props.denied, props.canMutate, props.externalDirty, base, draft, discard, selected, JSON.stringify(selectedIds)];
  const fence = useRef({ values: authority, token: {} });
  if (authority.some((value, index) => value !== fence.current.values[index])) fence.current = { values: authority, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && live.current.active && !live.current.denied && live.current.isCurrent();
  const locked = () => !current() || recoveryBusy.current || pendingRef.current || live.current.busy || !!live.current.isBusy?.() || live.current.externalDirty;
  const recovery = useMediaCanvasRecovery({ owner: props.draftOwner, client: props.client, active: props.active, denied: props.denied,
    canMutate: props.canMutate, busy: props.busy || pending, externalDirty: props.externalDirty, definition: draft, base, dirty, uncertain,
    requestId: createRequest.current, isCurrent: current, read: props.read, onBusy: value => { recoveryBusy.current = value; },
    onRestore: (snapshot, record) => { if (!current() || !live.current.canMutate) return;sourceEpoch.current++;baseRef.current=record;dirtyRef.current=true; resetHistory(); setBase(record);
      const restored = structuredClone(snapshot.definition); draftRef.current = restored; setDraft(restored); createRequest.current = snapshot.request_id;
      setUncertain(snapshot.uncertain); setSelected(''); setSelectedIds([]); setDiscard(false); setNotice('已恢复本机媒体草稿，尚未保存或执行。'); live.current.onDirtyChange(true); } });
  const editable = !locked() && props.canMutate && !uncertain;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  function edit(next: CanvasDefinition, recordHistory = true) {
    if (locked() || !live.current.canMutate || uncertain) return false;
    try { const valid = checkedCanvasDefinition(next); if (JSON.stringify(valid) === JSON.stringify(draftRef.current)) return false; sourceEpoch.current++;dirtyRef.current=true;if (recordHistory) { history.current = recordCanvasEdit(history.current, draftRef.current); setHistoryRevision(v => v + 1); } draftRef.current = valid; setDraft(valid); setDiscard(false); setNotice('尚未保存'); live.current.onDirtyChange(true); return true; }
    catch { setError('画布内容超出允许范围，当前草稿已保留。'); return false; }
  }
  function travel(redo: boolean) {
    if (locked() || !live.current.canMutate || uncertain) return;
    const next = travelCanvasEdit(history.current, draftRef.current, redo); if (!next) return;
    if (edit(next.definition, false)) { history.current = next.history; setHistoryRevision(v => v + 1); }
  }
  async function work<T>(write: boolean, task: () => Promise<T>, accept: (value: T) => void) {
    if (!client || locked() || write && (!live.current.canMutate || uncertain)) return;
    pendingRef.current = true; setPending(true); setError('');
    try { const value = await (write ? props.mutate(task) : props.read(task)); if (current()) accept(value); else if (write && alive.current) { setUncertain(true); live.current.onDirtyChange(true); } }
    catch (reason) { if (current()) setError(apiErrorView(reason).message); if (write && alive.current) { setUncertain(true); live.current.onDirtyChange(true); } }
    finally { pendingRef.current = false; if (alive.current) setPending(false); }
  }
  function adopt(row: CanvasViewRecord) { sourceEpoch.current++;baseRef.current=row;dirtyRef.current=false;resetHistory(); setBase(row); setDraft(row.definition); draftRef.current = row.definition; setSelected(''); setSelectedIds([]); setUncertain(false); setDiscard(false); setNotice('已读取持久化版本'); live.current.onDirtyChange(false); }
  function open(id: string) { if (dirty && !discard) return; void work(false, () => client!.get(id), adopt); }
  const states = new Map(base?.reference_states.map(row => [row.card_id, row]) ?? []);
  const currentCardIds = new Set(draft.cards.map(card => card.id));
  const selection = selectedIds.filter(id => currentCardIds.has(id));
  function selectCard(id: string, additive = false) { if (!current() || pendingRef.current) return; selectionEpoch.current++; setSelected(id); setSelectedIds(previous => additive ? previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id] : [id]); }
  const card = draft.cards.find(c => c.id === selected);
  function beginImageTask(){
    if(!base||!card?.asset||!['image','audio','video'].includes(card.asset.kind)||!editable||dirty||!props.onBeginImageTask)return;
    if(!props.draftOwner){setError('当前项目代次尚未核对，不能建立可恢复的卡片任务。');return;}
    const canvas=base,cardId=card.id,assetId=card.asset.asset_id,epoch=sourceEpoch.current,identity=props.identity,originalClient=props.client;
    void work(false,()=>props.client.asset(assetId),asset=>{
      try{const origin=(asset.kind==='video'?captureCanvasVideoTrimTask:asset.kind==='audio'?captureCanvasAudioTrimTask:captureCanvasImageTask)(canvas,cardId,asset,props.draftOwner!.incarnation);
        const isOriginCurrent=()=>alive.current&&live.current.identity===identity&&live.current.client===originalClient&&live.current.active&&!live.current.denied&&live.current.canMutate&&live.current.isCurrent()
          &&sourceEpoch.current===epoch&&!dirtyRef.current&&baseRef.current?.id===origin.canvasId&&baseRef.current.version===origin.canvasVersion&&baseRef.current.definition_digest===origin.canvasDigest;
        if(isOriginCurrent())props.onBeginImageTask!(origin,asset,isOriginCurrent);
      }catch(reason){setError(reason instanceof Error?reason.message:'图片卡片未通过核验。');}
    });
  }
  const matches = searchCanvasCards(draft, query);
  // Reference selection is metadata-only. The graph owner separately fences its own
  // dirty draft; all layout writes retain the original externalDirty lock.
  const imageSourceCurrent = () => current() && selectionEpoch.current === selectionGeneration && draftRef.current === draft
    && !!base && !dirty && !discard && !uncertain && !recoveryBusy.current && !pendingRef.current
    && !live.current.busy && !live.current.isBusy?.() && live.current.canMutate;
  const imageSources = selection.flatMap(id => { const row = draft.cards.find(value => value.id === id);
    return row?.asset?.kind === 'image' && states.get(id)?.state === 'CURRENT_METADATA' ? [{ cardId: id, reference: row.asset }] : []; });
  const imageChoiceAvailable = imageSourceCurrent() && props.imageGraphHandoff?.available;
  const textSourceCurrent = () => current() && draftRef.current === draft && !dirty && !discard && !uncertain
    && !recoveryBusy.current && !pendingRef.current && !live.current.busy && !live.current.isBusy?.() && live.current.canMutate;
  if (!props.active || props.denied || !client) return null;
  return <section className="media-canvas" aria-label="独立媒体素材画布" onKeyDown={event => {
      if (event.nativeEvent.isComposing || event.altKey || !(event.ctrlKey || event.metaKey) || (event.target as HTMLElement).closest('input,textarea,select,[contenteditable="true"]')) return;
      const key = event.key.toLowerCase(), redo = key === 'y' || key === 'z' && event.shiftKey;
      if (key !== 'z' && key !== 'y' || !editable || !(redo ? history.current.future.length : history.current.past.length)) return;
      event.preventDefault(); travel(redo);
    }}>
    {recovery.panel}
    <h3>媒体素材画布</h3><p>独立保存素材引用与位置。此视图不执行生成，也不改变执行图；选择卡片后可按需核验预览，仍复用原素材面板。</p>
    <div className="creative-actions">
      <Button disabled={!editable || !history.current.past.length} onClick={() => travel(false)}>撤销媒体画布编辑</Button>
      <Button disabled={!editable || !history.current.future.length} onClick={() => travel(true)}>重做媒体画布编辑</Button>
      <Button disabled={pending || props.busy || props.externalDirty} onClick={() => void work(false, () => client.list(), value => setRows(value.items))}>读取已存画布</Button>
      <Button disabled={!editable || draft.cards.some(c => !c.asset)} onClick={() => {
        const snapshot = draftRef.current; const requestId = createRequest.current;
        void work(true, () => base ? client.save(base.id, base.version, snapshot) : client.create(snapshot, requestId), row => { adopt(row); setNotice('已保存媒体画布'); });
      }}>保存媒体画布</Button>
      <Button disabled={pending || props.externalDirty || dirty && !discard} onClick={() => { if (locked() || dirty && !discard) return; const next = blank();sourceEpoch.current++;baseRef.current=undefined;dirtyRef.current=false; createRequest.current = `view-${crypto.randomUUID()}`; resetHistory(); setBase(undefined); setDraft(next); draftRef.current = next; setSelected(''); setSelectedIds([]); setUncertain(false); setDiscard(false); live.current.onDirtyChange(false); }}>新建空白视图</Button>
      <Button disabled={!editable} onClick={() => void work(false, () => props.client.assets(), value => setAssets(value.items.filter(a => ['image', 'video', 'audio'].includes(a.kind))))}>读取可用素材</Button>
    </div>
    <p>本地撤销最多 20 步、总快照不超过 2 MB；大画布可能提前淘汰旧记录。保存或重新读取后重置。快捷键 Ctrl／⌘ Z，重做 Ctrl Y 或 Shift Z；文字输入框保留自身撤销。</p>
    {props.taskProduction&&props.onResumeImageTask&&<CanvasImageTaskRecovery client={props.client} production={props.taskProduction} owner={props.draftOwner} ownerToken={token}
      disabled={dirty||pending||props.busy||props.externalDirty} canMutate={props.canMutate} isCurrent={current} read={props.read}
      onResume={(row,asset,job,origin)=>{if(!current()||locked()||!props.canMutate)return;adopt(row);const epoch=sourceEpoch.current,identity=props.identity,originalClient=props.client;
        const isOriginCurrent=()=>alive.current&&sourceEpoch.current===epoch&&live.current.identity===identity&&live.current.client===originalClient&&live.current.active&&!live.current.denied
          &&live.current.canMutate&&live.current.draftOwner?.incarnation===origin.binding?.incarnation&&live.current.isCurrent()&&!dirtyRef.current&&baseRef.current?.id===origin.canvasId&&baseRef.current.version===origin.canvasVersion&&baseRef.current.definition_digest===origin.canvasDigest;
        props.onResumeImageTask!(origin,asset,isOriginCurrent,job);setNotice('已从原 Job 恢复精确卡片位置；没有执行或采用，请继续原审核和回流确认。');}}/>}
    {base&&typeof client.history==='function'&&<MediaCanvasHistoryPanel base={base} client={client} owner={token} incarnation={props.draftOwner?.incarnation} canMutate={props.canMutate}
      externalDirty={dirty||props.externalDirty} busy={pending||props.busy} isBusy={props.isBusy} isCurrent={current} read={props.read} mutate={props.mutate}
      onAdopt={row=>{adopt(row);props.onTaskReturned?.();setNotice('已恢复为新的当前画布版本；原历史保留，旧选择和预览已退役。');}}
      onUncertain={()=>{sourceEpoch.current++;dirtyRef.current=true;setUncertain(true);live.current.onDirtyChange(true);}}/>}
    {dirty && <label><input type="checkbox" checked={discard} onChange={e => setDiscard(e.target.checked)} />允许用所选已存版本或空白视图替换当前草稿</label>}
    {uncertain && <StatusMessage tone="warning">保存结果尚未确认。已停止再次保存，请读取已存画布并核对；替换草稿需要上方明确确认。</StatusMessage>}
    {rows.length > 0 && <ul>{rows.map(row => <li key={row.id}><Button disabled={pending || props.externalDirty || dirty && !discard} onClick={() => open(row.id)}>{row.title} · v{row.version} · {row.card_count} 张</Button></li>)}</ul>}
    <div className="creative-actions">
      <label>画布标题<input value={draft.title} disabled={!editable} maxLength={160} onChange={e => edit({ ...draftRef.current, title: e.target.value })} /></label>
      <label>素材<select value={assetId} disabled={!editable} onChange={e => setAssetId(e.target.value)}><option value="">选择素材</option>{assets.map(a => <option key={a.id} value={a.id}>{a.filename}</option>)}</select></label>
      <Button disabled={!editable || !assetId || draft.cards.length >= 1000} onClick={() => {
        const asset = assets.find(a => a.id === assetId); if (!asset || !['image', 'video', 'audio'].includes(asset.kind)) return;
        const id = `Card_${crypto.randomUUID().replaceAll('-', '')}`, position = mediaViewportCenter(draftRef.current, size.width, size.height);
        edit({ ...draftRef.current, cards: [...draftRef.current.cards, { id, position: { x: clampGraphPosition(position.x), y: clampGraphPosition(position.y) }, asset: { asset_id: asset.id, version: asset.version, digest: asset.sha256, kind: asset.kind as 'image' | 'video' | 'audio' } }] }); selectCard(id);
      }}>加入引用卡片</Button>
      <label>查找卡片或素材 ID<input value={query} onChange={e => setQuery(e.target.value)} /></label>
    </div>
    {query.trim() && <section aria-label="画布查找结果"><p>匹配 {matches.length} 张，显示前 20 张。定位会移动视口并展开该卡片的上级分组；需要保存才会保留视图变化。</p>
      {matches.slice(0,20).map(result => <Button key={result.id} disabled={!editable} onClick={() => {
        if (locked() || !live.current.canMutate || uncertain) return;
        try { edit(focusCanvasCard(draftRef.current,result.id,size.width,size.height)); selectCard(result.id); } catch { setError('卡片或视口已改变，请重新查找。'); }
      }}>定位 {result.id}</Button>)}{!matches.length && <p>没有匹配卡片。隐藏或无权访问的素材详情不会参与查找。</p>}
    </section>}
    <div className="creative-actions">
      {(['x', 'y'] as const).map(axis => <label key={axis}>视口 {axis}<input type="number" min={-100000} max={100000} value={draft.viewport[axis]} disabled={!editable} onChange={e => edit({ ...draftRef.current, viewport: { ...draftRef.current.viewport, [axis]: clampGraphPosition(e.target.valueAsNumber) } })} /></label>)}
      <label>缩放<input type="number" step="0.1" min="0.35" max="2.5" value={draft.viewport.zoom} disabled={!editable} onChange={e => edit({ ...draftRef.current, viewport: { ...draftRef.current.viewport, zoom: clampGraphZoom(e.target.valueAsNumber) } })} /></label>
    </div>
    <div className="creative-actions"><span>已选 {selection.length} 张卡片</span>
      <Button disabled={!editable} onClick={() => { if (!locked()) { selectionEpoch.current++; setSelectedIds(draft.cards.map(c => c.id)); setSelected(draft.cards[0]?.id ?? ''); } }}>选择全部卡片（含视口外）</Button>
      <Button disabled={pending} onClick={() => { if (current()) { selectionEpoch.current++; setSelectedIds([]); } }}>清空卡片多选</Button>
      {([['left', '左对齐'], ['center', '水平居中'], ['top', '顶端对齐'], ['distribute', '水平等距']] as const).map(([mode, label]) => <Button key={mode} disabled={!editable || selection.length < (mode === 'distribute' ? 3 : 2)} onClick={() => edit(alignCanvasCards(draftRef.current, selection, mode))}>{label}所选卡片</Button>)}
    </div>
    {props.imageOutputHandoff && <GraphImageOutputStarterPanel owner={token} disabled={!textSourceCurrent()} isCurrent={textSourceCurrent} handoff={props.imageOutputHandoff} />}
    {props.imageGraphHandoff && <details><summary>选择双参考图片输入</summary><p>沿用卡片多选；这里仅选择已保存且元数据当前的图片，不移动视口或改写布局。显示查找结果前 20 张；上方查找可缩小范围。</p>
      {(query.trim() ? matches : draft.cards).filter(row => row.asset?.kind === 'image').slice(0,20).map(row => <label key={row.id}><input type="checkbox" aria-label={`图片输入 ${row.id}`} checked={selection.includes(row.id)} disabled={!imageChoiceAvailable || states.get(row.id)?.state !== 'CURRENT_METADATA'} onChange={() => { if (imageSourceCurrent() && live.current.imageGraphHandoff?.available) selectCard(row.id,true); }} />{row.id} · {row.asset?.asset_id}</label>)}
    </details>}
    {props.imageGraphHandoff && <MediaCanvasImageGraphStarter sources={selection.length === 2 && imageSources.length === 2 ? imageSources : []} owner={token} disabled={!imageSourceCurrent()} isCurrent={imageSourceCurrent} client={props.client} read={props.read} handoff={props.imageGraphHandoff} />}
    <MediaCanvasGroupTools definition={draft} selectedCard={selected} owner={token} disabled={!editable} isCurrent={current} onChange={edit} />
    <MediaCardViewport definition={draft} states={states} selected={selected} selection={selection} query={query} owner={token} disabled={!editable} isCurrent={current} onSelect={selectCard} onChange={edit} onSize={setSize} />
    {card && <div className="creative-actions"><span>选中 {card.id}</span>{(['x', 'y'] as const).map(axis => <label key={axis}>卡片 {axis}<input type="number" value={card.position[axis]} disabled={!editable} onChange={e => edit({ ...draftRef.current, cards: draftRef.current.cards.map(c => c.id === card.id ? { ...c, position: { ...c.position, [axis]: clampGraphPosition(e.target.valueAsNumber) } } : c) })} /></label>)}
      {props.onBeginImageTask&&<Button disabled={!editable||dirty||!['image','audio','video'].includes(card.asset?.kind??'')} onClick={beginImageTask}>{card.asset?.kind==='video'?'从此卡片创建视频截取任务':card.asset?.kind==='audio'?'从此卡片创建音频截取任务':'从此卡片创建图像任务'}</Button>}
      <Button disabled={!editable} onClick={() => { edit(removeCanvasCard(draftRef.current, card.id)); setSelected(''); }}>移除此引用卡片</Button></div>}
    {card?.asset && props.graphHandoff && <MediaCanvasGraphHandoff key={`graph:${card.id}`} reference={card.asset} owner={token} client={props.client} handoff={props.graphHandoff} disabled={dirty || pending || props.externalDirty || !props.canMutate} isCurrent={current} read={props.read} />}
    {card?.asset && <CanvasAssetPreview key={card.id} reference={card.asset} owner={token} client={props.client} disabled={pending || props.busy || props.externalDirty} isCurrent={current} read={props.read} />}
    {props.canvasTask&&props.canvasTaskApproved&&props.taskProduction&&<CanvasImageTaskReturn key={props.canvasTask.id} task={props.canvasTask} approved={props.canvasTaskApproved}
      client={props.client} production={props.taskProduction} disabled={dirty||pending||props.busy||props.externalDirty} canMutate={props.canMutate} isCurrent={()=>alive.current&&live.current.active&&!live.current.denied&&live.current.isCurrent()}
      read={props.read} mutate={props.mutate} onAdopt={row=>{adopt(row);setSelected(props.canvasTask!.origin.cardId);setSelectedIds([props.canvasTask!.origin.cardId]);setNotice('已采用正式结果并回填原卡片；原素材文件、坐标和分组保留。');}}
      onUncertain={()=>{sourceEpoch.current++;dirtyRef.current=true;setUncertain(true);live.current.onDirtyChange(true);}} onComplete={()=>props.onTaskReturned?.()}/>}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <p role="status">{notice}</p>}
  </section>;
}
