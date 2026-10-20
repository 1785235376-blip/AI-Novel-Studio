import type { Citation, Evidence, Source } from './researchLibraryClient';

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const positive = (value: unknown, max = Number.MAX_SAFE_INTEGER): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value > 0 && value <= max;
const page = (value: unknown) => value === null || positive(value, 1000);
function citation(value: unknown): value is Citation {
  return record(value) && typeof value.source_id === 'string' && !!value.source_id
    && positive(value.source_version) && typeof value.paragraph === 'number'
    && Number.isSafeInteger(value.paragraph) && value.paragraph >= 0 && value.paragraph <= 5000
    && typeof value.quote_sha256 === 'string' && /^[a-f0-9]{64}$/.test(value.quote_sha256)
    && (value.paragraph === 0 ? positive(value.page, 1000) : value.page === undefined);
}
export function sameResearchCitation(a: unknown, b: unknown): boolean {
  return citation(a) && citation(b) && a.source_id === b.source_id && a.source_version === b.source_version
    && a.paragraph === b.paragraph && a.page === b.page && a.quote_sha256 === b.quote_sha256;
}
export function isResearchEvidence(value: unknown): value is Evidence {
  return record(value) && citation(value.citation) && value.paragraph === value.citation.paragraph
    && page(value.page) && ['title', 'author', 'source', 'text'].every(key => typeof value[key] === 'string')
    && (value.not_understood === undefined || typeof value.not_understood === 'boolean')
    && (value.citation.paragraph === 0 ? value.page === value.citation.page && value.not_understood === true && value.text === ''
      : value.not_understood !== true && typeof value.text === 'string' && value.text.length > 0);
}
export function isResearchSource(value: unknown): value is Source {
  return record(value) && ['id', 'title', 'author', 'source', 'source_version', 'usage_notes', 'origin', 'format', 'filename', 'accessed_at', 'extraction_status'].every(key => typeof value[key] === 'string')
    && positive(value.version) && (value.status === undefined || value.status === 'ACTIVE')
    && Array.isArray(value.warnings) && value.warnings.every(item => typeof item === 'string')
    && Array.isArray(value.paragraphs) && value.paragraphs.length <= 5000
    && value.paragraphs.every(row => record(row) && positive(row.paragraph, 5000) && page(row.page)
      && typeof row.text === 'string' && citation(row.citation) && row.citation.paragraph === row.paragraph)
    && (value.page_citations === undefined || (Array.isArray(value.page_citations) && value.page_citations.length <= 1000
      && value.page_citations.every(row => citation(row) && row.paragraph === 0)));
}

// Owner paragraph identities, never text search or UTF-16/normalized offsets.
// Page-only references identify an unread page, not extracted content.
export function researchEvidenceLocation(source: unknown, evidence: unknown): number | undefined {
  if (!isResearchSource(source) || !isResearchEvidence(evidence)) return;
  const ref = evidence.citation;
  if (source.id !== ref.source_id || source.version !== ref.source_version) return;
  if (ref.paragraph === 0) {
    if (evidence.page !== ref.page || evidence.not_understood !== true || evidence.text !== '') return;
    const matches = source.page_citations?.filter(row => row.paragraph === 0 && row.page === ref.page) || [];
    return matches.length === 1 && sameResearchCitation(matches[0], ref) ? -1 : undefined;
  }
  if (evidence.not_understood || !evidence.text) return;
  const paragraphs = source.paragraphs!;
  const matches = paragraphs.filter(row => row.paragraph === ref.paragraph);
  if (matches.length !== 1) return;
  const paragraph = matches[0];
  if (paragraph.page !== evidence.page || paragraph.text !== evidence.text
    || !sameResearchCitation(paragraph.citation, ref)) return;
  return paragraphs.indexOf(paragraph);
}
