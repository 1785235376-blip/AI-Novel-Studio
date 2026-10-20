import { describe, expect, it } from 'vitest';
import { applyGraphRecipeParameters, checkedGraphRecipeParameters, graphRecipeParameterSupport } from './studioGraphRecipeParameters';
import { samplingDefinition, samplingProvider } from './studioGraphRecipeParameters.testFixtures';

describe('original Graph sampling parameter projection', () => {
  it('patches only the two original parameters, preserving binding, consent, pins and topology without mutation', () => {
    const definition = samplingDefinition(), before = structuredClone(definition);
    definition.nodes.push({ id: 'pin', definition_id: 'asset_reference', definition_version: 1, enabled: true, position: { x: 0, y: 280 }, parameters: { asset_id: 'original-source', version: 3, digest: 'c'.repeat(64), kind: 'image' } });
    const next = applyGraphRecipeParameters(definition, 'generate', samplingProvider(), { steps: '37', seed: '424242' });
    expect(next.nodes[1].parameters).toEqual({ ...before.nodes[1].parameters, parameters: { ...before.nodes[1].parameters.parameters, steps: 37, seed: 424242 } });
    expect(next.nodes[3]).toBe(definition.nodes[3]); expect(next.edges).toBe(definition.edges); expect(definition.nodes[1]).toEqual(before.nodes[1]);
  });
  it('omits explicitly cleared values so the original compiler supplies defaults', () => {
    const next = applyGraphRecipeParameters(samplingDefinition(), 'generate', samplingProvider(), { steps: '', seed: '' });
    expect(next.nodes[1].parameters.parameters).toEqual({ width: 512, height: 512, negative_prompt: 'synthetic negative' });
  });
  it.each([{ steps: '0', seed: '0' }, { steps: '151', seed: '0' }, { steps: '2.5', seed: '0' }, { steps: '1e2', seed: '0' },
    { steps: '20', seed: '-1' }, { steps: '20', seed: '2147483648' }, { steps: '20', seed: 'Infinity' }])('rejects invalid scalar input without touching the graph: %j', fields => {
    const definition = samplingDefinition(), before = structuredClone(definition);
    expect(() => applyGraphRecipeParameters(definition, 'generate', samplingProvider(), fields)).toThrow(); expect(definition).toEqual(before);
  });
  it('accepts the original finite boundary including a real zero seed and rejects additional fields', () => {
    expect(checkedGraphRecipeParameters({ steps: '150', seed: '0' })).toEqual({ steps: 150, seed: 0 });
    expect(() => checkedGraphRecipeParameters({ steps: '20', seed: '7', cfg: '999' } as never)).toThrow();
    expect(() => checkedGraphRecipeParameters({ steps: 20, seed: '7' } as never)).toThrow();
  });
  it.each(['unmatched', 'cloud', 'unknown recipe', 'missing supported scalar'] as const)('keeps unsupported adapter metadata unavailable: %s', kind => {
    const provider = samplingProvider();
    if (kind === 'unmatched') provider.model_id = 'different';
    if (kind === 'cloud') provider.local = false;
    if (kind === 'unknown recipe') provider.image_capabilities!.recipe_id = 'opaque-http';
    if (kind === 'missing supported scalar') provider.supported_parameters = ['steps'];
    expect(graphRecipeParameterSupport(samplingDefinition().nodes[1], provider)).toBeTruthy();
    expect(() => applyGraphRecipeParameters(samplingDefinition(), 'generate', provider, { steps: '37', seed: '424242' })).toThrow();
  });
});
