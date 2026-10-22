import { describe, expect, it } from 'vitest';
import { modelCatalog } from '../creative/studioGraphModel.testFixtures';
import { blankGraph } from '../creative/graphDraft';
import {
  ADD_NODE_MIME_ASSET_REF, ADD_NODE_NEEDS_SOURCE, filterAddNodeTypes, graphDisplayExecCounts,
  parseAssetDropPayload, serializeAssetDropPayload,
} from './addNodeMenu';

describe('addNodeMenu [HERMIA-FE-20261022 H-P1-03]', () => {
  it('filters creation vs execution without inventing types', () => {
    const catalog = modelCatalog();
    const draft = blankGraph();
    const creation = filterAddNodeTypes(catalog, draft, 'creation');
    const execution = filterAddNodeTypes(catalog, draft, 'execution');
    expect(creation.some(row => row.entry.id === 'asset_reference' || row.entry.category === 'TEXT' || row.entry.category === 'ASSET')).toBe(true);
    expect(creation.every(row => catalog.definitions.some(def => def.id === row.entry.id))).toBe(true);
    expect(execution.every(row => catalog.definitions.some(def => def.id === row.entry.id))).toBe(true);
    // 创作过滤不应只剩空集
    expect(creation.length).toBeGreaterThan(0);
  });

  it('keeps asset_reference as reference-only and marks source-bound kinds', () => {
    expect(ADD_NODE_NEEDS_SOURCE.has('asset_reference')).toBe(true);
    expect(ADD_NODE_NEEDS_SOURCE.has('text_input')).toBe(false);
  });

  it('parses drag payload as reference pin only', () => {
    const payload = { asset_id: 'a1', version: 2, digest: 'abc', kind: 'image' };
    expect(parseAssetDropPayload(serializeAssetDropPayload(payload))).toEqual(payload);
    expect(parseAssetDropPayload('{')).toBeNull();
    expect(parseAssetDropPayload('')).toBeNull();
    expect(ADD_NODE_MIME_ASSET_REF).toContain('asset-ref');
  });

  it('splits display / frame / executable counts for status honesty', () => {
    const counts = graphDisplayExecCounts(
      [{ definition_id: 'text_input' }, { definition_id: 'asset_reference' }, { definition_id: 'text_generate' }],
      [{ id: 'text_input', executable: true }, { id: 'asset_reference', executable: false }, { id: 'text_generate', executable: true }],
      2,
    );
    expect(counts).toEqual({ display: 3, frame: 2, executable: 2 });
  });
});
