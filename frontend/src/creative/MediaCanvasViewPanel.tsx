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
type Props = Pick<StudioGraphEditorProps, 'active' | 'denied' | 'identity' | 'client' | 'canMutate' | 'busy' | 'externalDirty' | 'isCurrent' | 'read' | 'mutate' | 'isBusy'> & { onDirtyChange: (dirty: boolean) => void };

/** Display metadata only; generation, media download and execution keep their original owners. */
export function MediaCanvasViewPanel(props: Props) {
  const history = useRef(emptyCanvasHistory()); const [, setHistoryRevision] = useState(0);
  const resetHistory = () => { history.current = emptyCanvasHistory(); setHistoryRevision(v => v + 1); };
  const [draft, setDraft] = useState(blank), [base, setBase] = useState<CanvasViewRecord>();
  const [rows, setRows] = useState<CanvasViewSummary[]>([]), [assets, setAssets] = useState<StudioAsset[]>([]);
  const [selectedIds, setSelectedIds] = useState<string[]>([]);
  const [selected, setSelected] = useState(''), [assetId, setAssetId] = useState(''), [query, setQuery] = useState('');
  const [pending, setPending] = useState(false), [uncertain, setUncertain] = useState(false), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [discard, setDiscard] = useState(false), [size, setSize] = useState({ width: 800, height: 480 });
  const alive = useRef(true), pendingRef = useRef(false), draftRef = useRef(draft), live = useRef(props);
  draftRef.current = draft; live.current = props;
  const dirty = uncertain || JSON.stringify(draft) !== JSON.stringify(base?.definition ?? blank());
  const client = props.client.graphs.canvasViews;
  const authority = [props.identity, props.client, props.active, props.denied, props.canMutate, props.externalDirty, base, draft, discard, selected, JSON.stringify(selectedIds)];
  const fence = useRef({ values: authority, token: {} });
  if (authority.some((value, index) => value !== fence.current.values[index])) fence.current = { values: authority, token: {} };
  const token = fence.current.token;
  const current = () => alive.current && fence.current.token === token && live.current.active && !live.current.denied && live.current.isCurrent();
  const locked = () => !current() || pendingRef.current || live.current.busy || !!live.current.isBusy?.() || live.current.externalDirty;
  const editable = !locked() && props.canMutate && !uncertain;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useEffect(() => { props.onDirtyChange(dirty); }, [dirty, props.onDirtyChange]);
  function edit(next: CanvasDefinition, recordHistory = true) {
    if (locked() || !live.current.canMutate || uncertain) return false;
    try { const valid = checkedCanvasDefinition(next); if (JSON.stringify(valid) === JSON.stringify(draftRef.current)) return false; if (recordHistory) { history.current = recordCanvasEdit(history.current, draftRef.current); setHistoryRevision(v => v + 1); } draftRef.current = valid; setDraft(valid); setDiscard(false); setNotice('尚未保存'); live.current.onDirtyChange(true); return true; }
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
  function adopt(row: CanvasViewRecord) { resetHistory(); setBase(row); setDraft(row.definition); draftRef.current = row.definition; setSelected(''); setSelectedIds([]); setUncertain(false); setDiscard(false); setNotice('已读取持久化版本'); live.current.onDirtyChange(false); }
  function open(id: string) { if (dirty && !discard) return; void work(false, () => client!.get(id), adopt); }
  const states = new Map(base?.reference_states.map(row => [row.card_id, row]) ?? []);
  const currentCardIds = new Set(draft.cards.map(card => card.id));
  const selection = selectedIds.filter(id => currentCardIds.has(id));
  function selectCard(id: string, additive = false) { if (!current() || pendingRef.current) return; setSelected(id); setSelectedIds(previous => additive ? previous.includes(id) ? previous.filter(value => value !== id) : [...previous, id] : [id]); }
  const card = draft.cards.find(c => c.id === selected);
  if (!props.active || props.denied || !client) return null;
  return <section className="media-canvas" aria-label="独立媒体素材画布" onKeyDown={event => {
      if (event.nativeEvent.isComposing || event.altKey || !(event.ctrlKey || event.metaKey) || (event.target as HTMLElement).closest('input,textarea,select,[contenteditable="true"]')) return;
      const key = event.key.toLowerCase(), redo = key === 'y' || key === 'z' && event.shiftKey;
      if (key !== 'z' && key !== 'y' || !editable || !(redo ? history.current.future.length : history.current.past.length)) return;
      event.preventDefault(); travel(redo);
    }}>
    <h3>媒体素材画布</h3><p>独立保存素材引用与位置。此视图不执行生成，也不改变执行图；选择卡片后可按需核验预览，仍复用原素材面板。</p>
    <div className="creative-actions">
      <Button disabled={!editable || !history.current.past.length} onClick={() => travel(false)}>撤销媒体画布编辑</Button>
      <Button disabled={!editable || !history.current.future.length} onClick={() => travel(true)}>重做媒体画布编辑</Button>
      <Button disabled={pending || props.busy || props.externalDirty} onClick={() => void work(false, () => client.list(), value => setRows(value.items))}>读取已存画布</Button>
      <Button disabled={!editable || draft.cards.some(c => !c.asset)} onClick={() => {
        const snapshot = draftRef.current; const requestId = `view-${crypto.randomUUID()}`;
        void work(true, () => base ? client.save(base.id, base.version, snapshot) : client.create(snapshot, requestId), row => { adopt(row); setNotice('已保存媒体画布'); });
      }}>保存媒体画布</Button>
      <Button disabled={pending || props.externalDirty || dirty && !discard} onClick={() => { if (locked() || dirty && !discard) return; const next = blank(); resetHistory(); setBase(undefined); setDraft(next); draftRef.current = next; setSelected(''); setSelectedIds([]); setUncertain(false); setDiscard(false); live.current.onDirtyChange(false); }}>新建空白视图</Button>
      <Button disabled={!editable} onClick={() => void work(false, () => props.client.assets(), value => setAssets(value.items.filter(a => ['image', 'video', 'audio'].includes(a.kind))))}>读取可用素材</Button>
    </div>
    <p>本地撤销最多 20 步、总快照不超过 2 MB；大画布可能提前淘汰旧记录。保存或重新读取后重置。快捷键 Ctrl／⌘ Z，重做 Ctrl Y 或 Shift Z；文字输入框保留自身撤销。</p>
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
    <div className="creative-actions">
      {(['x', 'y'] as const).map(axis => <label key={axis}>视口 {axis}<input type="number" min={-100000} max={100000} value={draft.viewport[axis]} disabled={!editable} onChange={e => edit({ ...draftRef.current, viewport: { ...draftRef.current.viewport, [axis]: clampGraphPosition(e.target.valueAsNumber) } })} /></label>)}
      <label>缩放<input type="number" step="0.1" min="0.35" max="2.5" value={draft.viewport.zoom} disabled={!editable} onChange={e => edit({ ...draftRef.current, viewport: { ...draftRef.current.viewport, zoom: clampGraphZoom(e.target.valueAsNumber) } })} /></label>
    </div>
    <div className="creative-actions"><span>已选 {selection.length} 张卡片</span>
      <Button disabled={!editable} onClick={() => { if (!locked()) { setSelectedIds(draft.cards.map(c => c.id)); setSelected(draft.cards[0]?.id ?? ''); } }}>选择全部卡片（含视口外）</Button>
      <Button disabled={pending} onClick={() => { if (current()) setSelectedIds([]); }}>清空卡片多选</Button>
      {([['left', '左对齐'], ['center', '水平居中'], ['top', '顶端对齐'], ['distribute', '水平等距']] as const).map(([mode, label]) => <Button key={mode} disabled={!editable || selection.length < (mode === 'distribute' ? 3 : 2)} onClick={() => edit(alignCanvasCards(draftRef.current, selection, mode))}>{label}所选卡片</Button>)}
    </div>
    <MediaCanvasGroupTools definition={draft} selectedCard={selected} owner={token} disabled={!editable} isCurrent={current} onChange={edit} />
    <MediaCardViewport definition={draft} states={states} selected={selected} selection={selection} query={query} owner={token} disabled={!editable} isCurrent={current} onSelect={selectCard} onChange={edit} onSize={setSize} />
    {card && <div className="creative-actions"><span>选中 {card.id}</span>{(['x', 'y'] as const).map(axis => <label key={axis}>卡片 {axis}<input type="number" value={card.position[axis]} disabled={!editable} onChange={e => edit({ ...draftRef.current, cards: draftRef.current.cards.map(c => c.id === card.id ? { ...c, position: { ...c.position, [axis]: clampGraphPosition(e.target.valueAsNumber) } } : c) })} /></label>)}
      <Button disabled={!editable} onClick={() => { edit(removeCanvasCard(draftRef.current, card.id)); setSelected(''); }}>移除此引用卡片</Button></div>}
    {card?.asset && <CanvasAssetPreview key={card.id} reference={card.asset} owner={token} client={props.client} disabled={pending || props.busy || props.externalDirty} isCurrent={current} read={props.read} />}
    {error && <StatusMessage tone="warning">{error}</StatusMessage>}{notice && <p role="status">{notice}</p>}
  </section>;
}
