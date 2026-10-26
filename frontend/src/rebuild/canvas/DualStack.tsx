// [HERMIA-FE-20261026 DUAL] 上下双画布（IMAGE / VIDEO 共用）。owner t186u：上下两个画布各管各的节点；上画布 = 主线，
// 下画布缺席/为空也完全可用；下画布 = 丰富创作，只有用户点「接入上画布」并确认，才把一个节点「复制」到上画布（快照，不联动）。
// 生成 / 执行需要的后端画布执行接口还没有 → 明写「不可用」，不假装能跑。
import {useCallback, useMemo, useRef, useState} from 'react';
import {useStudio} from '../../store';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {RebuildCanvas, canvasStorageKey, readCanvasGraph, writeCanvasGraph, type CanvasKind, type CvGraph, type CvNode, type CvViewport} from './RebuildCanvas';
import {LOWER_TYPES, feedToUpper, lowerCanvasStore} from './dualStackModel';

const TXT: Record<CanvasKind, {upper: string; lower: string}> = {
  image: {upper: '上画布 · 出图主线', lower: '下画布 · 丰富（参考 / 风格 / 变体 / 细节）'},
  video: {upper: '上画布 · 镜头主线', lower: '下画布 · 丰富（参考 / 导演风格 / 变体 / 细节）'},
};

export function DualStack({kind, scope, seed}: {kind: CanvasKind; scope: string; seed?: CvGraph}) {
  const actorId = useStudio(s => s.actor?.id), collab = useStudio(s => s.scope), novelId = useStudio(s => s.novelId);
  const identity = useMemo(() => resolveWorkspaceIdentity({actorId, collabScope: collab, projectId: novelId || scope}), [actorId, collab, novelId, scope]);
  const lower = lowerCanvasStore(kind, identity);
  const session = lower.persist === 'session';
  const [lowerOpen, setLowerOpen] = useState(true);
  const [picked, setPicked] = useState<CvNode | null>(null);
  const [confirm, setConfirm] = useState(false);
  const [rev, setRev] = useState(0);
  const [note, setNote] = useState('');
  const upperVp = useRef<CvViewport | undefined>(undefined);
  const [upperInit, setUpperInit] = useState<{sel?: string; reveal?: boolean}>({});
  const onUpperVp = useCallback((v: CvViewport) => { upperVp.current = v; }, []);
  const onLowerSel = useCallback((n: CvNode | null) => { setPicked(n); if (!n) setConfirm(false); }, []);
  const doFeed = () => {
    if (!picked) return;
    const key = canvasStorageKey(kind, scope);
    const cur = readCanvasGraph(key) ?? seed ?? {nodes: [], edges: []};
    const {graph, id} = feedToUpper(cur, picked);
    writeCanvasGraph(key, graph);
    setUpperInit({sel: id, reveal: true}); setRev(r => r + 1); setConfirm(false);
    setNote(`已把「${picked.title}」复制到上画布（快照，之后两边各改各的）`);
  };
  const t = TXT[kind];
  return (
    <section className="dstk" data-dual-stack={kind} aria-label={kind === 'image' ? '图片双画布' : '视频双画布'}>
      <div className="dstk__bar">
        <strong>双画布</strong>
        <span className="dstk__hint">上画布是主线，单独就能用；下画布用来丰富创作，<b>不会自动</b>影响上画布。</span>
        <span className={`dstk__id${session ? ' is-session' : ''}`} data-identity={session ? 'session' : 'real'}
          title={session ? '没有登录身份或作品范围，下画布只存在这次会话里，刷新即丢' : '下画布按账号 + 作品保存在本机浏览器'}>{session ? '仅本次会话' : '下画布按账号与作品保存（本机）'}</span>
        <span className="dstk__off" data-unavailable="canvas-run" title="后端还没有画布图执行接口">生成 / 执行：不可用（后端暂无画布执行接口）</span>
        <button type="button" className="nv-btn" aria-expanded={lowerOpen} aria-controls={`dstk-lower-${kind}`} onClick={() => setLowerOpen(o => !o)}>{lowerOpen ? '收起下画布' : '展开下画布'}</button>
      </div>
      <div className={`dstk__panes${lowerOpen ? '' : ' is-collapsed'}`}>
        <div className="dstk__pane dstk__pane--upper" data-canvas-layer="upper">
          <RebuildCanvas key={`u${rev}`} kind={kind} scope={scope} seed={seed} label={t.upper} ariaLabel={`${t.upper}（无限画布）`}
            initialViewport={upperVp.current} onViewport={onUpperVp} initialSelected={upperInit.sel} revealLast={upperInit.reveal}
            onRevealed={() => setUpperInit(u => ({...u, reveal: false}))} />
        </div>
        {lowerOpen ? <div className="dstk__pane dstk__pane--lower" data-canvas-layer="lower" id={`dstk-lower-${kind}`}>
          <div className="dstk__lowbar">
            <span>{picked ? <>已选：<b>{picked.title}</b></> : '在下画布选一个节点，才可以接入上画布'}</span>
            {confirm && picked ? <span className="dstk__confirm" role="group" aria-label="确认接入上画布">
              复制「{picked.title}」到上画布？复制后不联动。
              <button type="button" className="nv-btn nv-btn--primary" data-feed-confirm onClick={doFeed}>确认接入</button>
              <button type="button" className="nv-btn" onClick={() => setConfirm(false)}>取消</button>
            </span> : <button type="button" className="nv-btn" data-feed-upper disabled={!picked} onClick={() => setConfirm(true)}>接入上画布…</button>}
            {note ? <span className="dstk__note" role="status">{note}</span> : null}
          </div>
          <RebuildCanvas key={lower.key} kind={kind} scope={scope} storageKey={lower.key} persist={lower.persist} types={LOWER_TYPES[kind]}
            label={t.lower} ariaLabel={`${t.lower}（无限画布）`} onSelect={onLowerSel} menuTitle="添加到下画布（丰富，不会自动接入）"
            badge={session ? '仅本次会话 · 不保存' : '仅本机草稿 · 未同步服务端'} emptyHint="下画布是空的也没关系，上画布照常可用" />
        </div> : null}
      </div>
    </section>
  );
}
