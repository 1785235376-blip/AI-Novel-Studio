// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { useLocalHostSession } from '../localHostSession';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionJob } from './studioProductionClient';
import { CUTOUT_WEBP_PROFILE, CUTOUT_WEBP_OUTPUT } from './studioCutoutContract';
import { cutoutAssets, cutoutCommand, cutoutJob, cutoutPreview, cutoutProject } from './studioCpuCutout.testFixtures';
import actual from './fixtures/cpuCutoutWebp.actual.json';

const reply = (value: unknown) => ({ ok: true, status: 200, json: async () => value });
const label = '抠图交付格式（可选）';
let fetcher: ReturnType<typeof vi.fn>;
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
const button = (name: string) => screen.getByRole('button', { name }) as HTMLButtonElement;
const calls = (suffix: string) => fetcher.mock.calls.filter(([url]) => url.endsWith(suffix));
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto); useLocalHostSession.setState({ token: 'synthetic-webp-unit', actorId: '' });
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/providers')) return reply({ items: [], health_probed: false, credentials_read: false });
    if (url.endsWith('/preview')) {
      const command = JSON.parse(init!.body as string), value = cutoutPreview(command);
      if (command.parameters.cutout_output) { value.execution_recipe.parameters = command.parameters; value.execution_recipe.output_profile = CUTOUT_WEBP_OUTPUT; }
      return reply(value);
    }
    if (url.endsWith('/jobs') && init?.method === 'POST') {
      const command = JSON.parse(init.body as string).command, value = cutoutJob('QUEUED', 1, command);
      value.execution_recipe.parameters = command.parameters; value.execution_recipe.output_profile = CUTOUT_WEBP_OUTPUT;
      return reply(value);
    }
    if (url.endsWith('/jobs')) return reply({ items: [] });
    throw new Error('Unexpected WebP UI request');
  }); vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });
function mount() {
  const props = { client: studioProductionClient(cutoutProject, { sessionToken: '' }), assets: cutoutAssets(), canMutate: true, canReview: true, busy: false,
    isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn(), onUnavailable: vi.fn() };
  return { ...render(<StudioMediaExecutionPanel {...props} />), props };
}
async function choose() {
  await waitFor(() => expect((screen.getByLabelText('操作') as HTMLSelectElement).disabled).toBe(false));
  change('操作', 'm5.image.cutout'); fireEvent.click(screen.getByLabelText('source.png · v2'));
  change('绑定当前来源版本的遮罩', 'mask');
}
async function preview() { fireEvent.click(button('读取制作预览')); await screen.findByRole('region', { name: '制作预览确认' }); }
it('keeps default PNG and explicitly queues reviewed WebP without automatic execution', async () => {
  mount(); await choose(); await preview(); expect(JSON.parse(calls('/preview')[0][1].body).parameters).toEqual({});
  change(label, CUTOUT_WEBP_PROFILE); await preview();
  expect(JSON.parse(calls('/preview')[1][1].body).parameters).toEqual({ cutout_output: CUTOUT_WEBP_PROFILE });
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); fireEvent.click(button('仅创建任务并入队'));
  await waitFor(() => expect(calls('/jobs')).toHaveLength(1)); expect(calls('/execute')).toHaveLength(0);
});
it('retires preview and consent when the delivery profile changes away and back', async () => {
  mount(); await choose(); change(label, CUTOUT_WEBP_PROFILE); await preview();
  fireEvent.click(screen.getByLabelText('已核对本次输入、来源和处理边界')); change(label, ''); change(label, CUTOUT_WEBP_PROFILE);
  expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull(); expect(calls('/jobs')).toHaveLength(0);
});
it('decodes actual native File preview/queue/private output/approval and history', async () => {
  const api = studioProductionClient(actual.source.novel_id, { sessionToken: '' });
  fetcher.mockResolvedValue(reply(actual.preview)); expect(await api.preview(actual.command as MediaCommand)).toEqual(actual.preview);
  for (const row of [actual.queued, actual.executed, actual.approved]) { fetcher.mockResolvedValue(reply(row)); expect(await api.get('image', row.id)).toEqual(row); }
  fetcher.mockResolvedValue(reply({ items: [actual.approved] })); expect((await api.list())[0]).toEqual(actual.approved);
});
it.each(['missing', 'contract', 'rgba', 'hash', 'source', 'bytes', 'recipe', 'command'] as const)('rejects %s proof/profile corruption', async mutation => {
  const row = structuredClone(actual.executed) as unknown as ProductionJob;
  if (mutation === 'missing') row.processing_proof = null;
  else if (mutation === 'recipe') row.execution_recipe.parameters = {};
  else if (mutation === 'command') row.command!.parameters = {};
  else {
    const proof = row.processing_proof as unknown as Record<string, unknown>;
    if (mutation === 'contract') proof.contract = 'cpu-binary-mask-cutout/1';
    else if (mutation === 'rgba') delete proof.rgba_sha256;
    else if (mutation === 'hash') proof.output_sha256 = 'a'.repeat(64);
    else if (mutation === 'source') proof.source_sha256 = 'a'.repeat(64);
    else proof.output_bytes = 9 * 1024 * 1024;
  }
  fetcher.mockResolvedValue(reply(row)); await expect(studioProductionClient(actual.source.novel_id, { sessionToken: '' }).get('image', row.id)).rejects.toBeTruthy();
});
it.each([null, true, 'WEBP', 'WEBP_LOSSLESS_V2'])('rejects invalid profile %s before transport', async value => {
  const command = cutoutCommand(); (command.parameters as Record<string, unknown>).cutout_output = value;
  await expect(studioProductionClient(cutoutProject, { sessionToken: '' }).preview(command)).rejects.toBeTruthy(); expect(fetcher).not.toHaveBeenCalled();
});
