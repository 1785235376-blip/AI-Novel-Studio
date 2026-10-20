// @vitest-environment jsdom
import { cleanup, render, screen, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import type { ProductionRecipe } from './studioProductionClient';
import { StudioExecutionRecipePanel, type StudioExecutionRecipePanelProps } from './StudioExecutionRecipePanel';

const digest = 'b'.repeat(64);
const recipe = (patch: Partial<ProductionRecipe> = {}): ProductionRecipe => ({
  contract: 'studio-execution-recipe/1', operation_id: 'm5.image.i2i', recipe_digest: digest,
  adapter: 'COMFYUI_BUILTIN_IMAGE', automatic_fallback: false, workflow: {
    '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: 'owner-selected-model.safetensors' } },
    '6': { class_type: 'CLIPTextEncode', inputs: { text: 'author text', clip: ['4', 1] } },
    '5': { class_type: 'VAEEncode', inputs: { pixels: ['20', 0], vae: ['4', 2] } },
    '20': { class_type: 'LoadImage', inputs: { image: 'VERIFIED_SOURCE_UPLOAD_RECEIPT' } },
    '3': { class_type: 'KSampler', inputs: { model: ['4', 0], latent_image: ['5', 0], positive: ['6', 0] } },
    '8': { class_type: 'VAEDecode', inputs: { samples: ['3', 0], vae: ['4', 2] } },
    '9': { class_type: 'SaveImage', inputs: { images: ['8', 0] } },
  }, ...patch,
});
const props = (patch: Partial<StudioExecutionRecipePanelProps> = {}): StudioExecutionRecipePanelProps => ({
  recipe: recipe(), operationId: 'm5.image.i2i', current: true, ...patch,
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); vi.restoreAllMocks(); vi.useRealTimers(); });

describe('StudioExecutionRecipePanel readonly evidence', () => {
  it('explains recorded steps, component names, types and origin without marking execution passed', () => {
    const { container } = render(<StudioExecutionRecipePanel {...props()} />);
    const region = screen.getByRole('region', { name: '执行配方说明' });
    expect(within(region).getByText('owner-selected-model.safetensors')).toBeTruthy();
    expect(within(region).getByText('编码文本')).toBeTruthy();
    expect(within(region).getByText('编码图片到潜空间')).toBeTruthy();
    expect(within(region).getByText('采样潜空间')).toBeTruthy();
    expect(within(region).getByText('解码潜空间到图片')).toBeTruthy();
    expect(within(region).getByText('0:MODEL / 1:CLIP / 2:VAE', { exact: false })).toBeTruthy();
    expect(within(region).getByText(digest)).toBeTruthy();
    expect(within(region).getByText(/原 ProductionPreview \/ ProductionJob/)).toBeTruthy();
    expect(within(region).getByText(/实际任务状态请核对原 Job/)).toBeTruthy();
    expect(region.textContent).not.toMatch(/PASS|已执行|推理通过|已验收/);
    expect(container.querySelector('.ui-badge--success')).toBeNull();
    expect(region.style.overflowWrap).toBe('anywhere');
    expect(region.style.maxWidth).toBe('100%');
  });

  it('scrubs all previous contents immediately when current becomes false, then accepts a new current recipe', () => {
    const { container, rerender } = render(<StudioExecutionRecipePanel {...props()} />);
    expect(screen.getByText(digest)).toBeTruthy();
    rerender(<StudioExecutionRecipePanel {...props({ current: false })} />);
    expect(container.innerHTML).toBe('');
    rerender(<StudioExecutionRecipePanel {...props({ recipe: recipe({ recipe_digest: 'c'.repeat(64) }) })} />);
    expect(screen.queryByText(digest)).toBeNull(); expect(screen.getByText('c'.repeat(64))).toBeTruthy();
  });

  it.each([
    { recipe: undefined, message: '执行配方不可用' },
    { recipe: recipe({ recipe_digest: '' }), message: '执行配方信息不完整' },
    { recipe: recipe(), operationId: 'm7.video.t2v', message: '当前操作与配方 operation_id 不一致' },
  ])('renders a clear unavailable state without stale values: $message', ({ message, ...patch }) => {
    const { container } = render(<StudioExecutionRecipePanel {...props(patch)} />);
    expect(screen.getByRole('status').textContent).toContain(message);
    expect(screen.queryByText(digest)).toBeNull(); expect(screen.queryByText('owner-selected-model.safetensors')).toBeNull();
    expect(container.querySelector('.ui-badge--success')).toBeNull();
  });

  it.each(['ORIGINAL_HTTP_PROVIDER', 'AUTOMATIC1111_IMAGE', 'UNKNOWN_ADAPTER'])('keeps %s internals hidden even with a workflow extension', adapter => {
    render(<StudioExecutionRecipePanel {...props({ recipe: recipe({ adapter }) })} />);
    expect(screen.getByText(/内部不可见/)).toBeTruthy();
    expect(screen.queryByRole('list', { name: '原配方步骤' })).toBeNull();
    expect(screen.queryByText('KSampler')).toBeNull(); expect(screen.queryByText('VAEDecode')).toBeNull();
    expect(screen.queryByText('owner-selected-model.safetensors')).toBeNull();
  });

  it('does not label a missing Comfy workflow or unrecognized component as passing', () => {
    const { rerender, container } = render(<StudioExecutionRecipePanel {...props({ recipe: recipe({ workflow: undefined }) })} />);
    expect(screen.getByText(/未提供 workflow/)).toBeTruthy();
    expect(screen.queryByRole('list', { name: '原配方步骤' })).toBeNull();
    rerender(<StudioExecutionRecipePanel {...props({ recipe: recipe({ workflow: {
      '1': { class_type: 'FutureSampler', inputs: { mystery: 'private extension' } },
    } }) })} />);
    expect(screen.getByText('未知步骤 · 执行未验证')).toBeTruthy();
    expect(screen.getByText('UNKNOWN')).toBeTruthy();
    expect(container.textContent).not.toContain('private extension');
    expect(container.querySelector('.ui-badge--success')).toBeNull();
  });

  it('does not request, poll, create a task or render executable controls on mount, time advance or prop change', async () => {
    vi.useFakeTimers();
    const fetch = vi.fn(() => { throw new Error('read-only panel attempted transport'); }); vi.stubGlobal('fetch', fetch);
    const interval = vi.spyOn(globalThis, 'setInterval');
    const { container, rerender } = render(<StudioExecutionRecipePanel {...props()} />);
    await vi.advanceTimersByTimeAsync(60_000);
    rerender(<StudioExecutionRecipePanel {...props({ recipe: recipe({ adapter: 'ORIGINAL_HTTP_PROVIDER' }) })} />);
    expect(fetch).not.toHaveBeenCalled(); expect(interval).not.toHaveBeenCalled();
    expect(container.querySelectorAll('button,input,select,textarea,form,a,img,video,audio')).toHaveLength(0);
  });

  it('renders recorded strings as text and omits arbitrary credentials, route fields and purported job status', () => {
    const { container } = render(<StudioExecutionRecipePanel {...props({ recipe: recipe({ token: 'private-token',
      provider_id: 'unverified-provider', model_id: 'unverified-model', job_status: 'SUCCEEDED', workflow: {
        '4': { class_type: 'CheckpointLoaderSimple', inputs: { ckpt_name: '<script>not-code</script>' } },
      } }) })} />);
    expect(screen.getByText('<script>not-code</script>')).toBeTruthy(); expect(container.querySelector('script')).toBeNull();
    for (const secret of ['private-token', 'unverified-provider', 'unverified-model', 'SUCCEEDED']) expect(container.textContent).not.toContain(secret);
    expect(screen.getByText(/配方未提供 provider_id \/ model_id；见原预览或任务回执/)).toBeTruthy();
  });
});
