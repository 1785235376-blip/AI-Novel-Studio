// @vitest-environment jsdom
// These are local canvas interaction tests. No provider or backend is executed.
import {cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {RebuildCanvas, canvasStorageKey, type CvGraph} from './RebuildCanvas';
import {DualCanvas} from './DualCanvas';

const imageGraph = (prompt?: string): CvGraph => ({
  nodes: [{id: 'image-node', t: 'image_generate', x: 0, y: 0, title: '标题不是生成提示词', ...(prompt === undefined ? {} : {prompt})}],
  edges: [],
});
function selectNode(id = 'image-node') {
  const node = document.querySelector(`[data-node-id="${id}"]`)!;
  fireEvent.pointerDown(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
  fireEvent.pointerUp(node, {button: 0, pointerId: 1, clientX: 40, clientY: 40});
}
beforeEach(() => {
  localStorage.clear();
  vi.stubGlobal('PointerEvent', MouseEvent);
});
afterEach(() => {cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks();});

describe('canvas image task intent', () => {
  it('edits only the selected node prompt, persists the local draft and emits an explicit intent', () => {
    const fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    const onIntent = vi.fn();
    render(<RebuildCanvas kind="image" scope="novel-a" seed={imageGraph('最初提示词')} onImageTaskIntent={onIntent} />);
    expect(screen.queryByLabelText('本次提示词')).toBeNull();
    expect(onIntent).not.toHaveBeenCalled();
    selectNode();
    const prompt = screen.getByLabelText('本次提示词') as HTMLTextAreaElement;
    expect(prompt.value).toBe('最初提示词');
    fireEvent.change(prompt, {target: {value: '  雾中的港口与一盏灯  '}});
    expect(onIntent).not.toHaveBeenCalled();
    const saved = JSON.parse(localStorage.getItem(canvasStorageKey('image', 'novel-a'))!);
    expect(saved.nodes[0].prompt).toBe('  雾中的港口与一盏灯  ');
    fireEvent.click(screen.getByRole('button', {name: '为此节点准备图片任务'}));
    expect(onIntent).toHaveBeenCalledTimes(1);
    expect(onIntent).toHaveBeenCalledWith(expect.objectContaining({id: 'image-node', t: 'image_generate', title: '标题不是生成提示词', prompt: '雾中的港口与一盏灯'}));
    expect(fetcher).not.toHaveBeenCalled();
  });

  it('never substitutes a node title for missing or whitespace-only prompt', () => {
    const onIntent = vi.fn();
    render(<RebuildCanvas kind="image" scope="novel-a" seed={imageGraph()} onImageTaskIntent={onIntent} />);
    selectNode();
    const prompt = screen.getByLabelText('本次提示词') as HTMLTextAreaElement;
    expect(prompt.value).toBe('');
    const prepare = screen.getByRole('button', {name: '为此节点准备图片任务'}) as HTMLButtonElement;
    expect(prepare.disabled).toBe(true);
    fireEvent.change(prompt, {target: {value: '   '}});
    expect(prepare.disabled).toBe(true);
    fireEvent.click(prepare);
    expect(onIntent).not.toHaveBeenCalled();
  });

  it('does not offer task intent for unsupported reference nodes or video generation nodes', () => {
    const onIntent = vi.fn();
    const view = render(<RebuildCanvas kind="image" scope="novel-a" seed={{nodes: [{id: 'image-node', t: 'image_reference', x: 0, y: 0, title: '原图参考'}], edges: []}} onImageTaskIntent={onIntent} />);
    selectNode();
    expect(screen.queryByRole('button', {name: '为此节点准备图片任务'})).toBeNull();
    expect(screen.queryByLabelText('本次提示词')).toBeNull();
    view.rerender(<RebuildCanvas kind="video" scope="novel-a" seed={{nodes: [{id: 'image-node', t: 'video_generate', x: 0, y: 0, title: '视频生成', prompt: '不会派发'}], edges: []}} onImageTaskIntent={onIntent} />);
    selectNode();
    expect(screen.queryByRole('button', {name: '为此节点准备图片任务'})).toBeNull();
    expect(onIntent).not.toHaveBeenCalled();
  });

  it('retires selection and prompt when the project scope changes', () => {
    const onIntent = vi.fn();
    const view = render(<RebuildCanvas kind="image" scope="novel-a" seed={imageGraph('A 私有提示词')} onImageTaskIntent={onIntent} />);
    selectNode();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('A 私有提示词');
    view.rerender(<RebuildCanvas kind="image" scope="novel-b" seed={imageGraph('B 提示词')} onImageTaskIntent={onIntent} />);
    expect(screen.queryByLabelText('本次提示词')).toBeNull();
    expect(screen.queryByText('A 私有提示词')).toBeNull();
    selectNode();
    expect((screen.getByLabelText('本次提示词') as HTMLTextAreaElement).value).toBe('B 提示词');
    expect(onIntent).not.toHaveBeenCalled();
  });

  it('forwards creation-canvas intent through DualCanvas without turning it into a fake task', () => {
    localStorage.setItem(canvasStorageKey('image', 'dual-a'), JSON.stringify(imageGraph('双画布原提示词')));
    const onIntent = vi.fn(), fetcher = vi.fn(); vi.stubGlobal('fetch', fetcher);
    render(<DualCanvas scope="dual-a" onImageTaskIntent={onIntent} />);
    selectNode();
    fireEvent.change(screen.getByLabelText('本次提示词'), {target: {value: '新的双画布提示词'}});
    expect(onIntent).not.toHaveBeenCalled();
    fireEvent.click(screen.getByRole('button', {name: '为此节点准备图片任务'}));
    expect(onIntent).toHaveBeenCalledWith(expect.objectContaining({id: 'image-node', prompt: '新的双画布提示词'}));
    expect(fetcher).not.toHaveBeenCalled();
  });
});
