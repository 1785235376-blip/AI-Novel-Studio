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
import {nodeLabel, type CfNode, type NodeDef} from './comfy/comfyRegistry';
import {readLayout, writeLayout, layoutStore, splitterKey, toggleMax, toggleSwap, topShare, withTopShare, RATIO_MIN, RATIO_MAX, type DualLayout} from './dualLayout';
import type {StudioGraphDefinitionId} from '../../creative/studioGraphTypes';
import {useLocale, useT, type Locale} from '../../i18n';
import type {MessageKey} from '../../i18n/zh-CN';
import {displayNodeTitle} from '../../i18n/defaultNodeTitle';
import {CanvasImageQueue} from '../image/CanvasImageQueue';
import {CanvasNodeTaskStatus} from '../image/CanvasNodeTaskStatus';
import {RebuildFormalImageNode} from '../image/RebuildFormalImageNode';
import {imageDraftNodeExists} from '../image/canvasTaskBinding';
import {ConfirmDialog} from '../../ui/ConfirmDialog';

// [HERMIA-FE-20261031 DUALCANVAS-COMFY P2-1] 所有双画布文案走 i18n 词典（zh 输出不变）。
const TXT: Record<CanvasKind, {upper: MessageKey; lower: MessageKey}> = {
  image: {upper: 'dual.upper.image', lower: 'dual.lower'},
  video: {upper: 'dual.upper.video', lower: 'dual.lower'},
};
/** 下画布节点标题：仍是默认（中文注册名）时按当前语言显示；用户改过的标题原样显示。存储值不变。 */
export function displayLowerTitle(n: CfNode, d: NodeDef | null, locale: Locale): string {
  return d && n.title === nodeLabel(d, 'zh-CN') ? nodeLabel(d, locale) : displayNodeTitle(locale, n.title);
}

export function DualStack({kind, scope, seed}: {kind: CanvasKind; scope: string; seed?: CvGraph}) {
  const actorId = useStudio(s => s.actor?.id), collab = useStudio(s => s.scope), novelId = useStudio(s => s.novelId);
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: collab, projectId: novelId || scope}), [actorId, collab, novelId, scope]);
  const lower = lowerCanvasStore(kind, identity);
  const tr = useT();
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
  </> : <span data-unsupported="non-image">{tr('dual.task.unsupported')}</span>;
  useEffect(() => setCanvasTask(undefined), [scope, canvasTaskScope, kind]);
  const canvasTaskDrawer = kind === 'image' && canvasTask?.scope === canvasTaskScope && canvasTask.novelId === scope ? <Drawer title={tr('dual.task.drawer')} onClose={() => setCanvasTask(undefined)}>
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
  const locale = useLocale();
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
    setNote(tr('dual.feed.done', {title: displayLowerTitle(picked.n, picked.d, locale)}));
  };
  const t = {upper: tr(TXT[kind].upper), lower: tr(TXT[kind].lower)};
  const pickedTitle = picked ? displayLowerTitle(picked.n, picked.d, locale) : '';
  return (
    <section className="dstk" data-dual-stack={kind} aria-label={tr(kind === 'image' ? 'dual.aria.image' : 'dual.aria.video')}>
      <div className="dstk__bar">
        <strong>{tr('dual.title')}</strong>
        <span className="dstk__hint">{tr('dual.hint')}<b>{tr('dual.hint.b')}</b>{tr('dual.hint.c')}</span>
        <span className={`dstk__id${lstore.persist === 'session' ? ' is-session' : ''}`} data-layout-identity={lstore.persist}
          title={tr('dual.layout.title')}>{tr(lstore.persist === 'session' ? 'dual.layout.session' : 'dual.layout.real')}</span>
        <span className={`dstk__id${session ? ' is-session' : ''}`} data-identity={session ? 'session' : 'real'}
          title={tr(session ? 'dual.lower.session.title' : 'dual.lower.real.title')}>{tr(session ? 'dual.lower.session' : 'dual.lower.real')}</span>
        {kind === 'image'
          ? <span className="dstk__hint" data-formal-image="upper">{tr('dual.formal.image')}</span>
          : <span className="dstk__off" data-unsupported="video-run" data-unavailable="canvas-run" title={tr('dual.video.off.title')}>{tr('dual.video.off')}</span>}
        <button type="button" className="nv-btn" aria-expanded={lowerOpen} aria-controls={`dstk-lower-${kind}`} onClick={() => setLowerOpen(o => !o)}>{tr(lowerOpen ? 'dual.lower.collapse' : 'dual.lower.expand')}</button>
      </div>
      {(() => {
        const showLower = lowerOpen && layout.max !== 'upper';
        const showUpper = layout.max !== 'lower' || !lowerOpen;
        const both = showLower && showUpper;
        const top = Math.round(topShare(layout) * 100);
        const upperFlex = both ? (layout.ratio) : 1, lowerFlex = both ? 1 - layout.ratio : 1;
        const paneTools = (which: 'upper' | 'lower') => <span className="dstk__tools" role="group" aria-label={tr(which === 'upper' ? 'dual.win.upper' : 'dual.win.lower')}>
          <button type="button" className="dstk__tb" data-pane-max={which} aria-pressed={layout.max === which}
            onClick={() => { if (which === 'lower') setLowerOpen(true); setLayout(l => toggleMax(l, which)); }}>
            {tr(layout.max === which ? 'dual.restore' : 'dual.maximize')}</button>
          <button type="button" className="dstk__tb" data-pane-swap aria-pressed={layout.swapped} disabled={!both}
            title={tr('dual.swap.title')}
            onClick={() => setLayout(toggleSwap)}>{tr('dual.swap')}</button>
        </span>;
        return <div ref={panesRef} className={`dstk__panes dstk__panes--flex${lowerOpen ? '' : ' is-collapsed'}${layout.swapped ? ' is-swapped' : ''}`}
          data-layout-swapped={layout.swapped} data-layout-max={layout.max} data-layout-persist={lstore.persist}>
        <div className="dstk__pane dstk__pane--upper" data-canvas-layer="upper" hidden={!showUpper} style={{order: layout.swapped ? 3 : 1, flex: `${upperFlex} 1 0`}}>
          <div className="dstk__panehead"><span>{tr('dual.pane.main')}</span>{lowerOpen ? paneTools('upper') : null}</div>
          <RebuildCanvas key={`u${rev}`} kind={kind} scope={scope} seed={seed} label={t.upper} ariaLabel={tr('dual.infinite', {label: t.upper})}
            initialViewport={upperVp.current} onViewport={onUpperVp} initialSelected={upperInit.sel} revealLast={upperInit.reveal}
            onRevealed={() => setUpperInit(u => ({...u, reveal: false}))}
            onImageTaskIntent={kind === 'image' ? openCanvasTask : undefined}
            renderImageTaskBinding={kind === 'image' ? renderCanvasTask : undefined} />
        </div>
        {both ? <div className="dstk__split" role="separator" aria-orientation="horizontal" tabIndex={0} data-dual-splitter
          aria-label={tr('dual.split.aria')}
          aria-valuemin={Math.round(RATIO_MIN * 100)} aria-valuemax={Math.round(RATIO_MAX * 100)} aria-valuenow={top} aria-valuetext={tr('dual.split.value', {pct: top})}
          aria-controls={`dstk-lower-${kind}`} style={{order: 2}}
          onKeyDown={e => { const n = splitterKey(layout, e.key); if (n) { e.preventDefault(); setLayout(() => n); } }}
          onPointerDown={onSplitDown} onPointerMove={onSplitMove} onPointerUp={onSplitUp} onPointerCancel={onSplitUp}><span /></div> : null}
        {lowerOpen ? <div className="dstk__pane dstk__pane--lower" data-canvas-layer="lower" id={`dstk-lower-${kind}`} hidden={!showLower} style={{order: layout.swapped ? 1 : 3, flex: `${lowerFlex} 1 0`}}>
          <div className="dstk__lowbar">
            <span className="dstk__panehead dstk__panehead--inline">{tr('dual.pane.rich')}</span>
            <span>{picked ? <>{tr('dual.picked')}<b>{pickedTitle}</b>{feedable ? null : <> · <span data-feed-hint>{tr('dual.feed.only')}</span></>}</> : tr('dual.pick.hint')}</span>
            {/* [HERMIA-FE-20261030 B1] 确认条 → 模态对话框（焦点进入/圈住/Esc 取消/还给触发按钮） */}
            <button type="button" className="nv-btn" data-feed-upper disabled={!feedable} aria-haspopup="dialog" onClick={() => setConfirm(true)}>{tr('dual.feed.btn')}</button>
            {confirm && picked ? <ConfirmDialog title={tr('dual.feed.dlg')} confirmLabel={tr('dual.feed.ok')} cancelLabel={tr('dual.feed.cancel')} confirmData={{'data-feed-confirm': ''}}
              onConfirm={doFeed} onCancel={() => setConfirm(false)}>
              <p>{tr('dual.feed.body', {title: pickedTitle})}</p>
            </ConfirmDialog> : null}
            {note ? <span className="dstk__note" role="status">{note}</span> : null}
            {paneTools('lower')}
          </div>
          <ComfyCanvas key={lower.key} kind={kind} storageKey={lower.key} persist={lower.persist}
            label={t.lower} ariaLabel={tr('dual.infinite', {label: t.lower})} onSelect={onLowerSel}
            badge={tr(session ? 'dual.badge.session' : 'dual.badge.real')}
            badgeTitle={tr('dual.badge.title')}
            emptyHint={tr('dual.empty')} />
        </div> : null}
      </div>;
      })()}
      {canvasTaskDrawer}
    </section>
  );
}
