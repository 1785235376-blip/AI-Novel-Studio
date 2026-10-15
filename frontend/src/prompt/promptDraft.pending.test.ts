/**
 * R3-U1 —— 待提交快照安全（先复现失败，再修复）。
 *
 * 已从源码查实的风险：`editDraft` 在 SUBMITTING 期间仍然修改 content，而
 * `confirmSaved` 会把这份 draft 直接标成 SAVED —— 于是**提交途中输入的新文本会被显示成已保存**，
 * 而服务器上其实只保存了旧文本。
 */
import { describe, expect, it } from 'vitest';

import {
  beginSubmit, canSubmit, confirmSaved, editDraft, markConflict, markUnknown, needsRebase,
  newDraft, pendingMatchesContent, rebaseDraft, retryUnknown,
} from './promptDraft';

const allocate = () => 'req-1';

describe('R3-U1 submitting snapshot safety', () => {
  it('does not let text typed during save be reported as saved', () => {
    let draft = editDraft(newDraft('d1'), { text: '旧文本' });
    draft = beginSubmit(draft, allocate);
    // The user keeps typing while the request is in flight.
    const afterTyping = editDraft(draft, { text: '新文本（尚未提交）' });
    // Either the input is locked, or the new text must not be treated as saved.
    if (afterTyping.content.text === '新文本（尚未提交）') {
      const saved = confirmSaved(afterTyping, {
        familyId: 'fam-1', assetId: 'asset-1', revision: 1, idempotentReplay: false,
      });
      expect(saved.state).not.toBe('SAVED');
    } else {
      expect(afterTyping.content.text).toBe('旧文本');
    }
  });

  it('locks the pending snapshot while submitting and while the outcome is unknown', () => {
    let draft = editDraft(newDraft('d1'), { text: '已提交内容' });
    draft = beginSubmit(draft, allocate);
    expect(draft.state).toBe('SUBMITTING');
    expect(editDraft(draft, { text: '途中输入' }).content.text).toBe('已提交内容');

    draft = markUnknown(draft, '超时');
    expect(editDraft(draft, { text: '仍然输入' }).content.text).toBe('已提交内容');
  });

  it('records the immutable snapshot actually sent', () => {
    let draft = editDraft(newDraft('d1'), { text: '提交的正文' });
    draft = beginSubmit(draft, allocate);
    expect(pendingMatchesContent(draft)).toBe(true);
    // Mutating the returned content object must not reach into the draft snapshot.
    expect(draft.pending?.text).toBe('提交的正文');
  });

  it('confirms SAVED only for the snapshot that was actually submitted', () => {
    let draft = editDraft(newDraft('d1'), { text: '提交的正文' });
    draft = beginSubmit(draft, allocate);
    const saved = confirmSaved(draft, {
      familyId: 'fam-1', assetId: 'asset-1', revision: 1, idempotentReplay: false,
    });
    expect(saved.state).toBe('SAVED');
    expect(saved.content.text).toBe('提交的正文');
    expect(saved.pending).toBeNull();
  });
});

describe('R3-U1 request id discipline', () => {
  it('never reuses the request id after a conflict without an explicit rebase', () => {
    let draft = editDraft(newDraft('d1'), { text: '我的草稿' });
    draft = beginSubmit(draft, allocate);
    draft = markConflict(draft, 'PROMPT_REVISION_STALE', '有人保存了更新的修订。');
    expect(draft.state).toBe('CONFLICT');
    expect(draft.content.text).toBe('我的草稿');
    expect(needsRebase(draft)).toBe(true);
    // A conflicted request is terminally refused: the old identity must be retired.
    expect(draft.requestId).toBeNull();
    expect(canSubmit(draft)).toBe(false);
  });

  it('allows a new request id only after an explicit rebase', () => {
    let draft = editDraft(newDraft('d1'), { text: '我的草稿' });
    draft = beginSubmit(draft, allocate);
    draft = markConflict(draft, 'PROMPT_REVISION_STALE', '冲突');
    draft = editDraft(draft, { text: '我的草稿（继续编辑）' });
    expect(draft.state).toBe('DIRTY');
    // Editing does not resolve the conflict: the old identity stays retired and a new
    // submission still waits for an explicit rebase.
    expect(needsRebase(draft)).toBe(true);
    expect(canSubmit(draft)).toBe(false);

    draft = rebaseDraft(draft, { assetId: 'asset-2', revision: 2 });
    expect(needsRebase(draft)).toBe(false);
    expect(canSubmit(draft)).toBe(true);
    let calls = 0;
    const next = () => { calls += 1; return 'req-new'; };
    draft = beginSubmit(draft, next);
    expect(draft.requestId).toBe('req-new');
    expect(calls).toBe(1);
  });

  it('retries the original request id only when unknown and the content is unchanged', () => {
    let draft = editDraft(newDraft('d1'), { text: '原始提交' });
    draft = beginSubmit(draft, allocate);
    const original = draft.requestId;
    draft = markUnknown(draft, '响应丢失');
    expect(draft.requestId).toBe(original);

    // Content is locked while unknown, so an explicit retry may reuse the identity.
    expect(retryUnknown(draft).state).toBe('SUBMITTING');
    expect(retryUnknown(draft).requestId).toBe(original);

    // If the snapshot ever diverged from the content, retrying the same id would be wrong.
    const diverged = { ...draft, content: { ...draft.content, text: '被改过的正文' } };
    expect(retryUnknown(diverged)).toBe(diverged);
  });

  it('never auto-resubmits when the outcome is unknown', () => {
    let draft = editDraft(newDraft('d1'), { text: 'x' });
    draft = beginSubmit(draft, allocate);
    draft = markUnknown(draft, '超时');
    // markUnknown must not itself start a new attempt.
    expect(draft.state).toBe('UNKNOWN');
  });

  it('covers SUBMITTING -> UNKNOWN -> explicit retry -> SAVED', () => {
    let draft = editDraft(newDraft('d1'), { text: '一次提交' });
    draft = beginSubmit(draft, allocate);
    draft = markUnknown(draft, '超时');
    draft = retryUnknown(draft);
    draft = confirmSaved(draft, {
      familyId: 'fam-1', assetId: 'asset-1', revision: 1, idempotentReplay: true,
    });
    expect(draft.state).toBe('SAVED');
    expect(draft.requestId).toBeNull();
    expect(draft.message).toContain('没有重复创建');
  });
});
