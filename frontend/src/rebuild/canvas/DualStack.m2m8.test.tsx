// @vitest-environment jsdom
// [HERMIA-FE-20261030 B2] Vera 变异表补测：M2（接入时复用下画布 id = 引用而非快照）、M8（普通模式也挂 DualStack）。
import {describe, it, expect, beforeEach, afterEach, vi} from 'vitest';
import {render, cleanup, fireEvent, within, waitFor} from '@testing-library/react';
import {DualStack} from './DualStack';
import {canvasStorageKey, sessionCanvasStore} from './RebuildCanvas';
import {ImageRebuild} from '../image/ImageRebuild';
import {VideoRebuild} from '../video/VideoRebuild';
import {useStudio} from '../../store';

const json = (b: unknown) => Promise.resolve(new Response(JSON.stringify(b), {status: 200, headers: {'Content-Type': 'application/json'}}));
const layer = (l: 'upper' | 'lower') => document.querySelector(`[data-canvas-layer=${l}]`) as HTMLElement;
const ids = (l: 'upper' | 'lower') => [...layer(l).querySelectorAll('[data-node-id]')].map(n => n.getAttribute('data-node-id')!);
beforeEach(() => { cleanup(); localStorage.clear(); sessionCanvasStore.clear(); useStudio.setState({novelId: 'n1', actor: undefined, scope: undefined}); });
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });

describe('M2: fed node is a snapshot with a NEW id', () => {
  for (const kind of ['image', 'video'] as const) it(`${kind}: upper copy id differs from the lower source id`, () => {
    render(<DualStack kind={kind} scope="n1" />);
    fireEvent.contextMenu(within(layer('lower')).getByRole('application'), {clientX: 40, clientY: 40});
    fireEvent.click(layer('lower').querySelector('[data-add-node-menu] [data-node-type=text_input]')!);
    const [lowerId] = ids('lower');
    fireEvent.click(layer('lower').querySelector('[data-feed-upper]')!);
    fireEvent.click(document.querySelector('[data-feed-confirm]')!);
    const stored = JSON.parse(localStorage.getItem(canvasStorageKey(kind, 'n1'))!).nodes.map((n: {id: string}) => n.id);
    expect(stored).toHaveLength(1);
    expect(stored[0]).not.toBe(lowerId);
    expect(ids('upper')).not.toContain(lowerId);
    expect(ids('lower')).toEqual([lowerId]);
  });
});

describe('M8: basic mode never mounts DualStack (after data has loaded)', () => {
  it('IMAGE canvas view: basic → single canvas, pro → DualStack', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode="basic" />);
    await waitFor(() => expect(document.querySelector('.rcv')).not.toBeNull());
    expect(document.querySelector('[data-dual-stack]')).toBeNull();
    r.rerender(<ImageRebuild novelId="n1" view="canvas" onViewChange={() => {}} shellMode="pro" />);
    await waitFor(() => expect(document.querySelector('[data-dual-stack=image]')).not.toBeNull());
  });
  it('VIDEO studio view: basic → single canvas, pro → DualStack', async () => {
    vi.stubGlobal('fetch', vi.fn(() => json([])));
    const r = render(<VideoRebuild novelId="n1" shellMode="basic" />);
    await waitFor(() => expect(document.querySelector('#vidCanvasHost .rcv')).not.toBeNull());
    expect(document.querySelector('[data-dual-stack]')).toBeNull();
    r.rerender(<VideoRebuild novelId="n1" shellMode="pro" />);
    await waitFor(() => expect(document.querySelector('[data-dual-stack=video]')).not.toBeNull());
  });
});
