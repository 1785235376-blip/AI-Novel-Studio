// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { IndependentDirectorModelReview } from './IndependentDirectorModelReview';
import { createDirectorModelClient } from './directorModelClient';
import captured from './directorScreenplayWire.testFixture.json';
import { multiShotFixture } from './directorScreenplayMultiShot.testFixtures';
afterEach(cleanup);
const p = captured.preview.receipt;
function setup(options: { pending?: boolean; uncertainReview?: boolean } = {}) {
  const fixture = multiShotFixture(2048), requests: { path: string; method: string; body: any }[] = [];
  let multi = false;
  const json = vi.fn(async (path: string, method: string, body: any) => {
    requests.push({ path, method, body }); const suffix = path.split('/').at(-1);
    if (suffix === 'preview') { multi = body?.planning_mode === 'MULTI_SHOT_V1'; return structuredClone(multi ? fixture.preview : captured.preview); }
    if (suffix === 'dispatch') return structuredClone(fixture.completed_status);
    if (suffix === 'status') return structuredClone(options.pending ? fixture.pending_status : fixture.completed_status);
    if (suffix === 'prepare-review' || suffix === 'pending-review') return structuredClone(fixture.pending);
    if (suffix === 'review' && options.uncertainReview) throw new Error('lost review response');
    if (suffix === 'review' || suffix === 'reconcile-review') return structuredClone(fixture.adopted);
    throw new Error('Unexpected endpoint');
  });
  const model = createDirectorModelClient(captured.preview.project_id, { json: json as never }, undefined, 'SCREENPLAY');
  const props = { model, creative: { export: vi.fn() }, proposal: { id: p.proposal_id, version: p.version - 1, title: fixture.submitted_review.title },
    source: { id: p.source_document_id, version: p.source_version, digest: p.source_digest }, sourceMode: 'SCREENPLAY' as const,
    routes: [{ route_id: p.route_id, provider_id: p.provider_id, model_id: p.model_id, synthetic: false, available: true, reasons: [] }],
    canMutate: true, disabled: false, onDocument: vi.fn(), onPending: vi.fn(), onDenied: vi.fn() };
  return { props, fixture, json, requests };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
function chooseMulti() {
  fireEvent.change(screen.getByLabelText('剧本镜头规划方式'), { target: { value: 'MULTI_SHOT_V1' } });
  fireEvent.change(screen.getByLabelText('独立导演本地路由'), { target: { value: p.route_id } });
}
async function prepare() {
  chooseMulti(); click('预览独立剧本模型输入'); await screen.findByText('多镜头规划 · 待模型选择候选');
  fireEvent.click(screen.getByLabelText('已核对输入，允许调用一次本地模型')); click('调用一次独立导演模型');
  await screen.findByText('COMPLETED'); click('准备原模型结果供人工审核'); await screen.findByLabelText('模型导演草稿标题');
}
function approve() { fireEvent.click(screen.getByLabelText('已核对来源、理由和假设，创建独立导演草稿')); click('采用模型审核结果'); }
it('defaults to the unchanged scene request and emits no opt-in until explicitly selected', async () => {
  const e = setup(); render(<IndependentDirectorModelReview {...e.props} />); expect(e.json).not.toHaveBeenCalled();
  expect((screen.getByLabelText('剧本镜头规划方式') as HTMLSelectElement).value).toBe('SCENE_V2');
  fireEvent.change(screen.getByLabelText('独立导演本地路由'), { target: { value: p.route_id } });
  click('预览独立剧本模型输入'); await screen.findByText('预览尚未调用模型');
  expect(e.requests).toHaveLength(1); expect(e.requests[0].body).not.toHaveProperty('planning_mode');
  expect(screen.queryByText('多镜头规划 · 待模型选择候选')).toBeNull();
  expect((screen.getByRole('button', { name: '调用一次独立导演模型' }) as HTMLButtonElement).disabled).toBe(true);
});
it('shows the selected four-shot/two-scene plan and updates estimated timing without changing frozen IDs or order', async () => {
  const e = setup(); render(<IndependentDirectorModelReview {...e.props} />); await prepare();
  expect(e.requests[0].body.planning_mode).toBe('MULTI_SHOT_V1'); expect(e.requests[0].body.max_output_tokens).toBe(2048);
  const summary = within(screen.getByRole('region', { name: '多镜头候选摘要' }));
  expect(summary.getByText('2 个来源场景 · 4 个候选镜头 · 估算总时长 26 秒')).toBeTruthy();
  expect(summary.getByText('场景 4 · 2 个候选镜头 · 估算 11 秒')).toBeTruthy();
  expect(summary.getByText('场景 9 · 2 个候选镜头 · 估算 15 秒')).toBeTruthy();
  expect(summary.getByText(/时长为规划估算，质量尚未验证/)).toBeTruthy();
  fireEvent.click(screen.getByLabelText('已核对来源、理由和假设，创建独立导演草稿'));
  fireEvent.change(screen.getByLabelText('模型 4 时长（秒）'), { target: { value: '12' } });
  expect(summary.getByText('2 个来源场景 · 4 个候选镜头 · 估算总时长 30 秒')).toBeTruthy();
  expect((screen.getByRole('button', { name: '采用模型审核结果' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.change(screen.getByLabelText('模型 2 导演意图'), { target: { value: 'Human shot refinement' } });
  approve(); await screen.findByText('已采用为独立导演 DRAFT，画布尚未保存。');
  const body = e.requests.find(row => row.path.endsWith('/review'))!.body;
  expect(body.director_notes.map(({ id, scene_id, number }: any) => ({ id, scene_id, number }))).toEqual(e.fixture.pending.receipt.director_notes.map(({ id, scene_id, number }) => ({ id, scene_id, number })));
  expect(body.director_notes[1].note).toBe('Human shot refinement'); expect(body.director_notes[3].duration_seconds).toBe(12);
  expect(e.props.onDocument).not.toHaveBeenCalled(); expect(e.requests.filter(row => row.method === 'POST')).toHaveLength(4);
});
it('reopens V3 pending review read-only without redispatch or new opt-in', async () => {
  const e = setup({ pending: true }); render(<IndependentDirectorModelReview {...e.props} />);
  click('读取原模型任务状态'); await screen.findByRole('region', { name: '多镜头候选摘要' });
  expect(e.requests.map(row => [row.path.split('/').at(-1), row.method])).toEqual([['status', 'GET'], ['pending-review', 'GET']]);
  expect(screen.queryByLabelText('剧本镜头规划方式')).toBeNull(); expect(e.props.onPending).toHaveBeenLastCalledWith(true);
});
it('preserves all four dirty candidates when the remote version changes and requires explicit discard', async () => {
  const e = setup({ pending: true }); render(<IndependentDirectorModelReview {...e.props} />); await prepare();
  fireEvent.change(screen.getByLabelText('模型 3 导演意图'), { target: { value: 'Keep my third shot' } });
  const changed = structuredClone(e.fixture.pending_status); changed.receipt.version++;
  e.json.mockResolvedValueOnce(changed as never); click('读取原模型任务状态');
  await screen.findByText('原任务状态已变化，本地审核仍保留。');
  expect((screen.getByLabelText('模型 3 导演意图') as HTMLTextAreaElement).value).toBe('Keep my third shot');
  expect((screen.getByLabelText('模型导演草稿标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '按确认重新读取原任务' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.getByText('2 个来源场景 · 4 个候选镜头 · 估算总时长 26 秒')).toBeTruthy();
  expect(e.requests.filter(row => row.path.endsWith('/pending-review') || row.path.endsWith('/review'))).toHaveLength(0);
});
it('drops a late V3 preview after source A→B→A and clears its opt-in', async () => {
  const e = setup(); let resolve!: (value: typeof e.fixture.preview) => void;
  e.json.mockImplementationOnce(() => new Promise(yes => { resolve = yes; }));
  const view = render(<IndependentDirectorModelReview {...e.props} />); chooseMulti(); click('预览独立剧本模型输入');
  view.rerender(<IndependentDirectorModelReview {...e.props} source={{ ...e.props.source, version: 2 }} />);
  view.rerender(<IndependentDirectorModelReview {...e.props} />);
  await act(async () => resolve(e.fixture.preview));
  expect(screen.queryByText('多镜头规划 · 待模型选择候选')).toBeNull();
  expect((screen.getByLabelText('剧本镜头规划方式') as HTMLSelectElement).value).toBe('SCENE_V2');
  expect(e.json).toHaveBeenCalledTimes(1); expect(screen.queryByRole('button', { name: '调用一次独立导演模型' })).toBeNull();
});
it('locks the opt-in while preview is pending and deduplicates repeated gestures', async () => {
  const e = setup(); let resolve!: (value: typeof e.fixture.preview) => void;
  e.json.mockImplementationOnce(() => new Promise(yes => { resolve = yes; }));
  render(<IndependentDirectorModelReview {...e.props} />); chooseMulti(); click('预览独立剧本模型输入');
  const select = screen.getByLabelText('剧本镜头规划方式') as HTMLSelectElement; expect(select.disabled).toBe(true);
  fireEvent.change(select, { target: { value: 'SCENE_V2' } }); click('预览独立剧本模型输入');
  expect(e.json).toHaveBeenCalledTimes(1); expect(e.json.mock.calls[0][2].planning_mode).toBe('MULTI_SHOT_V1');
  await act(async () => resolve(e.fixture.preview)); expect(screen.getByText('多镜头规划 · 待模型选择候选')).toBeTruthy();
  expect((screen.getByRole('button', { name: '调用一次独立导演模型' }) as HTMLButtonElement).disabled).toBe(true);
});
it('retains the exact four-shot uncertain submission and reconciles without resending review', async () => {
  const e = setup({ uncertainReview: true }); render(<IndependentDirectorModelReview {...e.props} />); await prepare();
  fireEvent.change(screen.getByLabelText('模型 4 导演意图'), { target: { value: 'Last shot human review' } });
  approve(); await screen.findByText('lost review response');
  expect((screen.getByLabelText('模型 4 导演意图') as HTMLTextAreaElement).value).toBe('Last shot human review');
  expect((screen.getByLabelText('模型导演草稿标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
  click('读取原模型任务状态'); await waitFor(() => expect(e.requests.some(row => row.path.endsWith('/status'))).toBe(true));
  click('只读核对刚才的审核提交'); await screen.findByText('已采用为独立导演 DRAFT，画布尚未保存。');
  const writes = e.requests.filter(row => row.path.endsWith('/review')); expect(writes).toHaveLength(1);
  expect(e.requests.find(row => row.path.endsWith('/reconcile-review'))?.body).toEqual(writes[0].body);
});
it('does not expose the opt-in in storyboard mode or start work while the parent is disabled', () => {
  const e = setup(); const view = render(<IndependentDirectorModelReview {...e.props} sourceMode="STORYBOARD" />);
  expect(screen.queryByLabelText('剧本镜头规划方式')).toBeNull();
  view.rerender(<IndependentDirectorModelReview {...e.props} disabled />);
  expect((screen.getByLabelText('剧本镜头规划方式') as HTMLSelectElement).disabled).toBe(true);
  click('预览独立剧本模型输入'); expect(e.json).not.toHaveBeenCalled();
});
it('preserves dirty multi-shot text and blocks adoption while the parent source is dirty or stale', async () => {
  const e = setup(), view = render(<IndependentDirectorModelReview {...e.props} />); await prepare();
  fireEvent.change(screen.getByLabelText('模型 2 导演意图'), { target: { value: 'Keep local second shot' } });
  fireEvent.click(screen.getByLabelText('已核对来源、理由和假设，创建独立导演草稿'));
  view.rerender(<IndependentDirectorModelReview {...e.props} disabled />);
  expect((screen.getByLabelText('模型导演草稿标题').closest('fieldset') as HTMLFieldSetElement).disabled).toBe(true);
  click('采用模型审核结果'); expect(e.requests.filter(row => row.path.endsWith('/review'))).toHaveLength(0);
  expect((screen.getByLabelText('模型 2 导演意图') as HTMLTextAreaElement).value).toBe('Keep local second shot');
  expect(e.props.onPending).toHaveBeenLastCalledWith(true);
});
