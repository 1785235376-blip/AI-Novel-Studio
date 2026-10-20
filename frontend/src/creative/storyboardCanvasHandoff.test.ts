import { expect, it } from 'vitest';
import { storyboardCanvasSnapshot } from './storyboardCanvasHandoff';
import { newDocument, type CreativeDocument } from './types';
const source = { id: 'director', version: 1, digest: 'a'.repeat(64) };
const origin: CreativeDocument = { ...newDocument('DIRECTOR'), ...source, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {} };
const board: CreativeDocument = { ...origin, id: 'board', mode: 'STORYBOARD', status: 'DRAFT', source_documents: { director: { version: 1, digest: source.digest } } };
const pin = { id: 'board', version: 1, digest: 'b'.repeat(64) };
it('pins only the exact independent DRAFT and refuses changed digests or ancestry', () => {
  expect(storyboardCanvasSnapshot(board, pin.digest, source, origin, source.digest, pin)).toEqual(pin);
  expect(() => storyboardCanvasSnapshot(board, 'c'.repeat(64), source, origin, source.digest, pin)).toThrow();
  expect(() => storyboardCanvasSnapshot(board, pin.digest, source, origin, 'c'.repeat(64))).toThrow();
  expect(() => storyboardCanvasSnapshot({ ...board, id: source.id }, pin.digest, source, origin, source.digest)).toThrow();
  expect(() => storyboardCanvasSnapshot({ ...board, status: 'APPROVED' }, pin.digest, source, origin, source.digest)).toThrow();
  expect(() => storyboardCanvasSnapshot({ ...board, source_documents: { director: { version: 1, digest: 'c'.repeat(64) } } }, pin.digest, source, origin, source.digest)).toThrow();
});
