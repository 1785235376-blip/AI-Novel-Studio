/** [HERMIA-FE-20261022 N-UX-08] CTA state machine — three primary states + pick-chapter */
import {describe, expect, it} from 'vitest';
import {countOpenContinuityWarnings, decideNovelPrimaryCta} from './novelCta';

describe('decideNovelPrimaryCta (N-UX-08)', () => {
  it('three author states: 继续写 / 采用草稿 / 看一致性 (adopt > continuity > continue)', () => {
    expect(decideNovelPrimaryCta({draftReady: true, continuityWarningCount: 3, hasChapter: true}))
      .toEqual({kind: 'adopt', label: '采用草稿'});
    expect(decideNovelPrimaryCta({draftReady: false, continuityWarningCount: 2, hasChapter: true}))
      .toEqual({kind: 'continuity', label: '看一致性'});
    expect(decideNovelPrimaryCta({draftReady: false, continuityWarningCount: 0, hasChapter: true}))
      .toEqual({kind: 'continue', label: '继续写'});
  });

  it('cold-start without chapter stays pick-chapter (not media / not fake green)', () => {
    expect(decideNovelPrimaryCta({draftReady: false, hasChapter: false}))
      .toEqual({kind: 'pick-chapter', label: '在左侧选择或新建章节'});
  });
});

describe('countOpenContinuityWarnings (N-UX-08)', () => {
  it('counts only non-RESOLVED rows; empty/null → 0 (honest)', () => {
    expect(countOpenContinuityWarnings(null)).toBe(0);
    expect(countOpenContinuityWarnings([])).toBe(0);
    expect(countOpenContinuityWarnings([
      {status: 'OPEN'},
      {status: 'RESOLVED'},
      {status: 'resolved'},
      {status: 'WARNING'},
      null,
    ])).toBe(2);
  });
});
