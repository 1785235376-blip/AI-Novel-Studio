// Read-only projection of the original saved analysis. No inferred quality/drift score.
export type StyleComparison = {
  chapter_id: string; expected_version: number; language: 'zh' | 'en'; comparable: boolean;
  metrics: Record<string, unknown>;
  paragraphs: { paragraph: number; start: number; end: number; quote: string; metrics: Record<string, unknown> }[];
  paragraphs_truncated: boolean; interpretation: string;
};
const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const integer = (value: unknown, min = 0): value is number => typeof value === 'number' && Number.isSafeInteger(value) && value >= min;
export function readStyleComparison(value: unknown): StyleComparison | undefined {
  if (!record(value) || typeof value.chapter_id !== 'string' || !value.chapter_id.trim() || !integer(value.expected_version, 1)
    || (value.language !== 'zh' && value.language !== 'en') || typeof value.comparable !== 'boolean' || !record(value.metrics)
    || typeof value.paragraphs_truncated !== 'boolean' || !Array.isArray(value.paragraphs) || value.paragraphs.length > 200
    || (value.interpretation !== 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT' && value.interpretation !== 'LANGUAGE_METHODS_NOT_COMPARABLE')) return;
  let previousEnd = -1, previousParagraph = 0;
  for (const paragraph of value.paragraphs) {
    if (!record(paragraph) || !integer(paragraph.paragraph, 1) || paragraph.paragraph <= previousParagraph
      || !integer(paragraph.start) || paragraph.start < previousEnd || !integer(paragraph.end, 1) || paragraph.end <= paragraph.start
      || typeof paragraph.quote !== 'string' || Array.from(paragraph.quote).length !== paragraph.end - paragraph.start || !record(paragraph.metrics)) return;
    previousEnd = paragraph.end; previousParagraph = paragraph.paragraph;
  }
  return value as StyleComparison;
}
export function measuredRatio(value: unknown): { numerator: number; denominator: number } | undefined {
  if (!record(value) || !integer(value.numerator) || !integer(value.denominator) || (value.denominator === 0 && value.numerator !== 0)) return;
  return { numerator: value.numerator, denominator: value.denominator };
}
