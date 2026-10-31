// @vitest-environment jsdom
// Extracted additions and migrated variants; protected baseline suite stays byte-identical.
// Migrated variants preserve newer assertions and are not counted as unique new capabilities.
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { Chapter } from '../api';
import { experimentalClient } from './api';
import { StyleAnalysisPanel } from './StyleAnalysisPanel';

const chapter = { id: 'chapter-one', title: '雨夜', version: 3 } as Chapter;
const context = { sessionToken: 'session-one', scope: { workspaceId: 'w', projectId: 'novel-one', storylineId: 's', branchId: 'branch-one' } };
const style = { id: 'style-one', version: 2, status: 'APPROVED', title: '克制文风', instructions: '使用短句，保留停顿。', rules: ['留意重复意象'], chapter_ids: ['chapter-one'], character_ids: ['person-one'], privacy_level: 'LOCAL_ONLY' };
const catalog = { styles: [style], chapters: [{ ...chapter, characters: 50 }], characters: [{ id: 'person-one', name: '小林' }], operations: ['continue', 'rewrite', 'polish', 'brainstorm', 'review'] };
const preview = { style_id: style.id, style_version: 2, instructions: style.instructions, rules: style.rules, operation: 'continue', character_id: null, privacy_level: 'LOCAL_ONLY', context_injection: 'INSTRUCTIONS_ONLY', rules_usage: 'REFERENCE_ONLY', model_called: false, preview_digest: 'receipt-one' };
const analysis = { id: 'analysis-one', version: 1, style_id: style.id, style_version: 2, language: 'zh', method_version: 'counts-v1', status: 'COMPLETED', stale: false, metrics: { sentence_count: 4, paragraph_count: 2, unit_count: 40, dialogue_characters: 8, characters: 50 }, samples: [{ chapter_id: chapter.id, expected_version: 3, start: 0, end: null }], comparison: null, limitations: ['统计不能判断文学质量。'], privacy_level: 'LOCAL_ONLY' };
const rubric = { id: 'narrative-rules-v1', version: 1, title: '叙事基础检查', checks: ['重复段落'], limitations: ['不判断人物动机。'] };
const finding = { id: 'finding-one', version: 4, status: 'OPEN', decision: 'PENDING', code: 'REPEATED_PARAGRAPH', category: 'REPETITION', severity: 'WARNING', explanation: '两个段落完全相同。', suggestion: '核对是否为有意重复。', boundary: '不能判断作者意图。', origin: 'DETERMINISTIC', evidence: [{ chapter_id: chapter.id, chapter_version: 3, paragraph: 2, start: 12, end: 20, quote: '雨仍然在下。' }], stale: false };
const run = { id: 'run-one', version: 1, status: 'COMPLETED', stale: false, findings: [finding], abstentions: ['情节合理性无法判断。'], verification: 'DETERMINISTIC_RULES', model_called: false };
const reply = (body: unknown, status = 200) => new Response(JSON.stringify(body), { status });
const client = () => experimentalClient('novel-one', context);
function transport() {
  let analyses: unknown[] = [], reviewed = { ...finding };
  return vi.fn(async (url: string, init?: RequestInit) => {
    if (url.endsWith('/style-analysis/catalog')) return reply(catalog);
    if (url.endsWith('/style-analysis/analyses') && init?.method === 'POST') { analyses = [analysis]; return reply(analysis); }
    if (url.endsWith('/style-analysis/analyses')) return reply({ items: analyses });
    if (url.endsWith('/style-analysis/profiles')) return reply({ ...style, status: 'DRAFT', version: 1 });
    if (url.endsWith('/style-analysis/profiles/style-one') && init?.method === 'PUT') return reply({ ...style, version: 3, status: 'DRAFT', ...JSON.parse(init.body as string) });
    if (url.endsWith('/style-one/preview')) { const body = JSON.parse(init!.body as string); return reply({ ...preview, operation: body.operation, character_id: body.character_id }); }
    if (url.endsWith('/narrative-judge/catalog')) return reply({ chapters: [chapter], rubrics: [rubric], adapters: [] });
    if (url.endsWith('/narrative-judge/runs/run-one')) return reply({ ...run, findings: [reviewed] });
    if (url.endsWith('/narrative-judge/runs')) return reply(init?.method === 'POST' ? run : { items: [run] });
    if (url.endsWith('/findings/finding-one/review')) { const body = JSON.parse(init!.body as string); reviewed = { ...finding, version: 5, decision: body.action === 'ignore' ? 'IGNORED' : body.action === 'reopen' ? 'PENDING' : 'REVIEWED' }; return reply(reviewed); }
    throw new Error(`Unhandled ${init?.method} ${url}`);
  });
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

it('mounts saved target comparison beside original sample evidence and preserves manual profile input when target navigation is cancelled', async () => {
  const base = transport(), navigate = vi.fn(), useStyle = vi.fn();
  const measured = { sentence_length_mean: { numerator: 9, denominator: 3 }, sample_sufficiency: 'SHORT_SAMPLE' };
  const report = { ...analysis, metrics: measured, comparison: { chapter_id: 'target-two', expected_version: 8, language: 'zh', comparable: true, metrics: measured, paragraphs: [{ paragraph: 1, start: 0, end: 3, quote: '风😀。', metrics: measured }], paragraphs_truncated: false, interpretation: 'RAW_COUNT_DIFFERENCES_NOT_QUALITY_OR_NORMALIZED_DRIFT' } };
  const fetch = vi.fn((url: string, init?: RequestInit) => url.endsWith('/style-analysis/analyses') ? Promise.resolve(reply({ items: [report] })) : base(url, init));
  vi.stubGlobal('fetch', fetch);
  render(<StyleAnalysisPanel client={client()} chapter={chapter} onNavigate={navigate} onUseStyle={useStyle} />);
  await screen.findByRole('region', { name: '样本与目标比较 analysis-one' });
  fireEvent.click(screen.getByRole('button', { name: '编辑风格 克制文风' }));
  fireEvent.change(screen.getByLabelText('可复用风格指令（最多 120 字）'), { target: { value: '我的未保存人工判断' } });
  fireEvent.click(screen.getByRole('button', { name: '打开比较目标原章节 v8' }));
  expect(navigate).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '取消离开，保留文风输入' }));
  expect((screen.getByLabelText('可复用风格指令（最多 120 字）') as HTMLTextAreaElement).value).toBe('我的未保存人工判断');
  expect(fetch.mock.calls.every(([, init]) => init?.method === 'GET')).toBe(true);
  expect(useStyle).not.toHaveBeenCalled();
});
