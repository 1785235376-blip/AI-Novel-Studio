// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditor } from './useStudioGraphEditor';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { DirectorImageClient } from './directorImageClient';
import type { StudioClient } from './studioClient';
import { imageGraphCatalog, imageGraphRecord } from './studioImageGraph.testFixtures';
import { imageAsset, imagePending, imagePreview, imageRegistration, imageReview, imageSnapshot, imageSourceDocument, imageStatus } from './directorImage.testFixtures';
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (label: string, value: string) => fireEvent.change(screen.getByLabelText(label), { target: { value } });
function setup() {
  const images: DirectorImageClient = { assets: vi.fn().mockResolvedValue({ items: [imageAsset] }), capabilities: vi.fn().mockResolvedValue({ enabled: true, registered_choices: [imageRegistration] }),
    list: vi.fn().mockResolvedValue({ items: [imageStatus], truncated: false }), status: vi.fn().mockResolvedValue(imageStatus), preview: vi.fn().mockResolvedValue(imagePreview), dispatch: vi.fn().mockResolvedValue(imageStatus),
    prepare: vi.fn().mockResolvedValue(imagePending), declareCost: vi.fn(), review: vi.fn().mockResolvedValue(imageReview), adopt: vi.fn(), cancel: vi.fn() };
  const creative = { imageDirector: () => images, capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }), list: vi.fn().mockResolvedValue({ items: [imageSourceDocument] }),
    export: vi.fn().mockResolvedValue({ document: imageSourceDocument, document_digest: imageSnapshot.digest }), create: vi.fn(), update: vi.fn(), history: vi.fn(), derive: vi.fn() } as GraphDirectorSource;
  const record = imageGraphRecord(); const graphs = { catalog: vi.fn().mockResolvedValue(imageGraphCatalog()), imageCatalog: vi.fn().mockResolvedValue(imageGraphCatalog()), list: vi.fn().mockResolvedValue({ items: [record] }),
    get: vi.fn().mockResolvedValue(record), runs: vi.fn().mockResolvedValue({ items: [] }), createRun: vi.fn(), save: vi.fn(), create: vi.fn(), preflight: vi.fn(), previewMedia: vi.fn(), dispatchMedia: vi.fn(), executeMedia: vi.fn() };
  const client = { graphs } as unknown as StudioClient, run = async <T,>(work: () => Promise<T>) => work(), current = () => true;
  function Harness({ externalDirty = false }: { externalDirty?: boolean }) {
    const result = useStudioGraphEditor({ active: true, denied: false, identity: 'actor:branch', client, directorSource: creative, canMutate: true, canReview: true, busy: false, externalDirty, isCurrent: current, read: run, mutate: run });
    return <>{result.content}{result.inspector}</>;
  }
  return { Harness, images, creative, graphs };
}
afterEach(cleanup);
async function enter() {
  await screen.findByRole('option', { name: /Independent image graph/ }); change('已保存创作图', 'image-graph');
  await screen.findByRole('button', { name: /选择节点 .* · prompt$/ });
  fireEvent.click(screen.getByRole('button', { name: /选择节点 .* · prompt$/ }));
  click('打开导演总控台'); await waitFor(() => expect((screen.getByLabelText('文档标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(false));
  click('读取导演原文档目录'); await screen.findByRole('option', { name: /原导演 · v2/ }); change('总控台原导演文档', 'director'); click('读取所选导演原文档'); await screen.findByRole('button', { name: '打开图像导演审核' });
  click('打开图像导演审核'); await screen.findByRole('option', { name: /现有 VISION 注册/ }); change('图像理解目标场景', 'scene');
  click('读取图像提案目录'); await screen.findByRole('option', { name: /proposal · DISPATCHED/ }); change('已保存图像提案', 'proposal'); click('读取同一提案状态'); await screen.findByText(/仅核对任务元数据/);
}
it('protects IMAGE cost and note inputs from real canvas click, Escape, node directory and console reads', async () => {
  const { Harness, images, creative, graphs } = setup(); render(<Harness />); await enter(); click('准备图像成本审核'); await screen.findByLabelText(/人工声明本地成本/);
  change('人工声明本地成本（microUSD，1 USD = 1000000）', '24'); change('成本声明依据', '未提交成本依据');
  const prompt = () => screen.getByRole('button', { name: /选择节点 .* · prompt$/ }); const other = () => screen.getByRole('button', { name: /选择节点 .* · references$/ });
  fireEvent.click(other()); fireEvent.keyDown(screen.getByRole('group', { name: '节点图交互区域' }), { key: 'Escape' });
  expect(prompt().getAttribute('aria-pressed')).toBe('true'); expect(other().getAttribute('aria-pressed')).toBe('false');
  click('查找图中节点'); change('查找图中节点', 'references'); fireEvent.keyDown(screen.getByRole('combobox', { name: '查找图中节点' }), { key: 'Enter' });
  expect(prompt().getAttribute('aria-pressed')).toBe('true'); expect((screen.getByLabelText('成本声明依据') as HTMLTextAreaElement).value).toBe('未提交成本依据');
  for (const name of ['读取导演原文档目录', '读取所选导演原文档', '核对导演原文档版本']) expect((screen.getByRole('button', { name }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByLabelText('已保存创作图') as HTMLSelectElement).disabled).toBe(true); expect(creative.export).toHaveBeenCalledTimes(1);
  fireEvent.click(screen.getByLabelText('放弃尚未提交的成本与备注输入')); click('清除未提交的审核输入'); click('读取图像人工审核内容'); await screen.findByLabelText('人工审核后的导演备注');
  change('人工审核后的导演备注', '未提交人工备注'); fireEvent.click(other()); fireEvent.keyDown(screen.getByRole('group', { name: '节点图交互区域' }), { key: 'Escape' });
  expect((screen.getByLabelText('人工审核后的导演备注') as HTMLTextAreaElement).value).toBe('未提交人工备注'); expect(prompt().getAttribute('aria-pressed')).toBe('true');
  expect(images.declareCost).not.toHaveBeenCalled(); expect(images.adopt).not.toHaveBeenCalled(); expect(graphs.save).not.toHaveBeenCalled(); expect(graphs.createRun).not.toHaveBeenCalled();
  click('关闭图像审核并清除本页内容'); fireEvent.click(other()); expect(other().getAttribute('aria-pressed')).toBe('true');
});
it('keeps normal read-only graph selection available when there is no IMAGE intent', async () => {
  const { Harness } = setup(); const view = render(<Harness />); await screen.findByRole('option', { name: /Independent image graph/ }); change('已保存创作图', 'image-graph'); await screen.findByRole('button', { name: /选择节点 .* · prompt$/ });
  view.rerender(<Harness externalDirty />); const node = screen.getByRole('button', { name: /选择节点 .* · prompt$/ }); fireEvent.click(node); expect(node.getAttribute('aria-pressed')).toBe('true');
  fireEvent.keyDown(screen.getByRole('group', { name: '节点图交互区域' }), { key: 'Escape' }); expect(node.getAttribute('aria-pressed')).toBe('false');
});
