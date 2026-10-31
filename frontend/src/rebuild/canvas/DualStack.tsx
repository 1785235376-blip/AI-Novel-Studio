// [HERMIA-FE-20261026 DUAL] 上下双画布（IMAGE / VIDEO 共用）。owner t186u：上下两个画布各管各的节点；上画布 = 主线，
// 下画布缺席/为空也完全可用；下画布 = 丰富创作，只有用户点「接入上画布」并确认，才把一个节点「复制」到上画布（快照，不联动）。
// 生成 / 执行需要的后端画布执行接口还没有 → 明写「不可用」，不假装能跑。
import {useCallback, useEffect, useMemo, useRef, useState} from 'react';
import type {PointerEvent as RPE} from 'react';
import {useStudio} from '../../store';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {Drawer} from '../primitives';
import {useScopedRequestConsent} from '../../useScopedRequestConsent';
import {RebuildCanvas, canvasStorageKey, readCanvasGraph, writeCanvasGraph, type CanvasKind, type CvGraph, type CvNode, type CvViewport} from './RebuildCanvas';
import {feedToUpper, lowerCanvasStore} from './dualStackModel';
import {ComfyCanvas} from './comfy/ComfyCanvas';
import type {CfNode, NodeDef} from './comfy/comfyRegistry';
import {readLayout, writeLayout, layoutStore, splitterKey, toggleMax, toggleSwap, topShare, withTopShare, RATIO_MIN, RATIO_MAX, type DualLayout} from './dualLayout';
import type {StudioGraphDefinitionId} from '../../creative/studioGraphTypes';
import {useLocale} from '../../i18n';
import {CanvasImageQueue} from '../image/CanvasImageQueue';
import {CanvasNodeTaskStatus} from '../image/CanvasNodeTaskStatus';
import {RebuildFormalImageNode} from '../image/RebuildFormalImageNode';
import {imageDraftNodeExists} from '../image/canvasTaskBinding';
import {ConfirmDialog} from '../../ui/ConfirmDialog';

const TXT: Record<CanvasKind, {upper: string; lower: string}> = {
  image: {upper: '上画布 · 出图主线', lower: '下画布 · 丰富创作（ComfyUI 风格节点）'},
  video: {upper: '上画布 · 镜头主线', lower: '下画布 · 丰富创作（ComfyUI 风格节点）'},
};

export function DualStack({kind, scope, seed}: {kind: CanvasKind; scope: string; seed?: CvGraph}) {
  const actorId = useStudio(s => s.actor?.id), collab = useStudio(s => s.scope), novelId = useStudio(s => s.novelId);
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: collab, projectId: novelId || scope}), [actorId, collab, novelId, scope]);
  const lower = lowerCanvasStore(kind, identity);
  const session = lower.persist === 'session';
  const {scopeKey: canvasTaskScope} = useScopedRequestConsent([]);
  const [canvasTask, setCanvasTask] = useState<{scope: string; novelId: string; nodeId: string; prompt: string; isSourceCurrent?: () => boolean}>();
  const openCanvasTask = (node: CvNode, isSourceCurrent?: () => boolean) => {
    if (kind !== 'image') return;
    if ((!isSourceCurrent || isSourceCurrent()) && imageDraftNodeExists(scope, node.id) && node.t === 'image_generate') {
      setCanvasTask({scope: canvasTaskScope, novelId: scope, nodeId: node.id, prompt: node.prompt?.trim() || '', isSourceCurrent});
    }
  };
  const renderCanvasTask = (node: CvNode, isSourceCurrent?: () => boolean, sourceRevision?: number, formalSourceCurrent?: () => boolean) => kind === 'image' ? <>
    <CanvasNodeTaskStatus novelId={scope} nodeId={node.id} nodePrompt={node.prompt || ''} sourceRevision={sourceRevision} isSourceCurrent={isSourceCurrent} onOpen={() => openCanvasTask(node, isSourceCurrent)}/>
    <RebuildFormalImageNode projectId={scope} node={node} sourceRevision={sourceRevision} isSourceCurrent={formalSourceCurrent}/>
  </> : <span data-unsupported="non-image">此节点类型不支持正式图片任务</span>;
  useEffect(() => setCanvasTask(undefined), [scope, canvasTaskScope, kind]);
  const canvasTaskDrawer = kind === 'image' && canvasTask?.scope === canvasTaskScope && canvasTask.novelId === scope ? <Drawer title="画布图片任务" onClose={() => setCanvasTask(undefined)}>
    <CanvasImageQueue novelId={scope} nodeId={canvasTask.nodeId} prompt={canvasTask.prompt} isSourceCurrent={canvasTask.isSourceCurrent} onClose={() => setCanvasTask(undefined)}/>
  </Drawer> : null;
  const [lowerOpen, setLowerOpen] = useState(true);
  const [picked, setPicked] = useState<{n: CfNode; d: NodeDef | null} | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [rev, setRev] = useState(0);
  const [note, setNote] = useState('');
  const upperVp = useRef<CvViewport | undefined>(undefined);
  const [upperInit, setUpperInit] = useState<{sel?: string; reveal?: boolean}>({});
  const onUpperVp = useCallback((v: CvViewport) => { upperVp.current = v; }, []);
  const onLowerSel = useCallback((n: CfNode | null, d: NodeDef | null) => { setPicked(n ? {n, d} : null); if (!n) setConfirm(false); }, []);
  const feedable = !!picked?.d?.feedAs;
  // [HERMIA-FE-20261031 DUALCANVAS-COMFY] layout: ratio / swap / maximise, per identity (no identity → this session only)
  const locale = useLocale(); const zh = locale.startsWith('zh'); const L = (a: string, b: string) => (zh ? a : b);
  const lstore = useMemo(() => layoutStore(kind, identity), [kind, identity]);
  const [layout, setLayoutState] = useState<DualLayout>(() => readLayout(lstore));
  useEffect(() => { setLayoutState(readLayout(lstore)); }, [lstore]);
  const setLayout = useCallback((f: (l: DualLayout) => DualLayout) => setLayoutState(l => { const n = f(l); writeLayout(lstore, n); return n; }), [lstore]);
  const panesRef = useRef<HTMLDivElement>(null);
  const dragSplit = useRef(false);
  const onSplitDown = (e: RPE<HTMLDivElement>) => { dragSplit.current = true; (e.currentTarget as Element).setPointerCapture?.(e.pointerId); };
  const onSplitMove = (e: RPE<HTMLDivElement>) => {
    if (!dragSplit.current) return; const r = panesRef.current?.getBoundingClientRect(); if (!r || !r.height) return;
    const share = (e.clientY - r.top) / r.height; setLayout(l => withTopShare(l, share));
  };
  const onSplitUp = () => { dragSplit.current = false; };
  const doFeed = () => {
    if (!picked?.d?.feedAs) return;
    const node: CvNode = {id: picked.n.id, t: picked.d.feedAs as StudioGraphDefinitionId, x: picked.n.x, y: picked.n.y, title: picked.n.title};
    const key = canvasStorageKey(kind, scope);
    const cur = readCanvasGraph(key) ?? seed ?? {nodes: [], edges: []};
    const {graph, id} = feedToUpper(cur, node);
    writeCanvasGraph(key, graph);
    setUpperInit({sel: id, reveal: true}); setRev(r => r + 1); setConfirm(false);
    setNote(`已把「${picked.n.title}」复制到上画布（快照，之后两边各改各的）`);
  };
  const t = TXT[kind];
  return (
    <section className="dstk" data-dual-stack={kind} aria-label={kind === 'image' ? '图片双画布' : '视频双画布'}>
      <div className="dstk__bar">
        <strong>双画布</strong>
        <span className="dstk__hint">上画布是主线，单独就能用；下画布用来丰富创作，<b>不会自动</b>影响上画布。</span>
        <span className={`dstk__id${lstore.persist === 'session' ? ' is-session' : ''}`} data-layout-identity={lstore.persist}
          title={L('窗口比例 / 互换 / 最大化的记忆范围', 'Where the window layout is remembered')}>{lstore.persist === 'session' ? L('布局：仅本次会话', 'Layout: this session only') : L('布局按账号与作品记住', 'Layout remembered per account & project')}</span>
        <span className={`dstk__id${session ? ' is-session' : ''}`} data-identity={session ? 'session' : 'real'}
          title={session ? '没有登录身份或作品范围，下画布只存在这次会话里，刷新即丢' : '下画布按账号 + 作品保存在本机浏览器'}>{session ? '仅本次会话' : '下画布按账号与作品保存（本机）'}</span>
        {kind === 'image'
          ? <span className="dstk__hint" data-formal-image="upper">上画布选中「生成图片」节点后可走正式预览→确认→创建→执行→审阅采用（不自动执行/采用）</span>
          : <span className="dstk__off" data-unsupported="video-run" data-unavailable="canvas-run" title="VIDEO 正式节点执行未接线">VIDEO 正式生成 / 执行：unsupported · 不可用</span>}
        <button type="button" className="nv-btn" aria-expanded={lowerOpen} aria-controls={`dstk-lower-${kind}`} onClick={() => setLowerOpen(o => !o)}>{lowerOpen ? '收起下画布' : '展开下画布'}</button>
      </div>
      {(() => {
        const showLower = lowerOpen && layout.max !== 'upper';
        const showUpper = layout.max !== 'lower' || !lowerOpen;
        const both = showLower && showUpper;
        const top = Math.round(topShare(layout) * 100);
        const upperFlex = both ? (layout.ratio) : 1, lowerFlex = both ? 1 - layout.ratio : 1;
        const paneTools = (which: 'upper' | 'lower') => <span className="dstk__tools" role="group" aria-label={which === 'upper' ? L('上画布窗口', 'Main canvas window') : L('下画布窗口', 'Rich canvas window')}>
          <button type="button" className="dstk__tb" data-pane-max={which} aria-pressed={layout.max === which}
            onClick={() => { if (which === 'lower') setLowerOpen(true); setLayout(l => toggleMax(l, which)); }}>
            {layout.max === which ? L('还原', 'Restore') : L('最大化', 'Maximize')}</button>
          <button type="button" className="dstk__tb" data-pane-swap aria-pressed={layout.swapped} disabled={!both}
            title={L('只交换显示位置：上画布仍是主线，下画布仍是丰富创作', 'Swaps position only; roles and data stay the same')}
            onClick={() => setLayout(toggleSwap)}>{L('上下互换', 'Swap')}</button>
        </span>;
        return <div ref={panesRef} className={`dstk__panes dstk__panes--flex${lowerOpen ? '' : ' is-collapsed'}${layout.swapped ? ' is-swapped' : ''}`}
          data-layout-swapped={layout.swapped} data-layout-max={layout.max} data-layout-persist={lstore.persist}>
        <div className="dstk__pane dstk__pane--upper" data-canvas-layer="upper" hidden={!showUpper} style={{order: layout.swapped ? 3 : 1, flex: `${upperFlex} 1 0`}}>
          <div className="dstk__panehead"><span>{L('主线', 'Main')}</span>{lowerOpen ? paneTools('upper') : null}</div>
          <RebuildCanvas key={`u${rev}`} kind={kind} scope={scope} seed={seed} label={t.upper} ariaLabel={`${t.upper}（无限画布）`}
            initialViewport={upperVp.current} onViewport={onUpperVp} initialSelected={upperInit.sel} revealLast={upperInit.reveal}
            onRevealed={() => setUpperInit(u => ({...u, reveal: false}))}
            onImageTaskIntent={kind === 'image' ? openCanvasTask : undefined}
            renderImageTaskBinding={kind === 'image' ? renderCanvasTask : undefined} />
        </div>
        {both ? <div className="dstk__split" role="separator" aria-orientation="horizontal" tabIndex={0} data-dual-splitter
          aria-label={L('调整上下画布高度（方向键 / PageUp / PageDown / Home / End，回车恢复默认）', 'Resize canvases (arrows / PageUp / PageDown / Home / End, Enter resets)')}
          aria-valuemin={Math.round(RATIO_MIN * 100)} aria-valuemax={Math.round(RATIO_MAX * 100)} aria-valuenow={top} aria-valuetext={L(`上方 ${top}%`, `top ${top}%`)}
          aria-controls={`dstk-lower-${kind}`} style={{order: 2}}
          onKeyDown={e => { const n = splitterKey(layout, e.key); if (n) { e.preventDefault(); setLayout(() => n); } }}
          onPointerDown={onSplitDown} onPointerMove={onSplitMove} onPointerUp={onSplitUp} onPointerCancel={onSplitUp}><span /></div> : null}
        {lowerOpen ? <div className="dstk__pane dstk__pane--lower" data-canvas-layer="lower" id={`dstk-lower-${kind}`} hidden={!showLower} style={{order: layout.swapped ? 1 : 3, flex: `${lowerFlex} 1 0`}}>
          <div className="dstk__lowbar">
            <span className="dstk__panehead dstk__panehead--inline">{L('丰富创作', 'Rich')}</span>
            <span>{picked ? <>已选：<b>{picked.n.title}</b>{feedable ? null : <> · <span data-feed-hint>{L('这个节点只在下画布用，不能接入上画布', 'This node stays on the lower canvas')}</span></>}</> : '在下画布选一个节点，才可以接入上画布'}</span>
            {/* [HERMIA-FE-20261030 B1] 确认条 → 模态对话框（焦点进入/圈住/Esc 取消/还给触发按钮） */}
            <button type="button" className="nv-btn" data-feed-upper disabled={!feedable} aria-haspopup="dialog" onClick={() => setConfirm(true)}>接入上画布…</button>
            {confirm && picked ? <ConfirmDialog title="接入上画布？" confirmLabel="确认接入" cancelLabel="取消" confirmData={{'data-feed-confirm': ''}}
              onConfirm={doFeed} onCancel={() => setConfirm(false)}>
              <p>把「{picked.n.title}」复制一份到上画布。复制后两边各改各的，不会联动。</p>
            </ConfirmDialog> : null}
            {note ? <span className="dstk__note" role="status">{note}</span> : null}
            {paneTools('lower')}
          </div>
          <ComfyCanvas key={lower.key} kind={kind} storageKey={lower.key} persist={lower.persist}
            label={t.lower} ariaLabel={`${t.lower}（无限画布）`} onSelect={onLowerSel}
            badge={session ? L('仅本次会话 · 不会执行', 'This session only · never runs') : L('仅本机草稿 · 不会执行 · 未连接 ComfyUI', 'Local draft · never runs · ComfyUI not connected')}
            badgeTitle={L('后端还没有下画布执行 / 保存 / ComfyUI 代理接口：这里只编辑本地节点结构，不执行、不计费、不调用模型', 'No backend execute/save/ComfyUI proxy yet: local structure only, nothing runs or is billed')}
            emptyHint="下画布是空的也没关系，上画布照常可用" />
        </div> : null}
      </div>;
      })()}
      {canvasTaskDrawer}
    </section>
  );
}
