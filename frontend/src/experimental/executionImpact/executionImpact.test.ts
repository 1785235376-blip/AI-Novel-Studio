import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto, createHash } from 'node:crypto';
import { canonicalExecutionImpact, executionImpactSnapshot, fingerprintExecutionImpact } from './executionImpact';
import { impactInput } from './executionImpact.testFixtures';

beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => vi.unstubAllGlobals());
it('fingerprints the complete JSON wire input with SHA256 and stable object key order', async () => {
  const value = impactInput(), before = canonicalExecutionImpact(value);
  const ordered = Object.fromEntries(Object.entries(value).reverse());
  expect(canonicalExecutionImpact(ordered)).toBe(before);
  expect(await fingerprintExecutionImpact(executionImpactSnapshot(value))).toBe(createHash('sha256').update(before).digest('hex'));
});
it.each(['prompt', 'provider', 'model', 'parameter', 'source version', 'source digest', 'recipe', 'recipe digest', 'scope', 'job version', 'future canvas binding'])('includes %s in the fingerprint', async name => {
  const value = impactInput(), original = await fingerprintExecutionImpact(executionImpactSnapshot(value));
  if (name === 'prompt') value.command.prompt += ' changed';
  if (name === 'provider') value.command.provider_id = 'another-provider';
  if (name === 'model') value.command.model_id = 'another-model';
  if (name === 'parameter') value.command.parameters.seed = 8;
  if (name === 'source version') value.command.source_snapshots[0].version++;
  if (name === 'source digest') value.command.source_snapshots[0].digest = 'e'.repeat(64);
  if (name === 'recipe') value.recipe!.parameters = { steps: 37, seed: 100 };
  if (name === 'recipe digest') value.recipe!.recipe_digest = 'e'.repeat(64);
  if (name === 'scope') value.scope.incarnation = 'next-incarnation';
  if (name === 'job version') value.previousJob!.version++;
  if (name === 'future canvas binding') Object.assign(value.command, { canvas_return: { contract: 'synthetic-canvas-return/1', card_id: 'exact-card' } });
  expect(await fingerprintExecutionImpact(executionImpactSnapshot(value))).not.toBe(original);
});
it('reports real parameter and source pin differences without changing or filling the original request', () => {
  const input = impactInput();input.command.parameters.steps = 37;input.command.source_snapshots[0].version = 2;
  const original = structuredClone(input), view = executionImpactSnapshot(input);
  expect(view.differences).toContainEqual({ path: 'command.parameters.steps', before: '20', after: '37', changed: true });
  expect(view.differences).toContainEqual({ path: 'command.source_snapshots[0].version', before: '1', after: '2', changed: true });
  expect(input).toEqual(original);
});
it('keeps missing previous values unknown and does not infer a missing recipe from the old job', () => {
  const value = impactInput();delete value.previousJob;delete value.recipe;
  const view = executionImpactSnapshot(value);expect(view.previousCommandAvailable).toBe(false);expect(view.recipeAvailable).toBe(false);
  expect(view.differences.length).toBeGreaterThan(0);expect(view.differences.every(row => row.changed === null)).toBe(true);
});
it.each(['project', 'branch', 'incarnation', 'scope'])('rejects missing or mismatched %s context', name => {
  const value = impactInput();
  if (name === 'project') value.previousJob!.novel_id = 'other-project';
  if (name === 'branch') value.previousJob!.branch_id = 'other-branch';
  if (name === 'incarnation') value.scope.incarnation = '';
  if (name === 'scope') (value as unknown as {scope:unknown}).scope = undefined;
  expect(() => executionImpactSnapshot(value)).toThrow('输入范围');
});
it.each([NaN, Infinity, new Date(), () => true])('rejects a non-JSON value instead of omitting it', value => {
  expect(() => canonicalExecutionImpact({value})).toThrow();
});
it('rejects circular input and preserves source array ordering', () => {
  const cyclic: Record<string, unknown> = {};cyclic.self = cyclic;expect(() => canonicalExecutionImpact(cyclic)).toThrow();
  expect(canonicalExecutionImpact([1, 2])).not.toBe(canonicalExecutionImpact([2, 1]));
});
