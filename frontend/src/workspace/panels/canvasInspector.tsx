// [HERMIA-FE-20261024 M3-s1] Canvas-node inspector for ?uw=1 (dual canvas ↔ inspector linkage).
// The two RebuildCanvas instances only persist to their own localStorage key (canvasStorageKey(kind, scope)); there is
// no server canvas-graph API wired to them yet. Edits therefore go through ONE registry action that writes that same
// local draft and reads it back; success is only reported when the read-back matches. No network, no model calls.
import {useEffect, useRef, useState} from 'react';
import type {ActionContext, ActionRegistry} from '../../workbench/actions';
import {canvasStorageKey, NODE_TYPES, type CanvasKind, type CvGraph, type CvNode} from '../../rebuild/canvas/RebuildCanvas';
import type {PanelRenderApi} from '../layout/DockLayout';
import {DraftStore, nodeDraftKey, useDraft} from '../state/draftStore'; // [HERMIA-FE-20261024 M5-s1]

export const CANVAS_NODE_ACTION_ID = 'uw.canvas.renameNode';
export type CanvasPick = {kind: CanvasKind; id: string};
export type RenameNodeInput = {kind: CanvasKind; scope: string; id: string; title: string};
export const CANVAS_LABEL: Record<CanvasKind, string> = {image: '创作画布', video: '执行画布'};

function readGraph(kind: CanvasKind, scope: string): CvGraph | null {
  try { const g = JSON.parse(localStorage.getItem(canvasStorageKey(kind, scope)) || 'null'); return Array.isArray(g?.nodes) && Array.isArray(g?.edges) ? g : null; } catch { return null; }
}
export function readCanvasNode(kind: CanvasKind, scope: string, id: string): {node: CvNode; ins: number; outs: number} | null {
  const g = readGraph(kind, scope); const node = g?.nodes.find(n => n.id === id);
  return g && node ? {node, ins: g.edges.filter(e => e.b === id).length, outs: g.edges.filter(e => e.a === id).length} : null;
}

/** Writes the title into the canvas's own local draft and verifies by read-back. Throws on any mismatch. */
export function renameCanvasNode({kind, scope, id, title}: RenameNodeInput): CvNode {
  const t = title.trim(); if (!t) throw new Error('标题不能为空。');
  const g = readGraph(kind, scope); if (!g) throw new Error('读不到这块画布的本机草稿。');
  if (!g.nodes.some(n => n.id === id)) throw new Error('节点已不存在（可能已被删除）。');
  try { localStorage.setItem(canvasStorageKey(kind, scope), JSON.stringify({...g, nodes: g.nodes.map(n => n.id === id ? {...n, title: t} : n)})); }
  catch { throw new Error('写入本机草稿失败（浏览器存储不可用或已满）。'); }
  const back = readCanvasNode(kind, scope, id)?.node;
  if (!back || back.title !== t) throw new Error('写入后读回不一致，未保存。');
  return back;
}

export function registerCanvasNodeActions(actions: ActionRegistry): () => void {
  return actions.register({
    id: CANVAS_NODE_ACTION_ID, label: '重命名画布节点（本机草稿）', surfaces: [],
    run: async (c: ActionContext) => renameCanvasNode(c.input as RenameNodeInput),
  });
}

export function CanvasNodeInspector({pick, scope, actions, ctx, api, dirtyRef, onSaved, onBack, onSettled, drafts}: {
  pick: CanvasPick; scope: string; actions: ActionRegistry; ctx: (input?: unknown) => ActionContext; api: PanelRenderApi;
  dirtyRef: {current: boolean}; onSaved: (kind: CanvasKind) => void; onBack: () => void; onSettled?: () => void; drafts?: DraftStore;
}) {
  const info = readCanvasNode(pick.kind, scope, pick.id);
  // [HERMIA-FE-20261024 M5-s1] draft lives in the host store (keyed scope+canvas+node) so redock/tab switch keeps it.
  const localDrafts = useRef<DraftStore | null>(null);
  const store = drafts ?? (localDrafts.current ??= new DraftStore());
  const [stored, setStored] = useDraft(store, nodeDraftKey(scope, pick.kind, pick.id));
  const draft = stored ? stored.value : null;
  const setDraft = (v: string | null) => setStored(v === null ? null : {value: v, base: stored?.base ?? info?.node.title ?? ''});
  const [msg, setMsg] = useState<{kind: 'ok' | 'err'; text: string} | null>(null);
  const [saving, setSaving] = useState(false);
  useEffect(() => { setMsg(null); }, [pick.kind, pick.id, scope]);
  const dirty = draft !== null && !!info && draft !== info.node.title;
  dirtyRef.current = dirty;
  useEffect(() => () => { dirtyRef.current = false; }, [dirtyRef]);
  const live = useRef({draft, pick, scope}); live.current = {draft, pick, scope};
  const save = async () => {
    const {draft: d, pick: p, scope: s} = live.current; if (d === null) return;
    setSaving(true); setMsg(null);
    try {
      const r = await actions.execute(CANVAS_NODE_ACTION_ID, ctx({kind: p.kind, scope: s, id: p.id, title: d} satisfies RenameNodeInput));
      if (r.status !== 'done') {
        const text = r.status === 'error' ? (r.error instanceof Error ? r.error.message : '保存失败。') : r.status === 'blocked' ? r.reason
          : r.status === 'duplicate' ? '正在保存，请稍候。' : '项目已切换，本次保存未生效。';
        setMsg({kind: 'err', text}); throw new Error(text);
      }
      { const k = nodeDraftKey(s, p.kind, p.id); if (store.get(k)?.value === d) store.set(k, null); }
      setMsg({kind: 'ok', text: '已保存到本机草稿（未同步服务端）'}); dirtyRef.current = false; onSaved(p.kind); onSettled?.();
    } finally { setSaving(false); }
  };
  useEffect(() => api.registerDirty({isDirty: () => dirtyRef.current, save, discard: () => { const {pick: p, scope: s} = live.current; store.set(nodeDraftKey(s, p.kind, p.id), null); }}),
    // eslint-disable-next-line react-hooks/exhaustive-deps -- reads through live ref
    [api]);
  const head = <div style={{display: 'flex', justifyContent: 'space-between', alignItems: 'center'}}>
    <strong data-testid="uw-node-inspector-title">画布节点属性 · {CANVAS_LABEL[pick.kind]}</strong>
    <button type="button" className="uw-btn" onClick={onBack} disabled={dirty} title={dirty ? '先保存或放弃修改' : undefined}>回到章节属性</button></div>;
  if (!info) return <div className="uw-state" data-testid="uw-node-inspector" data-canvas={pick.kind}>{head}<p role="alert" data-state="missing">节点已不存在（可能已被删除）。</p></div>;
  const type = NODE_TYPES[pick.kind].find(t => t.id === info.node.t);
  const value = draft ?? info.node.title;
  return <form className="uw-state" data-testid="uw-node-inspector" data-canvas={pick.kind} data-node-id={pick.id}
    onSubmit={e => { e.preventDefault(); void save().catch(() => {}); }} style={{display: 'grid', gap: 8}}>
    {head}
    <label>节点标题<input aria-label="节点标题" value={value} onChange={e => { setDraft(e.target.value); setMsg(null); }} /></label>
    <dl style={{display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '2px 10px', margin: 0}}>
      <dt>类型</dt><dd data-testid="uw-node-type">{type?.label ?? info.node.t}</dd>
      <dt>位置</dt><dd>{Math.round(info.node.x)}, {Math.round(info.node.y)}</dd>
      <dt>连线</dt><dd>入 {info.ins} · 出 {info.outs}</dd>
      <dt>存储</dt><dd>仅本机草稿 · 未同步服务端</dd>
    </dl>
    <div style={{display: 'flex', gap: 8}}>
      <button type="submit" className="uw-btn uw-btn--primary" disabled={!dirty || saving || !value.trim()} aria-busy={saving || undefined}>保存</button>
      <button type="button" className="uw-btn" disabled={!dirty || saving} onClick={() => { setDraft(null); setMsg(null); dirtyRef.current = false; onSettled?.(); }}>放弃</button>
    </div>
    {msg && <p role={msg.kind === 'err' ? 'alert' : 'status'} data-testid="uw-node-msg">{msg.text}</p>}
  </form>;
}
