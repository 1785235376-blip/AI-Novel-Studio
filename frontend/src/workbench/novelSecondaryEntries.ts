/**
 * [HERMIA-FE-20261022 N-UX-11] Novel secondary discoverability entries.
 * PendingCanon / Continuity / StoryPlanning → existing FL panels only (story | check).
 * [HERMIA-FE-20261022 REBUILD-W3] 作者可见文案改为纯中文。
 * Does NOT invent FeatureLauncher ids. Primary CTA remains N-UX-08 writing state machine.
 */
export type NovelSecondaryEntryId = 'story-planning' | 'continuity' | 'pending-canon';

export type NovelSecondaryEntry = {
  id: NovelSecondaryEntryId;
  /** Author-facing short label on dock secondary CTA. */
  label: string;
  /** Existing FL / panel id only. */
  panel: 'story' | 'check';
  /** DOM anchor after open (data-novel-anchor). */
  anchor: NovelSecondaryEntryId;
  /** Registry action id (commandSearch). */
  actionId: string;
};

export const NOVEL_SECONDARY_ENTRIES: readonly NovelSecondaryEntry[] = [
  {
    id: 'story-planning',
    label: '故事规划',
    panel: 'story',
    anchor: 'story-planning',
    actionId: 'novel.open.storyPlanning',
  },
  {
    id: 'continuity',
    label: '一致性检查',
    panel: 'check',
    anchor: 'continuity',
    actionId: 'novel.open.continuityCheck',
  },
  {
    id: 'pending-canon',
    label: '待审设定',
    panel: 'check',
    anchor: 'pending-canon',
    actionId: 'novel.open.pendingCanon',
  },
] as const;

export function novelSecondaryEntry(id: NovelSecondaryEntryId): NovelSecondaryEntry {
  const found = NOVEL_SECONDARY_ENTRIES.find(e => e.id === id);
  if (!found) throw new Error(`unknown novel secondary entry: ${id}`);
  return found;
}

/** Scroll to in-panel anchor after setPanel; no-op if missing (honest). */
export function scrollNovelSecondaryAnchor(anchor: NovelSecondaryEntryId): void {
  const el = document.querySelector<HTMLElement>(`[data-novel-anchor="${anchor}"]`);
  el?.scrollIntoView?.({block: 'nearest', behavior: 'smooth'});
}
