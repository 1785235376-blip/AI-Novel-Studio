// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { StorySimulatorPanel } from './StorySimulatorPanel';
import { NarrativeJudgePanel } from './NarrativeJudgePanel';
import { DeclarativeAgentsPanel } from './DeclarativeAgentsPanel';
import { MultilingualEditionsPanel } from './MultilingualEditionsPanel';
import { ExperimentalWorkbench } from './ExperimentalWorkbench';
import { experimentalClient } from './api';
const reply = (v: unknown, status = 200) => new Response(JSON.stringify(v), { status });
const chapter = { id: 'n:1', title: 'Synthetic chapter', version: 1 };
const workflow = { agent: { title: 'Synthetic workflow', purpose: '', role_prompt: '', input_schema: { fields: [] }, output_schema: { fields: [] }, allowed_tools: [], model_route: null, max_steps: 3, timeout_seconds: 30, max_output_bytes: 256 }, nodes: [], edges: [] };
const catalog = { chapters: [chapter], characters: [], planning_nodes: [], limits: { max_steps: 32, max_branches: 8 }, rubrics: [{ id: 'narrative-rules-v1', title: 'Rules', version: 1, checks: [], limitations: [] }], tools: [], node_types: [], model_routes: [], default_definition: workflow };
function row(id: string, job: string) { return { id, version: 2, status: 'COMPLETED', stale: false, routes: [], limitations: [], findings: [], abstentions: [], model_called: false, definition_id: 'definition', definition_version: 1, input: {}, node_states: {}, agent_output: null, trace: [], dispatch_trace: [], applied: false, attempt: 1, model_execution: { job_id: job, status: 'COMPLETED', receipt_state: 'RECORDED', usage_state: 'UNKNOWN', model_called: false } }; }
const cases = [
 { label: 'simulator', Panel: StorySimulatorPanel, selector: '查看剧情推演记录', feature: 'story_simulator_v2', authority: 'simulator_model_job' },
 { label: 'judge', Panel: NarrativeJudgePanel, selector: '查看审阅记录', feature: 'narrative_quality_judge_v2', authority: 'judge_model_job' },
 { label: 'declarative', Panel: DeclarativeAgentsPanel, selector: '查看 Workflow 运行', feature: 'declarative_agents_v2', authority: 'declarative_model_job' },
];
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function fixture() {
 const rows = [row('wrong-run', 'wrong-job'), row('target-run', 'target-job')];
 const fetch = vi.fn(async (url: string, _init?: RequestInit) => url.endsWith('/catalog') ? reply(catalog) : url.endsWith('/runs') ? reply({ items: rows }) : url.endsWith('/runs/target-run') ? reply(rows[1]) : reply({ items: [] }));
 vi.stubGlobal('fetch', fetch); return { fetch, client: experimentalClient('n', { sessionToken: 'session-a' }) };
}
it.each(cases)('$label reopens the exact receipt, handles missing/back and never replays', async ({ Panel, selector }) => {
 const e = fixture(); const view = render(<Panel client={e.client} requestedJobId="target-job" />);
 await waitFor(() => expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('target-run'));
 expect(e.fetch.mock.calls.every(([, init]) => !init || init.method === 'GET')).toBe(true);
 view.rerender(<Panel client={e.client} requestedJobId="missing-job" />);
 await screen.findByText(/原模型任务在当前授权.*不可用或身份不唯一/);
 expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('');
 view.rerender(<Panel client={e.client} requestedJobId="target-job" />);
 await waitFor(() => expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('target-run'));
});
it.each(cases)('$label ignores a former session late owner response', async ({ Panel, selector }) => {
 let finish: (r: Response) => void = () => {};
 const fetch = vi.fn(async (url: string, init: RequestInit) => {
   if (url.endsWith('/catalog')) return reply(catalog);
   if (url.endsWith('/runs') && new Headers(init.headers).get('X-Session-Token') === 'old') return new Promise<Response>(resolve => { finish = resolve; });
   return reply({ items: [] });
 }); vi.stubGlobal('fetch', fetch);
 const view = render(<Panel client={experimentalClient('n', { sessionToken: 'old' })} requestedJobId="target-job" />);
 await waitFor(() => expect(fetch.mock.calls.some(([url]) => url.endsWith('/runs'))).toBe(true));
 view.rerender(<Panel client={experimentalClient('n', { sessionToken: 'new' })} requestedJobId="target-job" />);
 await act(async () => finish(reply({ items: [row('target-run', 'target-job')] })));
 await screen.findByText(/原模型任务在当前授权.*不可用或身份不唯一/);
 expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('');
});
it.each(cases)('Workbench forwards $label only for its original owner', async ({ selector, feature, authority }) => {
 const e = fixture(); const props = { novelId: 'n', context: { sessionToken: 's' }, requestedTab: feature, flags: { experimental: true, default_enabled: false as const, features: { ['experimental.' + feature]: true } } };
 const view = render(<ExperimentalWorkbench {...props} requestedTask={{ id: 'target-job', authority: 'foreign-owner' }} />);
 await waitFor(() => expect((screen.getByLabelText(selector) as HTMLSelectElement).disabled).toBe(false)); expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('');
 view.rerender(<ExperimentalWorkbench {...props} requestedTask={{ id: 'target-job', authority }} />);
 await waitFor(() => expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('target-run'));
 expect(e.fetch.mock.calls.every(([, init]) => !init || init.method === 'GET')).toBe(true);
});
const segment = { id: 'segment', chapter_id: 'n:1', source_version: 1, path: [0], from_pos: 1, to_pos: 4, source_text: 'Original', target_text: 'Saved draft', note: '', status: 'DRAFT', issues: [] };
const edition = { id: 'edition', version: 1, title: 'Target edition', status: 'DRAFT', target_language: 'en', direction: 'ltr', stale: false, content_withheld: false, segments: [segment], rules: [] };
const translation = { id: 'translation-original', version: 2, status: 'CANDIDATE', edition_id: 'edition', edition_version: 1, segment_id: 'segment', stale: false, content_withheld: false, automatic_retry: false, quality_verification: 'NOT_RUN', preview: null, execution: { job_id: 'target-job', receipt_state: 'RECORDED', usage_state: 'UNKNOWN', accounting: null }, candidate: { text: 'EXACT_TRANSLATION_CANDIDATE', digest: 'a', job_id: 'target-job' } };
function translationFixture(withheld = false) {
 const fetch = vi.fn(async (url: string, _init?: RequestInit) => {
   if (url.endsWith('/catalog')) return reply({ chapters: [chapter], branch_sources_available: true });
   if (url.endsWith('/language-editions')) return reply({ items: [edition], truncated: false });
   if (url.endsWith('/translations')) return reply({ items: [{ ...translation, stale: withheld, content_withheld: withheld, candidate: withheld ? null : translation.candidate }], truncated: false });
   return reply({ items: [] });
 }); vi.stubGlobal('fetch', fetch); return { fetch, client: experimentalClient('n', { sessionToken: 'host' }) };
}
it('translation locates its exact receipt without overwriting a dirty bilingual draft', async () => {
 const e = translationFixture(); const view = render(<MultilingualEditionsPanel client={e.client} />);
 fireEvent.click(await screen.findByRole('button', { name: 'Target edition · en · v1' })); fireEvent.change(screen.getByLabelText('第 1 段译文'), { target: { value: 'Unsaved author draft' } });
 view.rerender(<MultilingualEditionsPanel client={e.client} requestedJobId="target-job" />);
 const target = await screen.findByRole('region', { name: '任务中心原翻译任务' }); await within(target).findByDisplayValue('EXACT_TRANSLATION_CANDIDATE');
 expect((screen.getByLabelText('第 1 段译文') as HTMLTextAreaElement).value).toBe('Unsaved author draft');
 expect((within(target).getByRole('button', { name: '打开原译文段落（保留任务定位）' }) as HTMLButtonElement).disabled).toBe(true);
 expect(e.fetch.mock.calls.every(([, init]) => !init || init.method === 'GET')).toBe(true);
});
it('translation missing and revoked references display no unrelated candidate', async () => {
 const e = translationFixture(true); const view = render(<MultilingualEditionsPanel client={e.client} requestedJobId="target-job" />);
 await screen.findByText(/原段落来源或隐私已变化/); expect(screen.queryByDisplayValue('EXACT_TRANSLATION_CANDIDATE')).toBeNull();
 view.rerender(<MultilingualEditionsPanel client={e.client} requestedJobId="missing" />); await screen.findByText(/原翻译任务在当前授权记录中不可用/); expect(screen.queryByText(/原翻译记录 translation-original/)).toBeNull();
});
it('Workbench forwards only the translation owner to the exact receipt', async () => {
 translationFixture(); const props = { novelId: 'n', context: { sessionToken: 's' }, requestedTab: 'multilingual_editions_v2', flags: { experimental: true, default_enabled: false as const, features: { 'experimental.multilingual_editions_v2': true } } };
 const view = render(<ExperimentalWorkbench {...props} requestedTask={{ id: 'target-job', authority: 'foreign-owner' }} />);
 await screen.findByRole('button', { name: 'Target edition · en · v1' }); expect(screen.queryByRole('region', { name: '任务中心原翻译任务' })).toBeNull();
 view.rerender(<ExperimentalWorkbench {...props} requestedTask={{ id: 'target-job', authority: 'translation_model_job' }} />); await screen.findByDisplayValue('EXACT_TRANSLATION_CANDIDATE');
});

it.each(cases)('$label refuses ambiguous original job ownership rather than choosing first', async ({ Panel, selector }) => {
 vi.stubGlobal('fetch', vi.fn(async (url: string) => url.endsWith('/catalog') ? reply(catalog) : url.endsWith('/runs') ? reply({ items: [row('first', 'target-job'), row('second', 'target-job')] }) : reply({ items: [] })));
 render(<Panel client={experimentalClient('n', { sessionToken: 'host' })} requestedJobId="target-job" />);
 await screen.findByText(/原模型任务在当前授权.*不可用或身份不唯一/); expect((screen.getByLabelText(selector) as HTMLSelectElement).value).toBe('');
});
it('Task Center and resume prefer additive owner pointers while retaining legacy read contracts', async () => {
 const { WorkspaceToolsPanel } = await import('./WorkspaceToolsPanel'); const navigate = vi.fn();
 const source = { kind: 'feature', id: 'job', feature: 'story_simulator_v2' };
 const owner = { ...source, task_authority: 'simulator_model_job', chapter_id: 'n:1', version: 1 };
 const task = { id: 'job', authority: 'author_generation', label: 'Simulation', feature: source.feature, status: 'COMPLETED', stage_label: '已完成', source, owner_navigation: owner, progress: null, history: [], lifecycle: '原任务', actions: ['open_source'] };
 const fetch = vi.fn(async (url: string, _init?: RequestInit) => reply(url.endsWith('/resume') ? { item: null } : url.includes('/tasks') ? { items: [task], unavailable: [] } : { items: [] })); vi.stubGlobal('fetch', fetch);
 render(<WorkspaceToolsPanel client={experimentalClient('n', { sessionToken: 'host' })} initialSection="tasks" onNavigate={navigate} />);
 fireEvent.click(await screen.findByRole('button', { name: '打开来源工具' })); expect(navigate).toHaveBeenCalledWith(owner);
 expect(fetch.mock.calls.every(([, init]) => !init || init.method === 'GET')).toBe(true);
});
