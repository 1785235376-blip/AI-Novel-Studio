// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import type { CollaborationContext } from '../api';
import { useStudio } from '../store';
import { useLocalHostSession } from '../localHostSession';
import { IndependentStudioWorkspace } from './IndependentStudioWorkspace';
import type { StudioOverview } from './studioClient';
import { modelCatalog, modelGraph } from './studioGraphModel.testFixtures';
import { storedTextAssetRun } from './studioGraphTextAsset.testFixtures';

const projectId = 'model_project', base = `/api/projects/${projectId}/studio`;
const overview: StudioOverview = { project: { id: projectId, title: '原身份私有项目', entry_kind: 'NEUTRAL_STUDIO' },
  preferences: { version: 1, intents: [], preset: 'BLANK', custom_intent: '' },
  capabilities: { can_mutate: true, manual_import: true, manual_export: true, model_required: false, chapter_required: false,
    intent_is_permission: false, media_validator_configured: true, asset_kinds: ['image', 'video', 'audio'] } };
const reply = (body: unknown, status = 200) => ({ ok: status >= 200 && status < 300, status, json: async () => body });
function deferred<T>() {
  let resolve!: (value: T) => void;
  const promise = new Promise<T>(done => { resolve = done; });
  return { promise, resolve };
}
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  localStorage.clear();
  useStudio.setState({ novelId: projectId, chapterId: '', sessionToken: '', actor: undefined, scope: undefined });
  useLocalHostSession.setState({ token: 'host-original', actorId: 'host-author', epoch: 10 });
  fetchMock = vi.fn(async (url: string) => {
    if (url === base) return reply(overview);
    if (url.startsWith(`${base}/assets?`)) return reply({ items: [] });
    throw new Error(`Unexpected request: ${url}`);
  });
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

function mount(context: CollaborationContext = { sessionToken: '' }) {
  const query = new QueryClient({ defaultOptions: { queries: { retry: false }, mutations: { retry: false } } });
  const onVerified = vi.fn();
  return { ...render(<QueryClientProvider client={query}><IndependentStudioWorkspace projectId={projectId} context={context}
    scope={{ workspace: '工作区', project: '待核对项目', storyline: '默认', branch: '主线' }} actor="作者" module="IMAGE"
    onModuleChange={vi.fn()} onProjectChoice={vi.fn()} onVerified={onVerified} /></QueryClientProvider>), onVerified };
}

const localChanges: [string, () => void][] = [
  ['project ABA', () => { useStudio.setState({ novelId: 'another-project' }); useStudio.setState({ novelId: projectId }); }],
  ['session ABA', () => { useStudio.setState({ sessionToken: 'other-session' }); useStudio.setState({ sessionToken: '' }); }],
  ['Host token ABA', () => { useLocalHostSession.setState({ token: 'host-other' }); useLocalHostSession.setState({ token: 'host-original' }); }],
  ['Host actor ABA', () => { useLocalHostSession.setState({ actorId: 'host-other-author' }); useLocalHostSession.setState({ actorId: 'host-author' }); }],
  ['Host epoch ABA', () => { useLocalHostSession.setState({ epoch: 11 }); useLocalHostSession.setState({ epoch: 10 }); }],
  ['same-credential Host rebind', () => { useLocalHostSession.setState({ epoch: 11 }); }],
];

describe('independent Studio captured identity cannot revive before React effects', () => {
  it.each(localChanges)('rejects a delayed overview after synchronous %s', async (_label, changeIdentity) => {
    const pending = deferred<ReturnType<typeof reply>>();
    fetchMock.mockReturnValueOnce(pending.promise);
    const { onVerified } = mount();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());

    act(changeIdentity);
    await act(async () => pending.resolve(reply(overview)));

    expect(onVerified).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '上传资产' })).toBeNull();
    expect(screen.queryByText('项目：原身份私有项目')).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it.each(['actor', 'scope'] as const)('rejects a delayed collaboration overview after synchronous %s ABA', async field => {
    const context: CollaborationContext = { sessionToken: 'session-original', actor: { id: 'author-original', displayName: 'Author', workspaceId: 'workspace' },
      scope: { projectId, workspaceId: 'workspace', storylineId: 'storyline', branchId: 'branch-original' } };
    useStudio.setState({ sessionToken: context.sessionToken, actor: context.actor, scope: context.scope });
    const pending = deferred<ReturnType<typeof reply>>();
    fetchMock.mockReturnValueOnce(pending.promise);
    const { onVerified } = mount(context);
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());

    act(() => {
      if (field === 'actor') {
        useStudio.setState({ actor: { ...context.actor!, id: 'other-author' } });
        useStudio.setState({ actor: context.actor });
      } else {
        useStudio.setState({ scope: { ...context.scope!, branchId: 'other-branch' } });
        useStudio.setState({ scope: context.scope });
      }
    });
    await act(async () => pending.resolve(reply(overview)));

    expect(onVerified).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '上传资产' })).toBeNull();
    expect(fetchMock).toHaveBeenCalledOnce();
  });

  it('cannot submit a delayed local file after the project returns to its original value', async () => {
    mount();
    await screen.findByRole('button', { name: '上传资产' });
    const bytes = deferred<ArrayBuffer>(), file = new File(['private'], 'private.png', { type: 'image/png' });
    Object.defineProperty(file, 'arrayBuffer', { value: () => bytes.promise });
    fireEvent.change(screen.getByLabelText('选择要上传的资产文件'), { target: { files: [file] } });

    act(localChanges[0][1]);
    await act(async () => bytes.resolve(new Uint8Array([1, 2, 3]).buffer));

    expect(fetchMock.mock.calls.filter(([, init]) => init.method !== 'GET')).toEqual([]);
  });

  it('still adopts an overview when only non-authority editor state changes', async () => {
    const pending = deferred<ReturnType<typeof reply>>();
    fetchMock.mockReturnValueOnce(pending.promise);
    const { onVerified } = mount();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    act(() => useStudio.setState({ chapterId: 'another-chapter', writingInputs: { styleProfileId: 'style' } }));
    await act(async () => pending.resolve(reply(overview)));
    expect(onVerified.mock.calls).toEqual([[projectId]]);
    expect(await screen.findByRole('button', { name: '上传资产' })).toBeTruthy();
  });

  it.each([401, 403])('keeps a current authoritative overview denial %i effective', async status => {
    const pending = deferred<ReturnType<typeof reply>>();
    fetchMock.mockReturnValueOnce(pending.promise);
    const { onVerified } = mount();
    await waitFor(() => expect(fetchMock).toHaveBeenCalledOnce());
    await act(async () => pending.resolve(reply({ code: 'FORBIDDEN' }, status)));
    expect(screen.getByText('当前会话无权访问此项目')).toBeTruthy();
    expect(onVerified).not.toHaveBeenCalled();
    expect(screen.queryByRole('button', { name: '上传资产' })).toBeNull();
  });

  it('admits a newly mounted owner after the old instance was permanently invalidated', async () => {
    const first = mount(); await screen.findByRole('button', { name: '上传资产' });
    act(localChanges[0][1]);
    first.unmount();
    const second = mount();
    await screen.findByRole('button', { name: '上传资产' });
    expect(second.onVerified.mock.calls).toEqual([[projectId]]);
  });

  it.each(['project', 'session', 'actor', 'branch', 'actor workspace'] as const)(
    'immediately hides an adopted private run receipt after synchronous %s ABA and rejects a late list', async field => {
      const context: CollaborationContext = { sessionToken: 'session-original', actor: { id: 'author-original', displayName: 'Author', workspaceId: 'workspace' },
        scope: { projectId, workspaceId: 'workspace', storylineId: 'storyline', branchId: 'branch-original' } };
      useStudio.setState({ sessionToken: context.sessionToken, actor: context.actor, scope: context.scope });
      const ownerScope = { mode: 'collaboration' as const, novel_id: projectId, workspace_id: 'workspace', storyline_id: 'storyline', branch_id: 'branch-original' };
      const graph = { ...modelGraph(), scope: ownerScope }, run = { ...storedTextAssetRun(), scope: ownerScope };
      const pending = deferred<ReturnType<typeof reply>>();
      let deferList = false;
      fetchMock.mockImplementation(async (url: string) => {
        if (url === base) return reply(overview);
        if (url.startsWith(`${base}/assets?`)) return reply({ items: [] });
        if (url === `${base}/graphs/catalog`) return reply(modelCatalog());
        if (url === `${base}/graphs`) return reply({ items: [graph] });
        if (url === `${base}/graphs/model_graph`) return reply(graph);
        if (url === `${base}/graphs/model_graph/runs`) return deferList ? pending.promise : reply({ items: [run] });
        if (url === `${base}/graph-runs/model_run`) return reply(run);
        throw new Error(`Unexpected request: ${url}`);
      });
      mount(context);
      fireEvent.click(await screen.findByRole('button', { name: '创作图' }));
      await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));
      fireEvent.change(screen.getByLabelText('已保存创作图'), { target: { value: graph.id } });
      await waitFor(() => expect((screen.getByRole('button', { name: '读取运行记录' }) as HTMLButtonElement).disabled).toBe(false));
      fireEvent.click(screen.getByRole('button', { name: '读取运行记录' }));
      fireEvent.change(await screen.findByRole('combobox', { name: '已保存运行' }), { target: { value: run.id } });
      await screen.findByText(/private_text_asset/);
      expect(screen.getByText('Saved proposed text')).toBeTruthy();
      expect(screen.getByText('Complete reviewed author input')).toBeTruthy();
      deferList = true;
      fireEvent.click(screen.getByRole('button', { name: '读取运行记录' }));
      const requests = fetchMock.mock.calls.length;

      act(() => {
        if (field === 'project') { useStudio.setState({ novelId: 'other-project' }); useStudio.setState({ novelId: projectId }); }
        else if (field === 'session') { useStudio.setState({ sessionToken: 'other-session' }); useStudio.setState({ sessionToken: context.sessionToken }); }
        else if (field === 'branch') {
          useStudio.setState({ scope: { ...context.scope!, branchId: 'other-branch' } }); useStudio.setState({ scope: context.scope });
        } else {
          useStudio.setState({ actor: { ...context.actor!, ...(field === 'actor' ? { id: 'other-author' } : { workspaceId: 'other-workspace' }) } });
          useStudio.setState({ actor: context.actor });
        }
      });

      for (const privateText of [/private_text_asset/, /Saved proposed text/, /Complete reviewed author input/, /original_job/]) {
        expect(screen.queryByText(privateText)).toBeNull();
      }
      expect(screen.queryByRole('combobox', { name: '已保存创作图' })).toBeNull();
      expect(screen.queryByDisplayValue(graph.definition.title)).toBeNull();
      expect(screen.queryByText(/原身份私有项目/)).toBeNull();
      expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull();
      await act(async () => pending.resolve(reply({ items: [run] })));
      expect(screen.queryByRole('region', { name: '当前创作图运行' })).toBeNull();
      expect(document.body.textContent).not.toMatch(/private_text_asset|Saved proposed text|Complete reviewed author input|original_job/);
      expect(fetchMock).toHaveBeenCalledTimes(requests);
    });

  it('keeps only unsaved author text read-only while hiding private graph directory metadata', async () => {
    fetchMock.mockImplementation(async (url: string) => {
      if (url === base) return reply(overview);
      if (url.startsWith(`${base}/assets?`)) return reply({ items: [] });
      if (url === `${base}/graphs/catalog`) return reply(modelCatalog());
      if (url === `${base}/graphs`) return reply({ items: [{ ...modelGraph(), definition: { ...modelGraph().definition, title: '私有目录标题' } }] });
      throw new Error(`Unexpected request: ${url}`);
    });
    mount(); fireEvent.click(await screen.findByRole('button', { name: '创作图' }));
    await waitFor(() => expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(false));
    fireEvent.change(screen.getByLabelText('创作图标题'), { target: { value: '未保存作者标题' } });
    fireEvent.click(screen.getByRole('button', { name: '添加节点' }));
    fireEvent.change(screen.getByLabelText('作者输入文本'), { target: { value: '未保存作者文字' } });
    expect(screen.getByRole('option', { name: /私有目录标题/ })).toBeTruthy();
    const requests = fetchMock.mock.calls.length;

    act(localChanges[0][1]);

    expect((screen.getByLabelText('创作图标题') as HTMLInputElement).value).toBe('未保存作者标题');
    expect((screen.getByLabelText('创作图标题') as HTMLInputElement).disabled).toBe(true);
    expect((screen.getByLabelText('作者输入文本') as HTMLTextAreaElement).value).toBe('未保存作者文字');
    expect((screen.getByLabelText('作者输入文本') as HTMLTextAreaElement).disabled).toBe(true);
    expect(screen.queryByRole('option', { name: /私有目录标题/ })).toBeNull();
    expect(screen.queryByRole('button', { name: '保存创作图' })).toBeNull();
    expect(fetchMock).toHaveBeenCalledTimes(requests);
  });
});
