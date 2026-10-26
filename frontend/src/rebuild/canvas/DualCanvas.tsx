// [HERMIA-FE-20261022 U2] 双画布：原型「编排 · 创作画布 / 执行画布 / 对照分屏」与旧 creative/useStudioDualCanvasTask 的同一概念。
// 创作画布 = 图片画布（参考、提示词、风格、出图）；执行画布 = 视频画布（镜头、导演备注、生成视频、送剪辑）。
// 对照分屏左右并排；选中创作画布节点可「送到执行画布」，在执行画布生成一个引用节点。仍是本机草稿，不写服务端。
import {useCallback, useState, type ReactNode} from 'react';
import {RebuildCanvas, canvasStorageKey, type CvNode, type CvGraph} from './RebuildCanvas';

type Mode = 'creation' | 'execution' | 'split';
/** [HERMIA-FE-20261024 M2-s1fix] world position of sent reference nodes (inside the default execution viewport). */
export const LINK_X = 20, LINK_Y0 = 20, LINK_DY = 70, LINK_DX = 206; // DX = rendered node width 186 + 20 gap
export function linkToExecution(scope: string, n: CvNode): void {
  const key = canvasStorageKey('video', scope);
  let g: CvGraph = {nodes: [], edges: []};
  try { const raw = localStorage.getItem(key); if (raw) g = JSON.parse(raw); } catch { /* ignore */ }
  // [HERMIA-FE-20261024 M2-s1fix] was x:-220 (off-view: the execution canvas remounts at viewport {x:40,y:40,k:1}, so the
  // node showed only ~5px). Place it inside that default view: screen x 60..240, y 60..260 — fits the 320×280 panel minimum.
  // [HERMIA-FE-20261024 M2-s1fix2] grid instead of n%3 (4th node fully covered the 1st): column = floor(n/3), so the
  // first column (first 3 sends) stays inside the default view and later sends never overlap earlier ones.
  const i = g.nodes.length;
  const x = LINK_X + Math.floor(i / 3) * LINK_DX, y = LINK_Y0 + (i % 3) * LINK_DY;
  g.nodes = [...g.nodes, {id: `ref-${n.id}-${Date.now().toString(36)}`, t: 'image_reference', x, y, title: `参考 · ${n.title}`}];
  try { localStorage.setItem(key, JSON.stringify(g)); } catch { /* ignore */ }
}

type DualCanvasProps = {scope: string; initial?: Mode; videoSeed?: CvGraph;
  onImageTaskIntent?: (node: CvNode, isSourceCurrent?: () => boolean) => void; renderImageTaskBinding?: (node: CvNode, isSourceCurrent?: () => boolean, sourceRevision?: number, formalSourceCurrent?: () => boolean) => ReactNode};
export function DualCanvas(props: DualCanvasProps) {
  return <DualCanvasSession key={props.scope} {...props} />;
}

function DualCanvasSession({scope, initial = 'split', videoSeed, onImageTaskIntent, renderImageTaskBinding}: DualCanvasProps) {
  const [mode, setMode] = useState<Mode>(initial);
  const [sel, setSel] = useState<CvNode | null>(null);
  const [rev, setRev] = useState(0);
  const [note, setNote] = useState('');
  const onSel = useCallback((n: CvNode | null) => setSel(n), []);
  const send = () => { if (!sel) return; linkToExecution(scope, sel); setRev(r => r + 1); setNote(`已在执行画布加入「参考 · ${sel.title}」（本机草稿）`); if (mode === 'creation') setMode('split'); };
  return (
    <section className="dual-cv" data-dual-mode={mode} aria-label="双画布">
      <div className="dual-cv__bar" role="toolbar" aria-label="双画布模式">
        <div className="dual-cv__seg">
          {([['creation', '创作画布'], ['execution', '执行画布'], ['split', '对照分屏']] as [Mode, string][]).map(([m, l]) =>
            <button key={m} type="button" aria-pressed={mode === m} data-dual={m} onClick={() => setMode(m)}>{l}</button>)}
        </div>
        <span className="dual-cv__hint">左边组织素材和画面（图片），右边排镜头和生成（视频）。图片任务需另行确认；视频节点尚未接入执行。</span>
        <span className="nv-spacer" />
        {note ? <span className="dual-cv__note" role="status">{note}</span> : null}
        <button type="button" className="nv-btn" data-dual-link="true" disabled={!sel || mode === 'execution'} title={sel ? '' : '先在创作画布选中一个节点'} onClick={send}>
          {sel ? `送「${sel.title.slice(0, 10)}」到执行画布 →` : '选中创作节点后可送到执行画布'}</button>
      </div>
      <div className="dual-cv__panes">
        {mode !== 'execution' ? <div className="dual-cv__pane" aria-label="创作画布"><div className="dual-cv__lab">创作画布 · 图片</div><RebuildCanvas kind="image" scope={scope} label="创作画布" onSelect={onSel} onImageTaskIntent={onImageTaskIntent} renderImageTaskBinding={renderImageTaskBinding} /></div> : null}
        {mode !== 'creation' ? <div className="dual-cv__pane" aria-label="执行画布"><div className="dual-cv__lab">执行画布 · 视频镜头</div><RebuildCanvas key={rev} kind="video" scope={scope} label="执行画布" seed={videoSeed} /></div> : null}
      </div>
    </section>
  );
}
