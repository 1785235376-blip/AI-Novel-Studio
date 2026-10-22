/** [HERMIA-FE-20261022 N-UX-11] Secondary entries map to existing FL panels only */
import {describe, expect, it} from 'vitest';
import {
  NOVEL_SECONDARY_ENTRIES,
  novelSecondaryEntry,
} from './novelSecondaryEntries';

describe('novelSecondaryEntries (N-UX-11)', () => {
  it('exposes exactly three paths: StoryPlanning / Continuity / PendingCanon', () => {
    expect(NOVEL_SECONDARY_ENTRIES.map(e => e.id)).toEqual([
      'story-planning',
      'continuity',
      'pending-canon',
    ]);
  });

  it('maps to existing FL panels only (story | check) — no new FL ids', () => {
    const panels = new Set(NOVEL_SECONDARY_ENTRIES.map(e => e.panel));
    expect([...panels].sort()).toEqual(['check', 'story']);
    for (const e of NOVEL_SECONDARY_ENTRIES) {
      expect(['story', 'check']).toContain(e.panel);
      expect(e.actionId.startsWith('novel.open.')).toBe(true);
    }
    expect(novelSecondaryEntry('story-planning').panel).toBe('story');
    expect(novelSecondaryEntry('continuity').panel).toBe('check');
    expect(novelSecondaryEntry('pending-canon').panel).toBe('check');
  });
});
