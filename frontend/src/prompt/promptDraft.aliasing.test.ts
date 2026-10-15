/**
 * R3-U3 §3.1 —— 待提交快照的**引用独立**。
 *
 * `{ ...content }` 只做浅拷贝：数组仍与 content 共享引用，外部 push/splice 或复用同一个
 * 数组对象会改变“已经发出的请求”的含义。这些用例针对数组，而不是只测 text 字符串。
 */
import { describe, expect, it } from 'vitest';

import {
  beginSubmit, clearAllStashedDrafts, cloneContent, editDraft, emptyContent, newDraft,
  pendingMatchesContent, stashDraft, takeDraft,
} from './promptDraft';

const allocate = () => 'req-1';

describe('R3-U3 pending snapshot array independence', () => {
  it('does not share array references with the content that was submitted', () => {
    const chars = ['c1'];
    let draft = editDraft(newDraft('d1'), { text: 'x', characterIds: chars });
    draft = beginSubmit(draft, allocate);
    // A caller (or a stale component closure) mutates the array it still holds.
    chars.push('c2');
    expect(draft.pending?.characterIds).toEqual(['c1']);
    expect(draft.content.characterIds).toEqual(['c1']);
  });

  it('does not share array references between content and the pending snapshot', () => {
    let draft = editDraft(newDraft('d1'), { text: 'x' });
    draft = beginSubmit(draft, allocate);
    draft.pending!.characterIds.push('injected');
    expect(draft.content.characterIds).toEqual([]);
  });

  it('keeps every binding list independent, not just characters', () => {
    const draft = editDraft(newDraft('d1'), {
      text: 'x', characterIds: ['c1'], sceneIds: ['s1'], shotIds: ['sh1'],
      referenceAssetIds: ['a1'],
    });
    const submitted = beginSubmit(draft, allocate);
    for (const [key, value] of Object.entries({
      characterIds: 'c2', sceneIds: 's2', shotIds: 'sh2', referenceAssetIds: 'a2',
    })) {
      (draft.content[key as keyof typeof draft.content] as string[]).push(value);
      expect(submitted.pending?.[key as keyof typeof submitted.content]).toHaveLength(1);
    }
  });

  it('detects a divergence caused by an external mutation', () => {
    let draft = editDraft(newDraft('d1'), { text: 'x', characterIds: ['c1'] });
    draft = beginSubmit(draft, allocate);
    expect(pendingMatchesContent(draft)).toBe(true);
    // Even if something forces the content array to diverge, it is detected rather than
    // silently treated as the submitted payload.
    const diverged = { ...draft, content: { ...draft.content, characterIds: ['c1', 'c9'] } };
    expect(pendingMatchesContent(diverged)).toBe(false);
  });

  it('editDraft copies the arrays it is given', () => {
    const incoming = ['c1'];
    const draft = editDraft(newDraft('d1'), { text: 'x', characterIds: incoming });
    incoming.push('c2');
    expect(draft.content.characterIds).toEqual(['c1']);
  });

  it('cloneContent copies every array and the scalars', () => {
    const source = { ...emptyContent(), text: 't', characterIds: ['a'], sceneIds: ['b'],
      shotIds: ['c'], referenceAssetIds: ['d'] };
    const copy = cloneContent(source);
    expect(copy).toEqual(source);
    expect(copy.characterIds).not.toBe(source.characterIds);
    expect(copy.sceneIds).not.toBe(source.sceneIds);
    expect(copy.shotIds).not.toBe(source.shotIds);
    expect(copy.referenceAssetIds).not.toBe(source.referenceAssetIds);
  });
});

describe('R3-U3 session draft store isolation', () => {
  it('does not alias the stored draft with the caller object', () => {
    clearAllStashedDrafts();
    let draft = editDraft(newDraft('d1'), { text: 'original', characterIds: ['c1'] });
    draft = beginSubmit(draft, allocate);
    stashDraft('p1', null, 'author-a', draft);

    // Mutating the caller's copy must not reach into the store.
    draft.content.characterIds.push('injected');
    draft.pending!.characterIds.push('injected');
    const taken = takeDraft('p1', null, 'author-a', 'd1')!;
    expect(taken.content.characterIds).toEqual(['c1']);
    expect(taken.pending?.characterIds).toEqual(['c1']);

    // And mutating the taken copy must not reach back either.
    taken.content.characterIds.push('again');
    expect(takeDraft('p1', null, 'author-a', 'd1')!.content.characterIds).toEqual(['c1']);
  });

  it('isolates drafts by project, branch and actor', () => {
    clearAllStashedDrafts();
    const draft = editDraft(newDraft('d1'), { text: 'author-a 的私有正文' });
    stashDraft('p1', 'main', 'author-a', draft);
    expect(takeDraft('p1', 'main', 'author-a', 'd1')?.content.text).toBe('author-a 的私有正文');
    // A different actor, project or branch must never see it.
    expect(takeDraft('p1', 'main', 'author-b', 'd1')).toBeNull();
    expect(takeDraft('p2', 'main', 'author-a', 'd1')).toBeNull();
    expect(takeDraft('p1', 'other', 'author-a', 'd1')).toBeNull();
    clearAllStashedDrafts();
  });
});
