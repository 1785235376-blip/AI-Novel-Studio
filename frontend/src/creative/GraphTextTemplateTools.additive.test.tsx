// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphTextTemplateTools } from './GraphTextTemplateTools';
import { exportTextGraphTemplate } from './graphTextTemplates';
import { blankGraph } from './graphDraft';
import { modelCatalog } from './studioGraphModel.testFixtures';
import { downloadPortableBlob } from '../experimental/portableProjectsClient';
import type { StudioGraphDefinition } from './studioGraphTypes';
vi.mock('../experimental/portableProjectsClient', () => ({ downloadPortableBlob: vi.fn() }));
afterEach(() => { cleanup(); vi.clearAllMocks(); });
function graph(): StudioGraphDefinition { return { ...blankGraph(), nodes: [{ id: 'Source', definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: 'Source prose' }, position: { x: 0, y: 0 } }] }; }
function props() { return { definition: blankGraph(), catalog: modelCatalog(), owner: {}, disabled: false, isCurrent: () => true, onApply: vi.fn() }; }
async function importFile() { const raw = exportTextGraphTemplate(graph()); fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'), { target: { files: [{ size: raw.length, text: async () => raw }] } }); await screen.findByText(/将新增 1 个节点/); }
function retained(element: HTMLElement, name = 'onClick') { const key = Object.keys(element).find(k => k.startsWith('__reactProps$'))!; return (element as any)[key][name]; }
it('stages imported nodes only after explicit confirmation and consumes it once', async () => { const p = props(); render(<GraphTextTemplateTools {...p} />); await importFile(); expect(p.onApply).not.toHaveBeenCalled(); fireEvent.click(screen.getByLabelText('确认仅把模板追加到当前本地草稿')); const apply = retained(screen.getByText('明确追加模板节点')); act(() => { apply(); apply(); }); expect(p.onApply).toHaveBeenCalledTimes(1); expect(p.onApply.mock.calls[0][0].nodes[0].id).not.toBe('Source'); });
it.each(['uncheck', 'owner', 'disabled ABA', 'target', 'unmount'])('retires import approval after %s', async mode => { const p = props(), view = render(<GraphTextTemplateTools {...p} />); await importFile(); fireEvent.click(screen.getByLabelText('确认仅把模板追加到当前本地草稿')); const apply = retained(screen.getByText('明确追加模板节点'));
 if (mode === 'uncheck') { const change = retained(screen.getByLabelText('确认仅把模板追加到当前本地草稿'), 'onChange'); act(() => { change({ target: { checked: false } }); apply(); }); }
 else { if (mode === 'owner') view.rerender(<GraphTextTemplateTools {...p} owner={{}} />); if (mode === 'disabled ABA') { view.rerender(<GraphTextTemplateTools {...p} disabled />); view.rerender(<GraphTextTemplateTools {...p} />); } if (mode === 'target') view.rerender(<GraphTextTemplateTools {...p} definition={blankGraph()} />); if (mode === 'unmount') view.unmount(); act(apply); }
 expect(p.onApply).not.toHaveBeenCalled();
});
it('does not publish a late file result into a different target', async () => { const p = props(), view = render(<GraphTextTemplateTools {...p} />); let resolve!: (value: string) => void; fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'), { target: { files: [{ size: 100, text: () => new Promise<string>(r => { resolve = r; }) }] } }); view.rerender(<GraphTextTemplateTools {...p} owner={{}} />); await act(async () => resolve(exportTextGraphTemplate(graph()))); expect(screen.queryByText(/将新增/)).toBeNull(); expect(p.onApply).not.toHaveBeenCalled(); });
it('requires a single-use local export acknowledgment and rejects oversized files before reading', async () => { const p = { ...props(), definition: graph() }; render(<GraphTextTemplateTools {...p} />); expect(downloadPortableBlob).not.toHaveBeenCalled(); fireEvent.click(screen.getByLabelText('确认将当前节点文字、分组与便笺导出为本地模板文件')); const action = retained(screen.getByText('导出受限文字图模板')); act(() => { action(); action(); }); expect(downloadPortableBlob).toHaveBeenCalledTimes(1); expect(vi.mocked(downloadPortableBlob).mock.calls[0][1]).toBe('poemseed-text-graph-template.json');
 const text = vi.fn(); fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'), { target: { files: [{ size: 110001, text }] } }); await screen.findByText(/模板读取或兼容性检查失败/); expect(text).not.toHaveBeenCalled(); });
