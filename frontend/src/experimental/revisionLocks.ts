import { Extension } from '@tiptap/react';

// Preserve server-owned application lock metadata through ordinary TipTap JSON
// edits. This intentionally adds no fake disabled styling or OS-lock promise.
// HTML imports cannot create these attributes; the original server document can.
export const RevisionLocks = Extension.create({
  name: 'revisionLocks',
  addGlobalAttributes() {
    return [{ types: ['paragraph', 'heading', 'codeBlock'], attributes: {
      aiRevisionLock: { default: null, rendered: false, parseHTML: () => null },
    } }];
  },
});

// Canonical unlocked JSON must remain byte-shape compatible with pre-extension
// saved documents. Preserve all real markers, including explicit tombstones.
export function normalizeRevisionLockDocument<T extends { attrs?: Record<string, any>; content?: any[] }>(document: T): T {
  const value = { ...document };
  if (value.attrs?.aiRevisionLock === null) {
    value.attrs = { ...value.attrs }; delete value.attrs.aiRevisionLock;
    if (!Object.keys(value.attrs).length) delete value.attrs;
  }
  if (value.content) value.content = value.content.map(normalizeRevisionLockDocument);
  return value;
}
