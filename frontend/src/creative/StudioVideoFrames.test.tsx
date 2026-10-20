// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { StudioMediaExecutionPanel } from './StudioMediaExecutionPanel';
import { studioProductionClient, type MediaCommand, type ProductionProvider } from './studioProductionClient';
import type { StudioAsset } from './studioClient';

const project = 'video-frame-project';
const base = '/api/projects/' + project + '/studio/production';
const digest = (value: string) => value.repeat(64).slice(0, 64);
const assets: StudioAsset[] = [
  { id: 'asset-first', filename: 'first.png', kind: 'image', version: 2, sha256: digest('a'), size: 100, media_type: 'image/png', created_at: '', deleted_at: null, manual_mask: null, provenance: {} },
  { id: 'asset-last', filename: 'last.png', kind: 'image', version: 3, sha256: digest('b'), size: 100, media_type: 'image/png', created_at: '', deleted_at: null, manual_mask: null, provenance: {} },
] as unknown as StudioAsset[];
const source = (asset: StudioAsset) => ({ id: asset.id, kind: 'ASSET' as const, version: asset.version, digest: asset.sha256, asset_kind: 'image' as const });
function provider(endFrame: boolean): ProductionProvider {
  return { operation_id: 'm7.video.i2v', provider_id: 'http-video', model_id: 'frame-model', local: true,
    route_digest: digest('c'), capability: 'image_to_video', supported_parameters: ['width', 'height', 'duration_seconds', 'frame_rate', 'seed'],
    readiness: 'CONFIGURED_NOT_VERIFIED', video_frame_capabilities: { start_frame: true, end_frame: endFrame, multi_reference: false } };
}
let posted: MediaCommand | null = null;
let providerEndFrame = true;
const response = (value: unknown) => new Response(JSON.stringify(value), { status: 200, headers: { 'Content-Type': 'application/json' } });
let fetcher: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto);
  posted = null; providerEndFrame = true;
  fetcher = vi.fn(async (url: string, init?: RequestInit) => {
    if (url === base + '/providers') return response({ items: [provider(providerEndFrame)], health_probed: false, credentials_read: false });
    if (url === base + '/preview') {
      posted = JSON.parse(String(init?.body)) as MediaCommand;
      const command = posted;
      return response({
        contract: 'studio-production-preview/1', novel_id: project, branch_id: null, request_id: command.request_id,
        operation_id: command.operation_id, preview_digest: digest('d'), request_digest: digest('e'), command,
        provider: { provider_id: command.provider_id, model_id: command.model_id, local: true, route_digest: digest('c') },
        execution_recipe: { contract: 'studio-execution-recipe/1', operation_id: command.operation_id,
          adapter: 'ORIGINAL_HTTP_PROVIDER', recipe_digest: digest('f'), automatic_fallback: false },
        product_acceptance: 'LOCAL_REQUIRED', execution_available: true, automatic_dispatch: false,
        output_policy: 'PRIVATE_CANDIDATE_THEN_EXPLICIT_REVIEW',
      });
    }
    throw new Error('Unexpected request ' + url);
  });
  vi.stubGlobal('fetch', fetcher);
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); });
const perform = <T,>(work: () => Promise<T>) => work();
function mount() {
  const client = studioProductionClient(project, { sessionToken: '' });
  render(<StudioMediaExecutionPanel client={client} assets={assets} canMutate canReview busy={false}
    isCurrent={() => true} read={perform} mutate={perform} onDirtyChange={() => {}} onUnavailable={() => {}} />);
}
async function chooseFrames(endFrame: boolean) {
  providerEndFrame = endFrame;
  mount();
  fireEvent.change(screen.getByRole('combobox', { name: '操作' }), { target: { value: 'm7.video.i2v' } });
  fireEvent.click(screen.getByRole('button', { name: '重新读取配置' }));
  const providerSelect = await screen.findByRole('combobox', { name: '服务商与模型' });
  await waitFor(() => expect(providerSelect.querySelectorAll('option').length).toBeGreaterThan(1));
  fireEvent.change(providerSelect, { target: { value: JSON.stringify(['m7.video.i2v', 'http-video', 'frame-model', provider(endFrame).route_digest]) } });
  fireEvent.click(screen.getByLabelText('first.png · v2'));
  fireEvent.change(screen.getByLabelText('本次提示词'), { target: { value: 'first to last camera move' } });
  const tail = screen.getByLabelText(/尾帧（可选）/);
  fireEvent.change(tail, { target: { value: 'asset-last' } });
}
describe('first/last frame video authoring', () => {
  it('binds ordered first/last frame identities into the preview request', async () => {
    await chooseFrames(true);
    fireEvent.click(screen.getByRole('button', { name: '读取制作预览' }));
    await screen.findByRole('region', { name: '制作预览确认' });
    expect(posted).not.toBeNull();
    expect(posted!.source_snapshots).toEqual([source(assets[0]), source(assets[1])]);
    expect(posted!.video_frames).toEqual([{ role: 'FIRST', source: source(assets[0]) }, { role: 'LAST', source: source(assets[1]) }]);
    expect(screen.getByText(/首帧：first.png/)).toBeTruthy();
    fireEvent.change(screen.getByLabelText(/尾帧（可选）/), { target: { value: '' } });
    expect(screen.queryByRole('region', { name: '制作预览确认' })).toBeNull();
  });
  it('shows an explicit rejection instead of silently dropping a tail on a single-image adapter', async () => {
    await chooseFrames(false);
    await waitFor(() => expect(screen.getByText(/当前配置不支持尾帧/)).toBeTruthy());
    expect(posted).toBeNull();
  });
  it('rejects duplicate first/last frames in the command contract', () => {
    const command = { operation_id: 'm7.video.i2v', request_id: 'frame-duplicate', provider_id: 'http-video', model_id: 'frame-model',
      prompt: '', parameters: {}, source_snapshots: [source(assets[0]), source(assets[0])], allow_cloud: false, license_note: '',
      video_frames: [{ role: 'FIRST', source: source(assets[0]) }, { role: 'LAST', source: source(assets[0]) }] } as unknown as MediaCommand;
    return expect(studioProductionClient(project, { sessionToken: '' }).preview(command)).rejects.toThrow();
  });
});
