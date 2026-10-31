// @vitest-environment jsdom
// [HERMIA-FE-20261022 U1] 右键空白加节点 · 本机草稿标注 · 不发请求
import {describe, it, expect, beforeEach, vi} from 'vitest';
import {render, screen, fireEvent, cleanup} from '@testing-library/react';
import {RebuildCanvas, canvasStorageKey} from './RebuildCanvas';

describe('RebuildCanvas', () => {
  beforeEach(() => { cleanup(); localStorage.clear(); });
  it('right-click on empty canvas opens add-node menu and adds node at click position, local only', () => {
    const fetchSpy = vi.spyOn(globalThis, 'fetch' as any);
    render(<RebuildCanvas kind="image" scope="n1" />);
    expect(screen.getByText(/仅本机草稿/)).toBeTruthy();
    fireEvent.contextMenu(screen.getByRole('application', {name: '图片无限画布'}), {clientX: 120, clientY: 80});
    const menu = document.querySelector('[data-add-node-menu=rebuild]')!;
    expect(menu).toBeTruthy();
    fireEvent.click(menu.querySelector('[data-node-type=image_generate]')!);
    const saved = JSON.parse(localStorage.getItem(canvasStorageKey('image', 'n1'))!);
    expect(saved.nodes).toHaveLength(1);
    expect(saved.nodes[0]).toMatchObject({t: 'image_generate'});
    expect(screen.getByText(/节点 1 · 连线 0/)).toBeTruthy();
    expect(fetchSpy).not.toHaveBeenCalled();
  });
  it('video canvas filters types and right-click on node offers delete', () => {
    render(<RebuildCanvas kind="video" scope="n2" seed={{nodes: [{id: 'a', t: 'storyboard_shot', x: 0, y: 0, title: '镜头 1'}], edges: []}} />);
    const node = document.querySelector('[data-node-id=a]')!;
    fireEvent.contextMenu(node, {clientX: 10, clientY: 10});
    fireEvent.click(screen.getByRole('menuitem', {name: '删除节点'}));
    expect(document.querySelector('[data-node-id=a]')).toBeNull();
  });
});
