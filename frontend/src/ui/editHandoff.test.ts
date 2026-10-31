// @vitest-environment jsdom
/**
 * [HERMIA-FE-20261022 W-UX-14] session handoff inbox for EDIT media pool.
 */
import {afterEach, describe, expect, it} from 'vitest';
import {
  clearEditHandoffs,
  editHandoffsForNovel,
  pushEditHandoff,
  readEditHandoffs,
} from './editHandoff';

afterEach(() => clearEditHandoffs());

describe('editHandoff W-UX-14', () => {
  it('starts empty and accepts AUDIO/VIDEO/ASSETS/IMAGE sources', () => {
    expect(readEditHandoffs()).toEqual([]);
    pushEditHandoff({source: 'AUDIO', label: 'a', novelId: 'n1'});
    pushEditHandoff({source: 'VIDEO', label: 'v', novelId: 'n1'});
    pushEditHandoff({source: 'ASSETS', label: 's.mp4', novelId: 'n1'});
    pushEditHandoff({source: 'IMAGE', label: 'img', novelId: 'n2'});
    const all = readEditHandoffs();
    expect(all).toHaveLength(4);
    expect(editHandoffsForNovel('n1')).toHaveLength(3);
    expect(editHandoffsForNovel('n2').map(h => h.source)).toEqual(['IMAGE']);
  });

  it('clearEditHandoffs empties the inbox', () => {
    pushEditHandoff({source: 'AUDIO', label: 'x'});
    clearEditHandoffs();
    expect(readEditHandoffs()).toEqual([]);
  });
});
