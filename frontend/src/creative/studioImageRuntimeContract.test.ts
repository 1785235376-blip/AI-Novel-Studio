import { describe, expect, it } from 'vitest';
import { checkedImageRuntimeInputs, sameImageRuntimeInputs } from './studioImageRuntimeContract';
import type { ProductionSource } from './studioProductionClient';

const source = (id = 'source', version = 2): ProductionSource => ({ id, kind: 'ASSET', asset_kind: 'image', version, digest: 'a'.repeat(64) });
const mask = source('mask');
describe('optional source-bound image runtime inputs', () => {
  it('omits additions for unchanged legacy T2I and I2I request identities', () => {
    expect(checkedImageRuntimeInputs({}, [], 'm5.image.t2i', true)).toEqual({});
    expect(checkedImageRuntimeInputs({}, [source()], 'm5.image.i2i', true)).toEqual({});
    expect(sameImageRuntimeInputs({}, {})).toBe(true);
    expect(sameImageRuntimeInputs({}, { image_references: [] })).toBe(false);
  });
  it('retains explicit ordered weights and exact asset versions', () => {
    const references = [{ source: source(), weight: 0.25 }, { source: source('second'), weight: 1 }];
    const result = checkedImageRuntimeInputs({ image_references: references }, references.map(row => row.source), 'm5.image.reference', true);
    expect(result).toEqual({ image_references: references });
    expect(sameImageRuntimeInputs(result, { image_references: references })).toBe(true);
    expect(sameImageRuntimeInputs(result, { image_references: [...references].reverse() })).toBe(false);
    expect(sameImageRuntimeInputs(result, { image_references: [{ source: source(), weight: 0.5 }, references[1]] })).toBe(false);
  });
  it.each([0, -1, 1.01, Number.NaN, Number.POSITIVE_INFINITY, '1', null])('rejects unsupported weight %s', weight => {
    expect(() => checkedImageRuntimeInputs({ image_references: [{ source: source(), weight }] }, [source()], 'm5.image.reference', true))
      .toThrowError(/图片来源、权重或遮罩绑定无效/);
  });
  it('rejects missing, changed, duplicated, oversized and arbitrary reference inputs', () => {
    const bad = [[], [{ source: source(), weight: 1 }, { source: source(), weight: 2 }],
      Array.from({ length: 6 }, (_, index) => ({ source: source(`source${index}`), weight: 1 })),
      [{ source: source('source', 1), weight: 1 }], [{ source: { ...source(), path: 'external' }, weight: 1 }],
      [{ source: { ...source(), kind: 'CREATIVE_DOCUMENT' }, weight: 1 }], [{ source: source(), weight: 1, model: 'unknown' }]];
    bad.forEach(image_references => expect(() => checkedImageRuntimeInputs({ image_references }, [source()], 'm5.image.reference')).toThrow());
  });
  it('requires a separately versioned mask and rejects mask-as-reference or non-image operations', () => {
    const value = { image_source: source(), mask_source: mask };
    expect(checkedImageRuntimeInputs(value, [source(), mask], 'm5.image.inpaint')).toEqual(value);
    expect(() => checkedImageRuntimeInputs({}, [source()], 'm5.image.inpaint')).toThrow();
    expect(() => checkedImageRuntimeInputs(value, [source(), mask], 'm5.image.i2i')).toThrow();
    expect(() => checkedImageRuntimeInputs(value, [source(), mask], 'm7.video.i2v')).toThrow();
    expect(() => checkedImageRuntimeInputs({ mask_source: mask, image_references: [{ source: mask, weight: 1 }] }, [source(), mask], 'm5.image.inpaint')).toThrow();
    expect(sameImageRuntimeInputs(value, { ...value, mask_source: source('mask', 3) })).toBe(false);
  });
});
