import { expect, it } from 'vitest';
import { researchEvidenceLocation } from './researchEvidenceLocation';
import type { Source, Evidence } from './researchLibraryClient';
const citation = { source_id: 's', source_version: 2, paragraph: 22, quote_sha256: 'a'.repeat(64) };
const evidence: Evidence = { citation, title: 'source', author: '', source: '', page: 3, paragraph: 22, text: '🌊e\u0301\n港口' };
const source: Source = { access: 'PRIVATE', paragraph_count: 2, id: 's', version: 2, title: 's', author: '', source: '', source_version: '', usage_notes: '', origin: 'LOCAL_IMPORT', format: 'TXT', filename: 's.txt', accessed_at: '', extraction_status: 'TEXT_EXTRACTED', warnings: [], paragraphs: [{ paragraph: 1, page: 3, text: evidence.text, citation: { ...citation, paragraph: 1 } }, { paragraph: 22, page: 3, text: evidence.text, citation }] };
it('uses exact identity among duplicate Unicode text without normalizing or offset guessing', () => {
  expect(researchEvidenceLocation(source, evidence)).toBe(1);
  expect(researchEvidenceLocation(source, { ...evidence, text: evidence.text.normalize('NFC') })).toBeUndefined();
});
it.each([
  { version: 3 }, { id: 'other' }, { version: undefined }, { status: 'DELETED' },
  { paragraphs: [] }, { paragraphs: [...source.paragraphs!, source.paragraphs![1]] },
  { paragraphs: [{ ...source.paragraphs![1], page: 4 }] },
  { paragraphs: [{ ...source.paragraphs![1], citation: { ...citation, quote_sha256: 'b'.repeat(64) } }] },
])('rejects stale, unknown, ambiguous or mismatched original source %j', change => {
  expect(researchEvidenceLocation({ ...source, ...change } as Source, evidence)).toBeUndefined();
});
it('keeps page-only matching distinct from understood text', () => {
  const ref = { ...citation, paragraph: 0, page: 7 };
  const pageEvidence = { ...evidence, citation: ref, paragraph: 0, page: 7, not_understood: true, text: '' };
  const image = { ...source, paragraphs: [], page_citations: [ref] };
  expect(researchEvidenceLocation(image, pageEvidence)).toBe(-1);
  expect(researchEvidenceLocation(image, { ...pageEvidence, not_understood: false })).toBeUndefined();
  expect(researchEvidenceLocation({ ...image, page_citations: [ref, ref] }, pageEvidence)).toBeUndefined();
});

it.each([null, {}, { ...source, paragraphs: {} }, { ...source, paragraphs: [null] },
  { ...source, paragraphs: [{ ...source.paragraphs![1], citation: undefined }] },
  { ...source, paragraphs: [{ ...source.paragraphs![1], page: -1 }] },
  { ...source, page_citations: {} }, { ...source, warnings: null }, { ...source, title: {} },
])('withholds malformed original-source responses without throwing %j', malformed => {
  expect(researchEvidenceLocation(malformed, evidence)).toBeUndefined();
});
it.each([null, {}, { ...evidence, citation: null }, { ...evidence, page: -1 },
  { ...evidence, page: '3' }, { ...evidence, text: {} },
])('withholds malformed evidence without throwing %j', malformed => {
  expect(researchEvidenceLocation(source, malformed)).toBeUndefined();
});
