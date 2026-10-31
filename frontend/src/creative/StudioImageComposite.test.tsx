// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { Blob as NodeBlob } from 'node:buffer';
import { ApiError } from '../api';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionJob, type ProductionPreview } from './studioProductionClient';
import type { StudioAsset } from './studioClient';
import { checkedCompositeCommand } from './studioImageCompositeContract';
import captured from './fixtures/image-composite.capture.json';

const actual = captured as unknown as { command: MediaCommand; preview: ProductionPreview; queued: ProductionJob;
  executed: ProductionJob; approved: ProductionJob; assets: StudioAsset[]; output_base64: string };
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const base = `/api/projects/${actual.preview.novel_id}/studio/production`;
let fetcher: ReturnType<typeof vi.fn>, current: ProductionJob, input: MediaCommand;
let previewChange: ((value: ProductionPreview) => ProductionPreview) | undefined;
const json = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); vi.stubGlobal('Blob', NodeBlob);
  Object.defineProperty(URL, 'createObjectURL', { configurable: true, value: vi.fn(() => 'blob:composite-candidate') });
  Object.defineProperty(URL, 'revokeObjectURL', { configurable: true, value: vi.fn() });
  useLocalHostSession.setState({ token: 'composite-fixture', actorId: '' });
  current = clone(actual.queued); input = clone(actual.command); previewChange = undefined;
  const receipt = (value: ProductionJob) => ({ ...clone(value), request_id: input.request_id, command: clone(input),
    execution_recipe: { ...clone(value.execution_recipe), layers: clone(input.image_layers) } });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base + '/providers') return json({ items: [], health_probed: false, credentials_read: false });
    if (url === base + '/preview') {
      input = JSON.parse(String(init?.body)) as MediaCommand;
      const value = { ...clone(actual.preview), request_id: input.request_id, command: clone(input),
        sources: input.source_snapshots.map(source => clone(actual.preview.sources!.find(item => item.snapshot.id === source.id)!)),
        execution_recipe: { ...clone(actual.preview.execution_recipe), layers: clone(input.image_layers) } };
      return json(previewChange ? previewChange(value) : value);
    }
    if (url === base + '/jobs') {
      if (init?.method === 'POST') { input = JSON.parse(String(init.body)).command; current = receipt(actual.queued); return json(current); }
      return json({ items: [current] });
    }
    if (url.endsWith('/execute')) { current = receipt(actual.executed); return json(current); }
    if (url.endsWith('/review')) { current = receipt(actual.approved); return json(current); }
    if (url.endsWith('/candidate')) return new Response(Buffer.from(actual.output_base64, 'base64'), {
      headers: { 'Content-Type': 'image/png', 'X-Asset-Sha256': actual.executed.output_candidate!.digest } });
    if (url === base + '/jobs/image/' + current.id) return json(current);
    throw new Error('Unexpected fixture request ' + url);
  });
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const makeClient = () => studioProductionClient(actual.preview.novel_id, { sessionToken: '' });
const perform = <T,>(work: () => Promise<T>) => work();
function mount(canMutate = true) {
  const client = makeClient();
  render(<StudioMediaExecutionPanel client={client} assets={actual.assets} canMutate={canMutate} canReview busy={false}
    isCurrent={() => true} read={perform} mutate={perform} onDirtyChange={() => {}} onUnavailable={() => {}} />);
  return client;
}
function chooseLayers() {
  fireEvent.change(screen.getByRole('combobox', { name: '操作' }), { target: { value: 'm5.image.composite' } });
  for (const asset of actual.assets) fireEvent.click(screen.getByLabelText(asset.filename + ' · v' + asset.version));
}
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;

describe('strict original composite client', () => {
  it('decodes native File preview, job, CPU proof and review receipts', async () => {
    const client = makeClient(), preview = await client.preview(actual.command);
    const queued = await client.create(actual.command, preview.preview_digest);
    const result = await client.execute(queued);
    expect(result.processing_proof).toEqual(actual.executed.processing_proof);
    expect((await client.candidate(result)).type).toBe('image/png');
    const approved = await client.review(result);
    expect(approved.status).toBe('APPROVED'); expect(approved.approved_asset_version).toBe(2);
  });
  it.each(['third_layer', 'wrong_order', 'coerced_opacity', 'provider', 'extra_recipe'] as const)('rejects caller %s before sending', change => {
    const command = clone(actual.command);
    if (change === 'third_layer') command.image_layers!.push(clone(command.image_layers![0]));
    if (change === 'wrong_order') command.image_layers!.reverse();
    if (change === 'coerced_opacity') (command.image_layers![0] as unknown as { opacity: unknown }).opacity = true;
    if (change === 'provider') command.provider_id = 'unreviewed';
    if (change === 'extra_recipe') Object.assign(command, { execution_recipe: actual.preview.execution_recipe });
    expect(() => checkedCompositeCommand(command)).toThrow(ApiError); expect(fetcher).not.toHaveBeenCalled();
  });
  it.each(['layer', 'recipe', 'source'] as const)('rejects misbound server %s', async change => {
    previewChange = value => {
      if (change === 'layer') value.command.image_layers![0].opacity = 0;
      if (change === 'recipe') (value.execution_recipe.layers as { opacity: number }[])[0].opacity = 0;
      if (change === 'source') value.sources![1].snapshot.version += 1;
      return value;
    };
    await expect(makeClient().preview(actual.command)).rejects.toBeInstanceOf(ApiError);
  });
});

describe('two-layer authoring over the original media panel', () => {
  it('binds order, visibility and opacity and retires old preview consent on edits', async () => {
    mount(); chooseLayers();
    expect(screen.queryByRole('textbox', { name: '本次提示词' })).toBeNull();
    fireEvent.change(screen.getByLabelText('第 2 层透明度（0–255）'), { target: { value: '128' } });
    await waitFor(() => expect(button('读取制作预览').disabled).toBe(false));
    fireEvent.click(button('读取制作预览'));
    await screen.findByRole('region', { name: '制作预览确认' });
    expect(input.image_layers).toEqual(actual.command.image_layers);
    fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    fireEvent.click(button('交换上下层'));
    expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
    fireEvent.click(screen.getByLabelText('显示第 1 层'));
    await waitFor(() => expect(button('读取制作预览').disabled).toBe(false));
    fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' });
    expect(input.source_snapshots[0].id).toBe(actual.command.source_snapshots[1].id);
    expect(input.image_layers![0].opacity).toBe(128); expect(input.image_layers![0].visible).toBe(false);
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/execute'))).toBe(false);
  });
  it('requires explicit queue, execute, candidate inspection and human review', async () => {
    mount(); chooseLayers();
    fireEvent.change(screen.getByLabelText('第 2 层透明度（0–255）'), { target: { value: '128' } });
    await waitFor(() => expect(button('读取制作预览').disabled).toBe(false));
    fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' });
    fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界'));
    fireEvent.click(button('仅创建任务并入队')); await screen.findByRole('button', { name: '明确执行当前入队任务' });
    expect(fetcher.mock.calls.some(([url]) => String(url).endsWith('/execute'))).toBe(false);
    fireEvent.click(button('明确执行当前入队任务'));
    await screen.findByText('双层 PNG 合成证明');
    expect(button('明确审核并入素材库').disabled).toBe(true);
    fireEvent.click(button('读取并核对候选媒体'));
    await screen.findByAltText('本任务经摘要核对的图片候选');
    fireEvent.click(screen.getByLabelText('已查看本次候选，确认采用当前任务版本与输出摘要'));
    fireEvent.click(button('明确审核并入素材库'));
    await waitFor(() => expect(current.status).toBe('APPROVED'));
    expect(fetcher.mock.calls.filter(([url]) => String(url).endsWith('/execute'))).toHaveLength(1);
  });
  it('keeps write controls disabled without mutation permission', () => {
    mount(false); expect((screen.getByRole('combobox', { name: '操作' }) as HTMLSelectElement).disabled).toBe(true);
    expect(button('读取制作预览').disabled).toBe(true);
  });
});
