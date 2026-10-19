import { describe, expect, it } from 'vitest';
import { normalizeClipSelection, sameClipSelection, toggleClipSelection } from './clipSelection';

describe('local selection set over the validated visible order', () => {
  const order = ['a1', 'a2', 'b1', 'b2'];
  it('removes duplicates and unknown IDs without expanding the requested subset or mutating inputs', () => {
    const selected = Object.freeze(['b2', 'gone', 'a1', 'a1']);
    expect(normalizeClipSelection(selected, order)).toEqual(['a1', 'b2']);
    expect(selected).toEqual(['b2', 'gone', 'a1', 'a1']);
  });
  it.each([null, undefined, 42, 'a1', {}, [null, {}, 'gone']])('handles malformed view state %j without inventing a selection', input => {
    expect(normalizeClipSelection(input, order)).toEqual([]);
  });
  it('toggles only a current clip and canonicalizes both directions', () => {
    expect(toggleClipSelection(['b2'], 'a1', order)).toEqual(['a1', 'b2']);
    expect(toggleClipSelection(['b2', 'a1'], 'b2', order)).toEqual(['a1']);
    expect(toggleClipSelection(['a1'], 'gone', order)).toEqual(['a1']);
    expect(normalizeClipSelection(['a1'], ['a1', 'a1', 'b1'])).toEqual(['a1']);
  });
  it('detects order, duplication and invalid view state for cleanup', () => {
    expect(sameClipSelection(['a1','b2'], ['a1','b2'])).toBe(true);
    expect(sameClipSelection(['b2','a1'], ['a1','b2'])).toBe(false);
    expect(sameClipSelection(['a1','a1'], ['a1'])).toBe(false);
    expect(sameClipSelection(undefined, [])).toBe(false);
  });
});
