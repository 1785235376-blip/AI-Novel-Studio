// [HERMIA-FE-20261025 U2-M6] selection + context navigation reducer (mock evidence; pure)
import {describe, expect, it} from 'vitest';
import {EMPTY_SELECTION, multiEditSurface, pruneSelection, selectBox, selectDirect, selectToggle} from './selection';
import {INITIAL_NAV, openTask, panelClosed, returnToOrigin, toggleCompare, resetNav} from './contextNav';
import type {NavReturnPoint, TaskRef} from '../contracts';

const origin: NavReturnPoint = {panelId: 'creative', canvas: 'creative', nodeIds: ['c1', 'c2'], focusTestId: 'uw-creative-canvas', viewport: {x: -260, y: 40, zoom: 1.2}};
const task = (over: Partial<TaskRef> = {}): TaskRef => ({source: 'task-center', id: 't-1', owner: 'image', status: 'succeeded', revision: 3, title: '封面', link: {canvas: 'execution', documentId: null, nodeId: 'e1'}, stale: false, ...over});
const env = (nodes: Record<string, string[]>) => ({nodeExists: (c: 'creative' | 'execution', id: string) => (nodes[c] ?? []).includes(id), capture: () => origin});

describe('selection', () => {
  it('direct, toggle, cross-canvas replace', () => {
    let s = selectDirect(EMPTY_SELECTION, 'image', 'a');
    s = selectToggle(s, 'image', 'b'); expect(s).toEqual({canvas: 'image', ids: ['a', 'b']});
    s = selectToggle(s, 'image', 'a'); expect(s.ids).toEqual(['b']);
    expect(selectToggle(s, 'video', 'v')).toEqual({canvas: 'video', ids: ['v']});
    expect(selectDirect(s, 'image', null)).toEqual({canvas: 'image', ids: []});
  });
  it('box select hits intersecting rects; additive keeps same-canvas only', () => {
    const nodes = [{id: 'a', rect: {x: 0, y: 0, w: 180, h: 60}}, {id: 'b', rect: {x: 300, y: 0, w: 180, h: 60}}, {id: 'c', rect: {x: 0, y: 200, w: 180, h: 60}}];
    expect(selectBox(EMPTY_SELECTION, 'image', {x: 100, y: 10, w: 250, h: 20}, nodes).ids).toEqual(['a', 'b']);
    expect(selectBox({canvas: 'image', ids: ['c']}, 'image', {x: 295, y: 0, w: 10, h: 5}, nodes, true).ids).toEqual(['c', 'b']);
    expect(selectBox({canvas: 'video', ids: ['z']}, 'image', {x: 295, y: 0, w: 10, h: 5}, nodes, true).ids).toEqual(['b']);
  });
  it('prune reports deleted nodes instead of keeping phantoms', () => {
    expect(pruneSelection({canvas: 'image', ids: ['a', 'gone']}, id => id === 'a')).toEqual({sel: {canvas: 'image', ids: ['a']}, missing: ['gone']});
  });
  it('multi-select exposes no group-editable field and never offers batch generate', () => {
    const m = multiEditSurface('image', [{id: 'a', t: 'image_prompt', x: 0, y: 0, title: 'A'}, {id: 'b', t: 'image_generate', x: 0, y: 0, title: 'B'}]);
    expect(m.fields.filter(f => f.mode === 'editable')).toEqual([]);
    expect(m.fields.find(f => f.key === 'generate')!.mode).toBe('unsupported');
    expect(m.actions).not.toContain('generate');
    expect(m.typesLabel).toBe('图片提示词、生成图片');
  });
});

describe('context navigation', () => {
  it('single task with link opens execution alone, selects the real node, captures origin once', () => {
    const r = openTask(INITIAL_NAV, task(), env({execution: ['e1']}));
    expect(r.intent).toEqual({kind: 'show', preset: 'execution-single', select: {canvas: 'execution', nodeIds: ['e1']}, focusPanel: 'execution'});
    expect(r.state.origin).toBe(origin);
    // task switch keeps the ORIGINAL origin
    const other = {...origin, nodeIds: ['zzz']};
    const r2 = openTask(r.state, task({id: 't-2', link: {canvas: 'creative', documentId: null, nodeId: 'c1'}}), {...env({creative: ['c1']}), capture: () => other});
    expect(r2.state.origin).toBe(origin); expect(r2.state.task!.id).toBe('t-2');
    expect(r2.intent).toEqual({kind: 'show', preset: 'creative', select: {canvas: 'creative', nodeIds: ['c1']}, focusPanel: 'creative'});
  });
  it('missing link → honest notice, no fake node selected', () => {
    const r = openTask(INITIAL_NAV, task({link: null}), env({}));
    expect(r.intent).toEqual({kind: 'show', preset: 'execution-single', select: null, focusPanel: 'execution'});
    expect(r.state.notice!.text).toBe('任务「封面」没有关联到具体画布节点。');
  });
  it('deleted node → warning + next step, nothing selected', () => {
    const r = openTask(INITIAL_NAV, task(), env({execution: []}));
    expect(r.intent).toMatchObject({kind: 'show', select: null});
    expect(r.state.notice).toEqual({tone: 'warn', text: '任务「封面」关联的节点在执行画布里找不到了（可能已删除）。', next: '画布没有被修改；可以回到原位置，或在任务详情里查看来源。'});
  });
  it('stale task → no navigation', () => {
    expect(openTask(INITIAL_NAV, task({stale: true}), env({execution: ['e1']})).intent).toEqual({kind: 'none'});
  });
  it('return restores origin viewport/selection; reports vanished origin nodes', () => {
    const s = openTask(INITIAL_NAV, task(), env({execution: ['e1']})).state;
    const ok = returnToOrigin(s, env({creative: ['c1', 'c2']}));
    expect(ok.intent).toEqual({kind: 'restore', point: origin, preset: 'creative', missingNodes: []});
    expect(ok.state).toEqual(INITIAL_NAV);
    const gone = returnToOrigin(s, env({creative: ['c1']}));
    expect(gone.intent).toEqual({kind: 'restore', point: {...origin, nodeIds: ['c1']}, preset: 'creative', missingNodes: ['c2']});
    expect(gone.state.notice!.text).toBe('已回到原位置，但原来选中的 1 个节点已不存在。');
    expect(returnToOrigin(INITIAL_NAV, env({})).intent).toEqual({kind: 'none'});
  });
  it('compare is explicit and toggles back to the single view of the current context', () => {
    const s = openTask(INITIAL_NAV, task(), env({execution: ['e1']})).state;
    const c = toggleCompare(s); expect(c.state.preset).toBe('compare');
    expect(toggleCompare(c.state).state.preset).toBe('execution-single');
    expect(toggleCompare(toggleCompare(INITIAL_NAV).state).state.preset).toBe('creative');
  });
  it('closing execution falls back to creative (no auto reopen) and keeps origin; reset on scope switch', () => {
    const s = openTask(INITIAL_NAV, task(), env({execution: ['e1']})).state;
    const c = panelClosed(s, 'execution'); expect(c.preset).toBe('creative'); expect(c.origin).toBe(origin);
    expect(c.notice!.next).toBe('按 Ctrl／⌘+Alt+E 可以重新打开；原位置仍可返回。');
    expect(resetNav()).toEqual(INITIAL_NAV);
  });
});
