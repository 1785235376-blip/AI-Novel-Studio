// [HERMIA-FE-20261022 U1] 4 格不缺右下角：偶数全半宽，奇数末格跨行
import {describe, it, expect} from 'vitest';
import {comicCellSpans} from './ImageRebuild';
describe('comicCellSpans', () => {
  it('fills even counts, spans last on odd', () => {
    expect(comicCellSpans(4)).toEqual([false, false, false, false]);
    expect(comicCellSpans(3)).toEqual([false, false, true]);
    expect(comicCellSpans(1)).toEqual([false]);
  });
});
