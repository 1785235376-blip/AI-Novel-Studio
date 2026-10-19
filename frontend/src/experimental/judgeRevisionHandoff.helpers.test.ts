import { describe, expect, it } from 'vitest';
import type { Chapter } from '../api';
import type { JudgeRun } from './styleReviewClient';
import { judgeRevisionFinding, type JudgeRevisionIntent } from './judgeRevisionHandoff';
const proof = { chapter_id: 'c', chapter_version: 4, paragraph: 2, start: 5, end: 8, quote: '甲🙂。' };
const intent: JudgeRevisionIntent = { runId: 'r', runVersion: 2, findingId: 'f', findingVersion: 3, evidenceIndex: 1, evidence: proof };
const chapter = { id: 'c', version: 4, content: '甲🙂。\n\n甲🙂。\n\n' } as Chapter;
const run = { id: 'r', version: 2, stale: false, findings: [{ id: 'f', version: 3, decision: 'PENDING', stale: false, evidence: [{ ...proof, paragraph: 1, start: 0, end: 3 }, proof] }] } as JudgeRun;
it('validates exact Unicode evidence and the second duplicate without manufacturing PM positions', () => {
  expect(judgeRevisionFinding(intent, run, chapter)?.id).toBe('f');
  expect(judgeRevisionFinding(intent, run, chapter)).not.toHaveProperty('from_pos');
});
describe('rejects mismatched or stale identities and malformed evidence', () => {
  it.each([
    { runId: 'other' }, { runVersion: 1 }, { findingId: 'other' }, { findingVersion: 2 }, { evidenceIndex: 0 },
    { evidenceIndex: -1 }, { evidenceIndex: 1.1 }, { evidence: { ...proof, start: 6 } },
  ])('%j', change => expect(judgeRevisionFinding({ ...intent, ...change }, run, chapter)).toBeUndefined());
  it.each([{ id: 'other' }, { version: 5 }, { content: 'changed' }])('chapter %j', change => expect(judgeRevisionFinding(intent, run, { ...chapter, ...change })).toBeUndefined());
  it('rejects stale, intentional, ambiguous and missing sources', () => {
    expect(judgeRevisionFinding(intent, { ...run, stale: true }, chapter)).toBeUndefined();
    expect(judgeRevisionFinding(intent, { ...run, findings: [...run.findings, ...run.findings] }, chapter)).toBeUndefined();
    for (const change of [{ stale: true }, { decision: 'INTENTIONAL' as const }]) expect(judgeRevisionFinding(intent, { ...run, findings: [{ ...run.findings[0], ...change }] }, chapter)).toBeUndefined();
    expect(judgeRevisionFinding(intent, undefined, chapter)).toBeUndefined();
  });
  it.each([{ paragraph: 1 }, { start: -1 }, { end: 100 }, { start: 5.5 }, { quote: 'different' }])('does not accept invalid matching transport %j', change => {
    const invalid = { ...proof, ...change };
    expect(judgeRevisionFinding({ ...intent, evidence: invalid }, { ...run, findings: [{ ...run.findings[0], evidence: [proof, invalid] }] }, chapter)).toBeUndefined();
  });
});
it('uses Python-compatible paragraph whitespace, preserving BOM and Unicode offsets', () => {
  const text = '\u0085\n\ufeff\n甲🙂。';
  const evidence = { ...proof, paragraph: 2, start: 4, end: 7 };
  expect(judgeRevisionFinding({ ...intent, evidence }, { ...run, findings: [{ ...run.findings[0], evidence: [proof, evidence] }] }, { ...chapter, content: text })?.id).toBe('f');
});
it('validates raw Markdown rather than substituting rendered or normalized text', () => {
  const evidence = { ...proof, paragraph: 1, start: 2, end: 5 };
  const rawChapter = { ...chapter, content: '# 甲🙂。\n\n' };
  const rawRun = { ...run, findings: [{ ...run.findings[0], evidence: [proof, evidence] }] };
  expect(judgeRevisionFinding({ ...intent, evidence }, rawRun, rawChapter)?.id).toBe('f');
  expect(judgeRevisionFinding({ ...intent, evidence }, rawRun, { ...rawChapter, content: '甲🙂。\n\n' })).toBeUndefined();
  const wrong = { ...evidence, quote: '甲🙂。'.normalize('NFKC') + ' ' };
  expect(judgeRevisionFinding({ ...intent, evidence: wrong }, { ...rawRun, findings: [{ ...rawRun.findings[0], evidence: [proof, wrong] }] }, rawChapter)).toBeUndefined();
});
