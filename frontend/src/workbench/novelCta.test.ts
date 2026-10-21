/** [HERMIA-FE-20261022 N-UX-03] CTA state machine */
import {describe, expect, it} from 'vitest';
import {decideNovelPrimaryCta} from './novelCta';

describe('decideNovelPrimaryCta', () => {
  it('prioritizes adopt > continuity > continue > pick-chapter', () => {
    expect(decideNovelPrimaryCta({draftReady: true, continuityWarningCount: 3, hasChapter: true}))
      .toEqual({kind: 'adopt', label: '采用草稿'});
    expect(decideNovelPrimaryCta({draftReady: false, continuityWarningCount: 2, hasChapter: true}))
      .toEqual({kind: 'continuity', label: '看一致性'});
    expect(decideNovelPrimaryCta({draftReady: false, continuityWarningCount: 0, hasChapter: true}))
      .toEqual({kind: 'continue', label: '继续写'});
    expect(decideNovelPrimaryCta({draftReady: false, hasChapter: false}))
      .toEqual({kind: 'pick-chapter', label: '在左侧选择或新建章节'});
  });
});
