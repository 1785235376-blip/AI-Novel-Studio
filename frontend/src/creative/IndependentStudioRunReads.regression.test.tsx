// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import { studioClient, type StudioClient, type StudioOverview } from './studioClient';
import { modelCatalog, modelGraph, modelRun } from './studioGraphModel.testFixtures';
import type { StudioGraphRun } from './studioGraphTypes';

vi.mock('./studioClient', async original => ({ ...await original<typeof import('./studioClient')>(), studioClient: vi.fn() }));
const id = 'model_project';
const overview: StudioOverview = { project: { id, title: 'Read fence project', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' }, capabilities: { can_mutate: true, can_review: true,
    manual_import: true, manual_export: true, model_required: false, chapter_required: false, intent_is_permission: false,
    media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
function deferred<T>() {
  let resolve!: (value: T) => void, reject!: (reason: unknown) => void;
  const promise = new Promise<T>((yes, no) => { resolve = yes; reject = no; }); return { promise, resolve, reject };
}
const denial = (status = 403) => new ApiError({ status, code: 'DENIED', message: 'Denied.' });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
let client: StudioClient;
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({ novelId: id, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: '', actorId: '', epoch: 0 });
  client = { overview: vi.fn().mockResolvedValue(overview), assets: vi.fn().mockResolvedValue({ items: [] }), graphs: {
    catalog: vi.fn().mockResolvedValue(modelCatalog()), list: vi.fn().mockResolvedValue({ items: [modelGraph()] }), get: vi.fn().mockResolvedValue(modelGraph()),
    runs: vi.fn().mockResolvedValue({ items: [modelRun(), modelRun({ id: 'second_run' })] }), getRun: vi.fn().mockResolvedValue(modelRun()),
    action: vi.fn().mockResolvedValue(modelRun({ version: 8, status: 'CANCELLED' })), createRun: vi.fn(),
    modelCapabilities: vi.fn(), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(),
  } } as unknown as StudioClient;
  vi.mocked(studioClient).mockReturnValue(client);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); });
async function enterRuns() {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={id} context={{ sessionToken: '' }}
    scope={{ workspace: 'Local', project: 'Read fence project', storyline: 'Default', branch: 'Main' }} actor="Author" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} /></QueryClientProvider>);
  fireEvent.click(await screen.findByRole('button', { name: '创作图' }));
  await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: 'model_graph' } });
  await waitFor(() => expect((screen.getByRole('button', { name: '读取运行记录' }) as HTMLButtonElement).disabled).toBe(false));
  click('读取运行记录'); return screen.findByRole('combobox', { name: '已保存运行' });
}
async function openFirst() {
  const select = await enterRuns(); fireEvent.change(select, { target: { value: 'model_run' } });
  await screen.findByText('运行 model_run · v2 · 图 v1'); return select;
}

describe('original workspace respects graph read cancellation before denying access', () => {
  it.each([401, 403])('ignores cancelled list denial %i after a reviewed run command finishes', async status => {
    await openFirst(); const older = deferred<{ items: StudioGraphRun[] }>();
    vi.mocked(client.graphs.runs).mockReturnValueOnce(older.promise); click('读取运行记录');
    const signal = vi.mocked(client.graphs.runs).mock.calls[1][1]!;
    click('取消运行'); await screen.findByText('运行 model_run · v8 · 图 v1');
    expect(signal.aborted).toBe(true);
    await act(async () => older.reject(denial(status)));
    expect(screen.queryByText('当前会话无权访问此项目')).toBeNull();
    expect(screen.getByText('运行 model_run · v8 · 图 v1')).toBeTruthy();
    expect(client.graphs.action).toHaveBeenCalledOnce();
    expect(client.graphs.action).toHaveBeenCalledWith('model_run', 'cancel', { expected_version: 2, note: '' });
  });

  it.each([401, 403])('ignores cancelled selection denial %i after the newer exact run loads', async status => {
    const older = deferred<StudioGraphRun>(), newer = deferred<StudioGraphRun>();
    vi.mocked(client.graphs.getRun).mockReturnValueOnce(older.promise).mockReturnValueOnce(newer.promise);
    const select = await enterRuns(); fireEvent.change(select, { target: { value: 'model_run' } });
    fireEvent.change(select, { target: { value: 'second_run' } });
    await act(async () => newer.resolve(modelRun({ id: 'second_run', version: 9 })));
    await screen.findByText('运行 second_run · v9 · 图 v1');
    await act(async () => older.reject(denial(status)));
    expect(screen.queryByText('当前会话无权访问此项目')).toBeNull();
    expect(screen.getByText('运行 second_run · v9 · 图 v1')).toBeTruthy();
    expect(client.graphs.getRun).toHaveBeenCalledTimes(2); expect(client.graphs.action).not.toHaveBeenCalled();
  });

  it.each([401, 403])('still clears private state after a current list denial %i', async status => {
    await openFirst(); vi.mocked(client.graphs.runs).mockRejectedValueOnce(denial(status)); click('读取运行记录');
    await screen.findByText('当前会话无权访问此项目');
    expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull();
    expect(screen.queryByLabelText('创作图标题')).toBeNull();
  });

  it('still denies an active mutation after it supersedes a read-only list', async () => {
    await openFirst(); const older = deferred<{ items: StudioGraphRun[] }>();
    vi.mocked(client.graphs.runs).mockReturnValueOnce(older.promise);
    vi.mocked(client.graphs.action).mockRejectedValueOnce(denial());
    click('读取运行记录'); click('取消运行'); await screen.findByText('当前会话无权访问此项目');
    await act(async () => older.resolve({ items: [modelRun()] }));
    expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull();
    expect(client.graphs.action).toHaveBeenCalledOnce();
  });
});
