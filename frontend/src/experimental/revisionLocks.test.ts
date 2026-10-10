// @vitest-environment jsdom
import { Editor } from '@tiptap/react';
import StarterKit from '@tiptap/starter-kit';
import { expect, it } from 'vitest';
import { RevisionLocks, normalizeRevisionLockDocument } from './revisionLocks';

it('preserves original unlocked external JSON without null attribute pollution', () => {
  const doc = { type: 'doc', content: [{ type: 'paragraph', content: [{ type: 'text', text: '中文🙂é' }] }] };
  const editor = new Editor({ extensions: [StarterKit, RevisionLocks], content: doc });
  expect(normalizeRevisionLockDocument(editor.getJSON())).toEqual(doc);
  editor.destroy();
});
it('keeps real lock and explicit unlock metadata through original TipTap text edits', () => {
  for (const state of ['LOCKED', 'UNLOCKED']) {
    const marker = { state, id: 'stable', digest: 'original', source_version: 3 };
    const editor = new Editor({ extensions: [StarterKit, RevisionLocks], content: { type: 'doc', content: [{ type: 'paragraph', attrs: { aiRevisionLock: marker }, content: [{ type: 'text', text: '原文🙂' }] }] } });
    editor.commands.insertContentAt(1, '手工');
    expect(normalizeRevisionLockDocument(editor.getJSON()).content?.[0].attrs?.aiRevisionLock).toEqual(marker);
    editor.destroy();
  }
});
