import { describe, expect, it } from 'vitest';

import {
  beginSubmit, clearDraftMarker, confirmSaved, discardDraft, editDraft, emptyContent,
  hasUnconfirmedWork, markConflict, markUnknown, markerNotice, newDraft, readDraftMarker,
  rememberDraftMarker, retryUnknown,
} from './promptDraft';

const allocate = () => 'req-1';

describe('draft state machine', () => {
  it('tracks the four required states distinctly', () => {
    let draft = newDraft('d1');
    expect(draft.state).toBe('CLEAN');
    expect(hasUnconfirmedWork(draft)).toBe(false);

    draft = editDraft(draft, { text: '一个瘦高的男人站在雨里\n🙂' });
    expect(draft.state).toBe('DIRTY');
    expect(hasUnconfirmedWork(draft)).toBe(true);

    draft = beginSubmit(draft, allocate);
    expect(draft.state).toBe('SUBMITTING');

    draft = confirmSaved(draft, { familyId: 'fam-1', assetId: 'asset-1', revision: 1, idempotentReplay: false });
    expect(draft.state).toBe('SAVED');
    expect(hasUnconfirmedWork(draft)).toBe(false);
    expect(draft.baseRevision).toBe(1);
    expect(draft.requestId).toBeNull();
  });

  it('preserves CJK, newlines and emoji exactly through the machine', () => {
    const text = '第一行\n\n  缩进 emoji 🙂🙂 结尾\n';
    let draft = editDraft(newDraft('d1'), { text });
    draft = beginSubmit(draft, allocate);
    draft = markUnknown(draft, '超时');
    expect(draft.content.text).toBe(text);
  });

  it('allocates the request id once and reuses it on retry', () => {
    let calls = 0;
    const counting = () => { calls += 1; return `req-${calls}`; };
    let draft = editDraft(newDraft('d1'), { text: 'x' });
    draft = beginSubmit(draft, counting);
    const first = draft.requestId;
    // A second begin while in flight must not allocate again.
    draft = beginSubmit(draft, counting);
    expect(draft.requestId).toBe(first);

    draft = markUnknown(draft, '响应丢失');
    expect(draft.state).toBe('UNKNOWN');
    // Retrying reuses the SAME id: changing it would genuinely create a second revision.
    draft = retryUnknown(draft);
    expect(draft.state).toBe('SUBMITTING');
    expect(draft.requestId).toBe(first);
    expect(calls).toBe(1);
  });

  it('an unknown outcome never clears or silently edits the pending content', () => {
    let draft = editDraft(newDraft('d1'), { text: '待确认内容' });
    draft = beginSubmit(draft, allocate);
    draft = markUnknown(draft, '超时');
    const frozen = draft;
    // Typing while the outcome is unknown must not mutate the pending submission.
    expect(editDraft(draft, { text: '别的' })).toEqual(frozen);
    expect(hasUnconfirmedWork(draft)).toBe(true);
  });

  it('keeps the draft on conflict so a 409 cannot lose the user content', () => {
    let draft = editDraft(newDraft('d1'), { text: '我的草稿' });
    draft = beginSubmit(draft, allocate);
    draft = markConflict(draft, 'PROMPT_REVISION_STALE', '有人保存了更新的修订。');
    expect(draft.state).toBe('CONFLICT');
    expect(draft.content.text).toBe('我的草稿');
    expect(draft.conflictCode).toBe('PROMPT_REVISION_STALE');
    expect(hasUnconfirmedWork(draft)).toBe(true);
  });

  it('only a user action discards local content', () => {
    let draft = editDraft(newDraft('d1'), { text: '内容' });
    draft = markConflict(draft, 'PROMPT_REVISION_STALE', '冲突');
    expect(draft.content.text).toBe('内容');
    draft = discardDraft(draft);
    expect(draft.content).toEqual(emptyContent());
    expect(draft.state).toBe('CLEAN');
  });

  it('reports a replay as a replay rather than a new revision', () => {
    let draft = editDraft(newDraft('d1'), { text: 'x' });
    draft = beginSubmit(draft, allocate);
    draft = confirmSaved(draft, { familyId: 'fam-1', assetId: 'asset-1', revision: 2, idempotentReplay: true });
    expect(draft.message).toContain('没有重复创建');
  });
});

describe('reload marker (no prompt text is ever persisted)', () => {
  const storage = () => {
    const map = new Map<string, string>();
    return {
      getItem: (key: string) => map.get(key) ?? null,
      setItem: (key: string, value: string) => { map.set(key, value); },
      removeItem: (key: string) => { map.delete(key); },
      dump: () => [...map.values()].join('\n'),
    };
  };

  it('stores no prompt text, only a bounded content-free marker', () => {
    const store = storage();
    expect(rememberDraftMarker('p1', { familyId: 'fam-1', baseRevision: 1, requestId: 'req-1' }, store)).toBe(true);
    expect(store.dump()).not.toContain('一个瘦高的男人');
    expect(JSON.parse(store.dump())).toEqual({
      schema: 1, mode: 'local', actor: 'local-author', project_id: 'p1',
      family_id: 'fam-1', base_revision: 1, request_id: 'req-1',
    });
  });

  it('tells the user plainly that a reload cannot restore the text', () => {
    const store = storage();
    rememberDraftMarker('p1', { familyId: 'fam-1', baseRevision: null, requestId: null }, store);
    const marker = readDraftMarker('p1', store);
    expect(marker.state).toBe('EXISTS');
    const notice = markerNotice(marker)!;
    expect(notice).toContain('无法恢复');
    expect(notice).not.toContain('已恢复');
  });

  it('rejects a tampered or foreign marker instead of trusting it', () => {
    const store = storage();
    store.setItem('studio.prompt-draft-marker.v1:local-author:file', JSON.stringify({ schema: 1, mode: 'cloud' }));
    expect(readDraftMarker('p1', store).state).toBe('INVALID');
    const other = storage();
    rememberDraftMarker('p2', { familyId: 'fam-1', baseRevision: 1, requestId: null }, other);
    expect(readDraftMarker('p1', other).state).toBe('EMPTY');
    const extra = storage();
    extra.setItem('studio.prompt-draft-marker.v1:local-author:file',
      JSON.stringify({ schema: 1, mode: 'local', actor: 'local-author', project_id: 'p1', text: '泄漏' }));
    expect(readDraftMarker('p1', extra).state).toBe('INVALID');
  });

  it('clears the marker once the work is confirmed saved', () => {
    const store = storage();
    rememberDraftMarker('p1', { familyId: 'fam-1', baseRevision: 1, requestId: 'r' }, store);
    expect(readDraftMarker('p1', store).state).toBe('EXISTS');
    clearDraftMarker(store);
    expect(readDraftMarker('p1', store).state).toBe('EMPTY');
    expect(markerNotice(readDraftMarker('p1', store))).toBeNull();
  });

  it('reports unavailable storage instead of pretending there is no draft', () => {
    const broken = { getItem: () => { throw new Error('blocked'); } };
    expect(readDraftMarker('p1', broken).state).toBe('UNAVAILABLE');
  });
});
