// @vitest-environment jsdom
import { cleanup, render, screen } from '@testing-library/react';
import { afterEach, expect, it } from 'vitest';
import { StudioExecutionRecipePanel } from './StudioExecutionRecipePanel';
import { buildStudioExecutionRecipeView } from './studioExecutionRecipeView';
import type { ProductionRecipe } from './studioProductionClient';
afterEach(cleanup);
const recipe = (): ProductionRecipe => ({ contract: 'studio-execution-recipe/1', operation_id: 'm5.image.t2i', adapter: 'COMFYUI_BUILTIN_IMAGE', recipe_digest: 'a'.repeat(64), automatic_fallback: false,
  workflow: { '3': { class_type: 'KSampler', inputs: { seed: 0, steps: 37, cfg: 7, denoise: 0.6 } },
    '6': { class_type: 'CLIPTextEncode', inputs: { text: 'private-author-prompt-sentinel' } },
    '28': { class_type: 'ImageCompositeMasked', inputs: { resize_source: false, x: 0, y: 0 } } } });
it('projects actual finite typed scalar values, preserving zero/false and the source recipe', () => {
  const source = recipe(), before = structuredClone(source), view = buildStudioExecutionRecipeView({ recipe: source, operationId: 'm5.image.t2i', current: true });
  expect(view.steps[0].inputs.find(input => input.name === 'seed')?.recordedValue).toBe(0);
  expect(view.steps[0].inputs.find(input => input.name === 'steps')?.recordedValue).toBe(37);
  expect(view.steps[2].inputs.find(input => input.name === 'resize_source')?.recordedValue).toBe(false);
  expect(JSON.stringify(view)).not.toContain('private-author-prompt-sentinel'); expect(source).toEqual(before);
});
it('renders recorded seed and steps as recipe evidence while retaining the execution-unverified boundary', () => {
  render(<StudioExecutionRecipePanel recipe={recipe()} operationId="m5.image.t2i" current/>);
  const inputs = screen.getByLabelText('节点 3 输入类型');
  expect(inputs.textContent).toContain('seed：INT · 配方记录值 0'); expect(inputs.textContent).toContain('steps：INT · 配方记录值 37');
  expect(screen.getByLabelText('节点 28 输入类型').textContent).toContain('false');
  expect(screen.getByText('执行未验证')).toBeTruthy(); expect(document.body.textContent).not.toContain('private-author-prompt-sentinel');
});
it('never coerces strings, unsafe integer values, non-finite numbers or unknown ports into recorded scalars', () => {
  const value = recipe(); value.workflow = { '3': { class_type: 'KSampler', inputs: { seed: Number.MAX_SAFE_INTEGER + 1, steps: 'not-a-number-sentinel', cfg: Infinity, api_key: 87654321 } } };
  const view = buildStudioExecutionRecipeView({ recipe: value, current: true });
  expect(view.steps[0].inputs.every(input => !Object.hasOwn(input, 'recordedValue'))).toBe(true);
  expect(JSON.stringify(view)).not.toContain('not-a-number-sentinel'); expect(JSON.stringify(view)).not.toContain('87654321');
});
it('hides compiled scalar values for opaque cloud adapters and mismatched operations', () => {
  const value = recipe(); value.adapter = 'ORIGINAL_HTTP_PROVIDER';
  const cloud = buildStudioExecutionRecipeView({ recipe: value, current: true }); expect(cloud.visibility).toBe('hidden'); expect(cloud.steps).toEqual([]);
  expect(buildStudioExecutionRecipeView({ recipe: recipe(), operationId: 'm5.image.i2i', current: true }).steps).toEqual([]);
});
it('does not inspect an expired recipe while adding scalar presentation', () => {
  const value = recipe(); Object.defineProperty(value, 'workflow', { get: () => { throw new Error('stale recipe accessed'); } });
  render(<StudioExecutionRecipePanel recipe={value} current={false}/>); expect(screen.queryByLabelText('执行配方说明')).toBeNull();
});
