import { afterEach, describe, expect, it } from 'vitest';
import { beginSubmit, clearAllStashedDrafts, clearDraftSlot, confirmSaved, editDraft,
  markUnknown, newDraft, settleStashedDraft, stashDraft, takeDraft } from './promptDraft';
import type { DraftContent } from './promptDraft';

const submitted = () => beginSubmit({ ...editDraft(newDraft('A'), { text: 'frozen text',
  characterIds: ['character-1'] }), familyId: 'A', baseAssetId: 'A-1', baseRevision: 1 }, () => 'request-1');
const saved = (draft: ReturnType<typeof submitted>) => confirmSaved(draft, {
  familyId: 'A', assetId: 'A-2', revision: 2, idempotentReplay: false,
});
afterEach(clearAllStashedDrafts);

describe('exact session-slot settlement', () => {
  it('settles the exact frozen operation and retains isolated copies', () => {
    const operation = submitted();
    stashDraft('p', 'b', 'actor', operation);
    expect(settleStashedDraft('p', 'b', 'actor', operation, saved)).toBe(true);
    expect(takeDraft('p', 'b', 'actor', 'A')).toMatchObject({ state: 'SAVED',
      baseAssetId: 'A-2', baseRevision: 2, requestId: null, content: { text: 'frozen text' } });
    operation.content.characterIds.push('later');
    expect(takeDraft('p', 'b', 'actor', 'A')?.content.characterIds).toEqual(['character-1']);
    expect(settleStashedDraft('p', 'b', 'actor', operation, saved)).toBe(false);
  });

  it.each(['project', 'branch', 'actor', 'request', 'snapshot', 'base', 'deleted', 'replaced'])
    ('refuses %s mismatch without recreating or replacing the slot', kind => {
      const operation = submitted();
      const current = submitted();
      if (kind === 'request') current.requestId = 'request-2';
      if (kind === 'snapshot') {
        current.content.text = 'other snapshot';
        current.pending!.text = 'other snapshot';
      }
      if (kind === 'base') current.baseRevision = 7;
      stashDraft('p', 'b', 'actor', kind === 'replaced' ? editDraft(newDraft('A'), { text: 'replacement' }) : current);
      if (kind === 'deleted') clearDraftSlot('p', 'b', 'actor', 'A');
      const before = takeDraft('p', 'b', 'actor', 'A');
      expect(settleStashedDraft(kind === 'project' ? 'other' : 'p', kind === 'branch' ? 'other' : 'b',
        kind === 'actor' ? 'other' : 'actor', operation, saved)).toBe(false);
      expect(takeDraft('p', 'b', 'actor', 'A')).toEqual(before);
    });

  it('settles a reconciled UNKNOWN slot only with the same frozen request', () => {
    const operation = submitted();
    stashDraft('p', null, 'actor', markUnknown(operation, 'awaiting receipt'));
    expect(settleStashedDraft('p', null, 'actor', operation, saved)).toBe(true);
    expect(takeDraft('p', null, 'actor', 'A')?.state).toBe('SAVED');
  });

  const changedContent: DraftContent = { text: 'different', negativePrompt: 'different',
    purpose: 'VIDEO', modelReference: 'other-model', parameters: '{"other":true}', seed: '42',
    characterIds: ['other'], sceneIds: ['other'], shotIds: ['other'], referenceAssetIds: ['other'],
    changeNote: 'different', changeReason: 'different' };
  it.each(Object.keys(changedContent) as (keyof DraftContent)[])
    ('refuses a self-consistent but different frozen %s', field => {
      const operation = submitted();
      const current = submitted();
      current.content = { ...current.content, [field]: changedContent[field] };
      current.pending = { ...current.content };
      stashDraft('p', null, 'actor', current);
      expect(settleStashedDraft('p', null, 'actor', operation, saved)).toBe(false);
      expect(takeDraft('p', null, 'actor', 'A')).toEqual(current);
    });

  it.each(['familyId', 'baseAssetId', 'key', 'pending'] as const)
    ('refuses a different submitted %s', field => {
      const operation = submitted();
      stashDraft('p', null, 'actor', operation);
      if (field === 'pending') operation.pending!.text = 'corrupted pending';
      else operation[field] = 'other';
      expect(settleStashedDraft('p', null, 'actor', operation, saved)).toBe(false);
      expect(takeDraft('p', null, 'actor', 'A')?.state).toBe('SUBMITTING');
    });

  it('does not promote a new prompt over an occupied destination family', () => {
    const operation = beginSubmit(editDraft(newDraft('new'), { text: 'new prompt' }), () => 'request-new');
    const destination = editDraft(newDraft('A'), { text: 'existing family draft' });
    stashDraft('p', null, 'actor', operation);
    stashDraft('p', null, 'actor', destination);
    expect(settleStashedDraft('p', null, 'actor', operation, saved)).toBe(false);
    expect(takeDraft('p', null, 'actor', 'A')).toEqual(destination);
    expect(takeDraft('p', null, 'actor', 'new')).toEqual(operation);
  });
});
