// @vitest-environment jsdom
// [HERMIA-FE-20261026 DUAL] 上下双画布独立性：上画布在下画布为空时照常可用；改一边不动另一边；下画布绝不自动接入上画布。
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest';
import {render, screen, fireEvent, cleanup, within} from '@testing-library/react';
import {DualStack} from './DualStack';
import {canvasStorageKey, sessionCanvasStore, NODE_TYPES, type CvGraph} from './RebuildCanvas';
import {LOWER_TYPES, LOWER_KEY_PREFIX, feedToUpper, lowerCanvasStore} from './dualStackModel';
import {resolveWorkspaceIdentity} from '../../workspace/state/scopeLease';
import {useStudio} from '../../store';

const COLLAB = {workspaceId: 'ws1', projectId: 'n1', storylineId: 's1', branchId: 'b1'};
const layer = (l: 'upper' | 'lower') => document.querySelector(`[data-canvas-layer=${l}]`) as HTMLElement;
const addVia = (l: 'upper' | 'lower', type: string) => {
  fireEvent.contextMenu(within(layer(l)).getByRole('application'), {clientX: 50, clientY: 50});
  fireEvent.click(layer(l).querySelector(`[data-add-node-menu] [data-node-type=${type}]`)!);
};
const nodes = (l: 'upper' | 'lower') => layer(l).querySelectorAll('[data-node-id]').length;
const lowerKeys = () => Object.keys(localStorage).filter(k => k.startsWith(LOWER_KEY_PREFIX));

beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); useStudio.setState({actor: undefined, scope: undefined}); });

describe('dualStackModel (pure)', () => {
  it('feedToUpper returns a new upper graph with one snapshot copy and mutates neither input', () => {
    const up: CvGraph = {nodes: [{id: 'u1', t: 'image_prompt', x: 0, y: 0, title: '主线'}], edges: []};
    const low = {id: 'l1', t: 'image_reference' as const, x: 9, y: 9, title: '雾港参考'};
    const upSnap = JSON.stringify(up), lowSnap = JSON.stringify(low);
    const {graph, id} = feedToUpper(up, low);
    expect(JSON.stringify(up)).toBe(upSnap); expect(JSON.stringify(low)).toBe(lowSnap);
    expect(graph.nodes).toHaveLength(2); expect(id).not.toBe('l1');
    expect(graph.nodes[1]).toMatchObject({t: 'image_reference', title: '↑雾港参考'});
  });
  it('lower palette is enrichment only and every id renders in the upper palette', () => {
    for (const k of ['image', 'video'] as const) {
      for (const t of LOWER_TYPES[k]) { expect(NODE_TYPES[k].some(u => u.id === t.id)).toBe(true); expect(t.id).not.toMatch(/generate|export|review/); }
    }
  });
  it('lower key: real identity → per user/project/instance localStorage; no identity → session memory', () => {
    const real = lowerCanvasStore('image', resolveWorkspaceIdentity({actorId: 'actor-1', collabScope: COLLAB, projectId: 'n1'}));
    expect(real.persist).toBe('local'); expect(real.key).toContain('actor-1'); expect(real.key).toContain('ws1/s1/b1');
    const ses = lowerCanvasStore('image', resolveWorkspaceIdentity({actorId: undefined, collabScope: null, projectId: 'n1'}));
    expect(ses.persist).toBe('session');
    expect(lowerCanvasStore('video', resolveWorkspaceIdentity({actorId: 'actor-1', collabScope: COLLAB, projectId: 'n1'})).key).not.toBe(real.key);
  });
});

describe('DualStack', () => {
  for (const kind of ['image', 'video'] as const) {
    it(`${kind}: upper is fully usable while the lower is empty; lower untouched`, () => {
      const fetchSpy = vi.spyOn(globalThis, 'fetch' as any);
      render(<DualStack kind={kind} scope="n1" />);
      expect(nodes('lower')).toBe(0);
      addVia('upper', kind === 'image' ? 'image_generate' : 'video_generate');
      expect(nodes('upper')).toBe(1); expect(nodes('lower')).toBe(0);
      expect(JSON.parse(localStorage.getItem(canvasStorageKey(kind, 'n1'))!).nodes).toHaveLength(1);
      // collapsing the lower canvas leaves the upper working
      fireEvent.click(screen.getByRole('button', {name: '收起下画布'}));
      expect(layer('lower')).toBeNull(); addVia('upper', 'text_input'); expect(nodes('upper')).toBe(2);
      expect(fetchSpy).not.toHaveBeenCalled();
    });
    it(`${kind}: adding to the lower never auto-feeds the upper; feeding needs an explicit confirmed click`, () => {
      render(<DualStack kind={kind} scope="n1" />);
      addVia('upper', 'text_input');
      const upRaw = localStorage.getItem(canvasStorageKey(kind, 'n1'));
      addVia('lower', 'image_reference');
      expect(nodes('lower')).toBe(1); expect(nodes('upper')).toBe(1);
      expect(localStorage.getItem(canvasStorageKey(kind, 'n1'))).toBe(upRaw); // no auto-feed
      // lower palette has no generation nodes
      fireEvent.contextMenu(within(layer('lower')).getByRole('application'), {clientX: 5, clientY: 5});
      expect(layer('lower').querySelector('[data-node-type$=_generate]')).toBeNull();
      fireEvent.keyDown(layer('lower').querySelector('[data-add-node-menu] input')!, {key: 'Escape'});
      const feed = layer('lower').querySelector('[data-feed-upper]') as HTMLButtonElement;
      fireEvent.click(feed); // opens confirm only
      expect(localStorage.getItem(canvasStorageKey(kind, 'n1'))).toBe(upRaw);
      fireEvent.click(screen.getByRole('button', {name: '取消'}));
      expect(localStorage.getItem(canvasStorageKey(kind, 'n1'))).toBe(upRaw);
      fireEvent.click(layer('lower').querySelector('[data-feed-upper]')!);
      fireEvent.click(layer('lower').querySelector('[data-feed-confirm]')!);
      expect(nodes('upper')).toBe(2); expect(nodes('lower')).toBe(1);
      const up = JSON.parse(localStorage.getItem(canvasStorageKey(kind, 'n1'))!);
      expect(up.nodes[1]).toMatchObject({t: 'image_reference'}); expect(up.nodes[1].title).toMatch(/^↑/);
      // later edits to the upper do not touch the lower (snapshot, no live link)
      addVia('upper', 'text_input'); expect(nodes('lower')).toBe(1);
    });
  }
  it('feed button is disabled until a lower node is selected (just-added nodes are selected)', () => {
    render(<DualStack kind="image" scope="n1" />);
    expect((layer('lower').querySelector('[data-feed-upper]') as HTMLButtonElement).disabled).toBe(true);
  });
  it('no identity: shows 「仅本次会话」 and never writes the lower to localStorage', () => {
    render(<DualStack kind="image" scope="n1" />);
    expect(screen.getByText('仅本次会话')).toBeTruthy();
    addVia('lower', 'image_style');
    expect(lowerKeys()).toEqual([]);
  });
  it('real identity: lower persists under the identity key; another user does not see it', () => {
    useStudio.setState({actor: {id: 'actor-1', displayName: 'A', workspaceId: 'ws1'}, scope: COLLAB as any, novelId: 'n1'});
    const v = render(<DualStack kind="video" scope="n1" />);
    expect(screen.queryByText('仅本次会话')).toBeNull();
    addVia('lower', 'director_note');
    expect(lowerKeys()).toHaveLength(1); expect(lowerKeys()[0]).toContain('actor-1');
    v.unmount();
    useStudio.setState({actor: {id: 'actor-2', displayName: 'B', workspaceId: 'ws1'}});
    render(<DualStack kind="video" scope="n1" />);
    expect(nodes('lower')).toBe(0);
  });
  it('generation is labelled unavailable, not faked', () => {
    render(<DualStack kind="video" scope="n1" />);
    expect(document.querySelector('[data-unavailable=canvas-run]')!.textContent).toMatch(/不可用/);
  });
});
