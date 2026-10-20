// @vitest-environment jsdom
import { act, cleanup, renderHook, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { studioIntentState } from './studioEntryContract';
import { studioBlankIntentValues } from './studioEntryClient';
import {
  STUDIO_INTENT_IDS, STUDIO_INTENT_LABELS, type StudioEntryClient, type StudioEntryIntent,
  type StudioEntryProject, type StudioProjectCreation,
} from './studioEntryTypes';
import { useStudioEntry, studioSuggestions, type StudioEntryControllerConfig } from './useStudioEntry';

const rows: StudioEntryProject[] = [
  { id: 'novel-1', title: '第一个项目', updated_at: null, entry_kind: 'NEUTRAL_STUDIO', genre: null, status: null },
  { id: 'novel-2', title: '第二个项目', updated_at: null, entry_kind: null, genre: null, status: null },
];
const values = (selected: string[]) => STUDIO_INTENT_IDS.map(intent_id => ({
  intent_id,
  label: STUDIO_INTENT_LABELS[intent_id],
  selected: selected.includes(intent_id),
  custom: intent_id === 'custom',
}));
/** Fixtures go through the strict validator, so the hook is driven by real contract data. */
function intent(version: number, selected: string[] = []): StudioEntryIntent {
  return studioIntentState({ version, preset: 'TEXT', values: values(selected), editable: true, history_retained: true }, 'novel-1');
}
const createdProject: StudioProjectCreation = { id: 'novel-new', title: '新项目', studio_ready: true, requires_scope_selection: false };
type Fake = {
  listProjects: ReturnType<typeof vi.fn>; createBlankProject: ReturnType<typeof vi.fn>;
  readIntent: ReturnType<typeof vi.fn>; saveIntent: ReturnType<typeof vi.fn>;
};
function fakeClient(patch: Partial<Fake> = {}) {
  const client: Fake = {
    listProjects: vi.fn(async () => rows),
    createBlankProject: vi.fn(async () => createdProject),
    readIntent: vi.fn(async () => intent(1)),
    saveIntent: vi.fn(async () => intent(2)),
    ...patch,
  };
  return { client: client as unknown as StudioEntryClient, listProjects: client.listProjects, createBlankProject: client.createBlankProject, readIntent: client.readIntent, saveIntent: client.saveIntent };
}
const config = (client: StudioEntryClient, patch: Partial<StudioEntryControllerConfig> = {}): StudioEntryControllerConfig => ({
  client, identity: 'entry-session', active: true, ...patch,
});
const mount = (client: StudioEntryClient, patch: Partial<StudioEntryControllerConfig> = {}) =>
  renderHook((value: StudioEntryControllerConfig) => useStudioEntry(value), { initialProps: config(client, patch) });

beforeEach(() => { vi.restoreAllMocks(); });
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('studio entry controller', () => {
  it('reads the project list once and reaches ready with the saved intent', async () => {
    const { client, listProjects, readIntent } = fakeClient();
    const view = mount(client);
    expect(view.result.current.state).toBe('loading');
    await waitFor(() => expect(view.result.current.state).toBe('ready'));
    expect(listProjects).toHaveBeenCalledTimes(1);
    expect(readIntent).not.toHaveBeenCalled();
    expect(view.result.current.values.every(item => !item.selected)).toBe(true);
    expect(view.result.current.dirty).toBe(false);
    await act(async () => { await view.result.current.reload(); });
    expect(listProjects).toHaveBeenCalledTimes(2);
  });

  it('reports an empty project list as empty and never reads an intent without a project', async () => {
    const { client, readIntent } = fakeClient({ listProjects: vi.fn(async () => []) });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('empty'));
    expect(view.result.current.projects).toEqual([]);
    expect(readIntent).not.toHaveBeenCalled();
    expect(view.result.current.suggestions.length).toBeGreaterThan(0);
  });

  it('never collapses a read failure into an empty list', async () => {
    const { client } = fakeClient({ listProjects: vi.fn(async () => { throw new ApiError({ status: 503, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); }) });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('failed'));
    expect(view.result.current.state).not.toBe('empty');
    expect(view.result.current.problem?.code).toBe('STUDIO_REQUEST_FAILED');
    expect(view.result.current.projects).toEqual([]);
  });

  it('reaches denied when the session loses authority and clears the data', async () => {
    const { client, readIntent } = fakeClient({
      listProjects: vi.fn(async () => { throw new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: 'denied' }); }),
    });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('denied'));
    expect(view.result.current.projects).toEqual([]);
    await act(async () => { await view.result.current.reload(); });
    expect(readIntent).not.toHaveBeenCalled();
  });

  it('reports a resume target that cannot be read as invalid instead of creating a replacement', async () => {
    const { client, createBlankProject } = fakeClient({
      listProjects: vi.fn(async () => rows),
      readIntent: vi.fn(async () => { throw new ApiError({ status: 404, code: 'STUDIO_REQUEST_FAILED', message: '记录不可用。' }); }),
    });
    const view = mount(client, { projectId: 'deleted-project' });
    await waitFor(() => expect(view.result.current.state).toBe('missing'));
    expect(view.result.current.problem?.code).toBe('STUDIO_ENTRY_PROJECT_MISSING');
    expect(view.result.current.problem?.message).toContain('已不可用');
    expect(view.result.current.problem?.message).toContain('不会自动创建一个替代项目');
    expect(createBlankProject).not.toHaveBeenCalled();
    expect(view.result.current.intent).toBeUndefined();
  });

  it('reads the saved intent of a known project when one is selected', async () => {
    const { client, readIntent } = fakeClient({ readIntent: vi.fn(async () => intent(4, ['image_design'])) });
    const view = mount(client, { projectId: 'novel-1' });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(4));
    expect(readIntent).toHaveBeenCalledWith('novel-1', expect.anything());
    expect(view.result.current.selectedIntentIds).toEqual(['image_design']);
    expect(view.result.current.canOpen).toBe(true);
    expect(view.result.current.dirty).toBe(false);
  });

  it('creates a blank project without ever writing an intent', async () => {
    const { client, createBlankProject, saveIntent, readIntent } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('ready'));
    act(() => view.result.current.setTitle('新项目'));
    let result: Awaited<ReturnType<typeof view.result.current.create>> | undefined;
    await act(async () => { result = await view.result.current.create('blank'); });
    expect(result?.status).toBe('created');
    expect(createBlankProject).toHaveBeenCalledWith({ title: '新项目' });
    expect(saveIntent).not.toHaveBeenCalled();
    expect(readIntent).not.toHaveBeenCalled();
    expect(view.result.current.projects[0].id).toBe('novel-new');
  });

  it('creates a project from the selected intents and saves them as one versioned replacement', async () => {
    const { client, readIntent, saveIntent } = fakeClient();
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('ready'));
    act(() => view.result.current.setTitle('意图项目'));
    act(() => view.result.current.toggleIntent('image_design'));
    expect(view.result.current.savable).toBe(true);
    let result: Awaited<ReturnType<typeof view.result.current.create>> | undefined;
    await act(async () => { result = await view.result.current.create('intent'); });
    expect(result?.status).toBe('created');
    expect(readIntent).toHaveBeenCalledWith('novel-new');
    expect(saveIntent).toHaveBeenCalledTimes(1);
    const draft = saveIntent.mock.calls[0][1];
    expect(draft.expected_version).toBe(1);
    expect(draft.values.filter((item: { selected: boolean }) => item.selected).map((item: { intent_id: string }) => item.intent_id)).toEqual(['image_design']);
  });

  it('keeps the project and the draft when the intent step of a creation fails', async () => {
    const { client, saveIntent } = fakeClient({
      saveIntent: vi.fn(async () => { throw new ApiError({ status: 422, code: 'PRODUCTION_WORKFLOW_INTENT_INVALID', message: '服务端未接受这次创作意图。当前输入仍保留，请核对意图标识与自定义名称。' }); }),
    });
    const view = mount(client);
    await waitFor(() => expect(view.result.current.state).toBe('ready'));
    act(() => view.result.current.setTitle('意图项目'));
    act(() => view.result.current.toggleIntent('image_design'));
    let result: Awaited<ReturnType<typeof view.result.current.create>> | undefined;
    await act(async () => { result = await view.result.current.create('intent'); });
    expect(result?.status).toBe('intent_failed');
    expect(result?.project?.id).toBe('novel-new');
    expect(view.result.current.selectedId).toBe('novel-new');
    expect(view.result.current.dirty).toBe(true);
    expect(view.result.current.problem?.message).toContain('服务端未接受');
  });

  it('re-reads on a 409 conflict, keeps the user draft and resubmits the served version', async () => {
    let served = intent(3, []);
    const { client, readIntent, saveIntent } = fakeClient({ readIntent: vi.fn(async () => served) });
    const view = mount(client, { projectId: 'novel-1' });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(3));
    act(() => view.result.current.toggleIntent('image_design'));
    expect(view.result.current.dirty).toBe(true);

    served = intent(5, []);
    // The owner's mapped, bounded text is what the client seam hands this controller.
    saveIntent.mockRejectedValueOnce(new ApiError({ status: 409, code: 'PRODUCTION_WORKFLOW_INTENT_CONFLICT', message: '创作意图已被其他会话更新。当前输入仍保留，请核对最新版本后重新提交。' }));
    await act(async () => { await view.result.current.saveIntent(); });
    await waitFor(() => expect(view.result.current.conflict).toBe(true));
    // The user's own draft survives the conflict, including the re-read version.
    expect(view.result.current.values.find(item => item.intent_id === 'image_design')?.selected).toBe(true);
    expect(view.result.current.draft?.expected_version).toBe(5);
    expect(view.result.current.notice).toContain('你的选择仍保留');
    expect(readIntent).toHaveBeenCalledTimes(2);

    act(() => view.result.current.acknowledgeConflict());
    expect(view.result.current.conflict).toBe(false);
    await act(async () => { await view.result.current.saveIntent(); });
    expect(saveIntent).toHaveBeenLastCalledWith('novel-1', expect.objectContaining({ expected_version: 5 }));
    expect(view.result.current.intent?.version).toBe(2);
    expect(view.result.current.notice).toContain('v2');
  });

  it('refuses a selected custom intent without a name and never calls the owner', async () => {
    const { client, saveIntent } = fakeClient({ readIntent: vi.fn(async () => intent(1)) });
    const view = mount(client, { projectId: 'novel-1' });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(1));
    act(() => view.result.current.toggleIntent('custom'));
    act(() => view.result.current.setCustomLabel('   '));
    expect(view.result.current.customPending).toBe(true);
    expect(view.result.current.canSave).toBe(false);
    await act(async () => { await view.result.current.saveIntent(); });
    expect(saveIntent).not.toHaveBeenCalled();
    expect(view.result.current.problem?.code).toBe('STUDIO_ENTRY_INTENT_LOCAL_INVALID');
  });

  it('makes skipping the intent a first-class action that writes nothing', async () => {
    const { client, saveIntent } = fakeClient({ readIntent: vi.fn(async () => intent(1)) });
    const setItem = vi.spyOn(Storage.prototype, 'setItem');
    const onIntentHandled = vi.fn();
    const view = mount(client, { projectId: 'novel-1', onIntentHandled });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(1));
    act(() => view.result.current.toggleIntent('image_design'));
    expect(view.result.current.dirty).toBe(true);
    act(() => view.result.current.skipIntent());
    expect(saveIntent).not.toHaveBeenCalled();
    expect(view.result.current.dirty).toBe(false);
    expect(view.result.current.values.every(item => !item.selected)).toBe(true);
    expect(view.result.current.notice).toContain('已跳过创作意图设置');
    expect(onIntentHandled).toHaveBeenCalledTimes(1);
    // Nothing in this entry persists a preference to browser storage.
    expect(setItem).not.toHaveBeenCalled();
  });

  it('computes deterministic suggestions from the selected intents only', async () => {
    const { client, saveIntent } = fakeClient({ readIntent: vi.fn(async () => intent(1)) });
    const view = mount(client, { projectId: 'novel-1' });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(1));
    const baseline = view.result.current.suggestions[0].plan_id;
    expect(baseline).toBe('plan:blank');
    act(() => view.result.current.toggleIntent('image_design'));
    const single = view.result.current.suggestions;
    expect(single[0]).toMatchObject({ plan_id: 'plan:image_design', preset: 'IMAGE' });
    expect(single[0].modules).toEqual(['image', 'asset']);
    // Adopting the recommended layout writes the preference and executes nothing.
    await act(async () => { await view.result.current.adoptPlan('plan:image_design'); });
    expect(saveIntent).toHaveBeenCalledTimes(1);
    expect(view.result.current.adoptedPlanId).toBe('plan:image_design');
    expect(view.result.current.notice).toContain('没有生成任何内容');
    // The same selection always yields the same plan list in the same order.
    expect(studioSuggestions(['image_design'])).toEqual(studioSuggestions(['image_design']));
    expect(studioSuggestions(['image_design']).map(plan => plan.plan_id)).toEqual(['plan:image_design', 'plan:blank']);
    expect(studioSuggestions(['image_design', 'podcast_voice']).map(plan => plan.plan_id))
      .toEqual(['plan:image_design', 'plan:podcast_voice', 'plan:image_design+podcast_voice', 'plan:blank']);
  });

  it('keeps the draft when a save fails with an unexpected status', async () => {
    const { client, saveIntent } = fakeClient({
      readIntent: vi.fn(async () => intent(2)), saveIntent: vi.fn(async () => { throw new ApiError({ status: 503, code: 'STUDIO_REQUEST_FAILED', message: '请求未完成。' }); }),
    });
    const view = mount(client, { projectId: 'novel-1' });
    await waitFor(() => expect(view.result.current.intent?.version).toBe(2));
    act(() => view.result.current.toggleIntent('image_design'));
    await act(async () => { await view.result.current.saveIntent(); });
    expect(view.result.current.conflict).toBe(false);
    expect(view.result.current.draft).toBeDefined();
    expect(view.result.current.dirty).toBe(true);
    expect(view.result.current.problem?.code).toBe('STUDIO_REQUEST_FAILED');
    expect(saveIntent).toHaveBeenCalledTimes(1);
  });

  it('offers the blank baseline so a project can start with nothing selected', () => {
    const { client } = fakeClient();
    const view = mount(client, { active: false });
    expect(view.result.current.state).toBe('idle');
    expect(view.result.current.baseline.plan_id).toBe('plan:blank');
    expect(view.result.current.baseline.preset).toBe('BLANK');
    expect(studioBlankIntentValues().length).toBe(STUDIO_INTENT_IDS.length);
  });
});
