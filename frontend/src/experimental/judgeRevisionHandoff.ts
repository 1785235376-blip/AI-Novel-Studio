import type { Chapter } from '../api';
import type { JudgeEvidence, JudgeFinding, JudgeRun } from './styleReviewClient';

/** Session navigation only. This is neither an approval nor a manuscript range. */
export type JudgeRevisionIntent = {
  runId: string; runVersion: number; findingId: string; findingVersion: number;
  evidenceIndex: number; evidence: JudgeEvidence;
};

export function judgeRevisionFinding(intent: JudgeRevisionIntent, run: JudgeRun | undefined, chapter: Chapter | undefined): JudgeFinding | undefined {
  if (!chapter || !run || !Array.isArray(run.findings) || run.stale || run.id !== intent.runId || run.version !== intent.runVersion) return;
  const matches = run.findings.filter(row => row.id === intent.findingId);
  if (matches.length !== 1) return;
  const finding = matches[0];
  if (finding.stale || finding.version !== intent.findingVersion || finding.decision === 'INTENTIONAL') return;
  if (!Number.isSafeInteger(intent.evidenceIndex) || intent.evidenceIndex < 0) return;
  const proof = finding.evidence[intent.evidenceIndex];
  if (!proof || (['chapter_id', 'chapter_version', 'paragraph', 'start', 'end', 'quote'] as (keyof JudgeEvidence)[]).some(key => proof[key] !== intent.evidence[key])) return;
  if (typeof proof.quote !== 'string' || !proof.quote || proof.chapter_id !== chapter.id || proof.chapter_version !== chapter.version || typeof chapter.content !== 'string') return;
  if (![proof.start, proof.end, proof.paragraph].every(Number.isSafeInteger) || proof.start < 0 || proof.end <= proof.start || proof.paragraph < 1) return;
  const characters = Array.from(chapter.content);
  if (characters.length > 100_000 || proof.end > characters.length || characters.slice(proof.start, proof.end).join('') !== proof.quote) return;
  // Same source contract as Judge: each nonempty raw Markdown line is a paragraph.
  // These Unicode offsets MUST NOT be reused as ProseMirror UTF-16 positions.
  let paragraph = 0, offset = 0, inParagraph = false;
  for (const line of chapter.content.split(/([\r\n])/)) {
    const length = Array.from(line).length;
    if (line && !/^[\r\n]$/.test(line) && line.replace(/[\u0009-\u000d\u001c-\u0020\u0085\u00a0\u1680\u2000-\u200a\u2028\u2029\u202f\u205f\u3000]/g, '')) {
      paragraph++;
      if (paragraph === proof.paragraph && offset <= proof.start && proof.end <= offset + length) inParagraph = true;
    }
    offset += length;
  }
  return inParagraph ? finding : undefined;
}

export function judgeRevisionReference(intent: JudgeRevisionIntent): string {
  return `审阅 ${intent.runId} / ${intent.findingId} v${intent.findingVersion} · 证据 ${intent.evidenceIndex + 1} · 章节 ${intent.evidence.chapter_id} v${intent.evidence.chapter_version}`;
}
