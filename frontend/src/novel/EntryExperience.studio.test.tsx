// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { api, setCollaborationContext } from '../api';
import { EntryExperience } from './EntryExperience';

vi.mock('./FirstUsePanel', () => ({ FirstUsePanel: () => null }));
vi.mock('./NovelImportPanel', () => ({ NovelImportPanel: () => null }));
const workspace = { id: 'authorized-workspace', name: '已有创作空间' };
const path = { workspace_id: workspace.id, project_id: 'new-shared-project', storyline_id: 'server-storyline', branch_id: 'server-branch', project_name: '共享空白项目' };
let fetchMock: ReturnType<typeof vi.fn>;
beforeEach(() => {
  vi.spyOn(api, 'adminWorkspaces').mockResolvedValue([workspace]);
  vi.spyOn(api, 'adminWorkspaceNavigation').mockResolvedValue({ workspace_id: workspace.id, eligible_paths: [], default_path: null });
  vi.spyOn(api, 'adminCreateProject').mockResolvedValue({ id: path.project_id, title: path.project_name } as any);
  fetchMock = vi.fn(async () => ({ ok: true, status: 200, json: async () => ({ project: { id: path.project_id, title: path.project_name, entry_kind: 'NEUTRAL_STUDIO' } }) }));
  vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => { cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({ sessionToken: '' }); });
async function open(enabled = true, onEnter = vi.fn()) {
  const view = render(<EntryExperience initialToken="original-session" onEnter={onEnter} independentStudioEnabled={enabled} />);
  fireEvent.click(await screen.findByRole('button', { name: workspace.name }));
  await screen.findByRole('heading', { name: '新建小说' });
  return view;
}
async function create() {
  fireEvent.change(await screen.findByLabelText('空白项目名称'), { target: { value: path.project_name } });
  fireEvent.click(screen.getByRole('button', { name: '创建空白项目' }));
}

it('keeps the independent entry absent when the server feature consumer is off', async () => {
  await open(false);
  expect(screen.queryByLabelText('空白项目名称')).toBeNull();
  expect(screen.queryByRole('button', { name: '创建空白项目' })).toBeNull();
  expect(fetchMock).not.toHaveBeenCalled();
});

it('creates through the existing admin owner, resolves eligible scope, then explicitly activates that scope', async () => {
  const enter = vi.fn(); await open(true, enter);
  vi.mocked(api.adminWorkspaceNavigation).mockResolvedValue({ workspace_id: workspace.id, eligible_paths: [path], default_path: path });
  await create();
  await waitFor(() => expect(enter).toHaveBeenCalledWith('original-session', expect.objectContaining({ workspaceId: workspace.id, projectId: path.project_id, storylineId: path.storyline_id, branchId: path.branch_id })));
  expect(api.adminCreateProject).toHaveBeenCalledWith(workspace.id, path.project_name, '', { sessionToken: 'original-session' });
  expect(api.adminWorkspaceNavigation).toHaveBeenLastCalledWith(workspace.id, { sessionToken: 'original-session' });
  expect(fetchMock).toHaveBeenCalledTimes(1);
  expect(fetchMock.mock.calls[0][0]).toBe(`/api/projects/${path.project_id}/studio/activate`);
  expect(fetchMock.mock.calls[0][1]).toMatchObject({ method: 'POST', headers: { 'X-Session-Token': 'original-session', 'X-Branch-Id': path.branch_id } });
  expect(fetchMock.mock.calls.some(([url]) => url === '/api/experimental/projects')).toBe(false);
});

it('does not manufacture a branch when the created project has no eligible path', async () => {
  const enter = vi.fn(); await open(true, enter); await create();
  await screen.findByText('项目已创建，但当前身份没有可用创作分支。请核对权限后从项目列表打开。');
  expect(enter).not.toHaveBeenCalled(); expect(fetchMock).not.toHaveBeenCalled();
  expect(api.adminCreateProject).toHaveBeenCalledTimes(1);
});

it('does not activate or enter a scope after the originating picker has unmounted', async () => {
  let finish!: (value: any) => void;
  vi.mocked(api.adminCreateProject).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const enter = vi.fn(); const view = await open(true, enter); await create(); view.unmount();
  await act(async () => finish({ id: path.project_id, title: path.project_name }));
  expect(fetchMock).not.toHaveBeenCalled(); expect(enter).not.toHaveBeenCalled();
  expect(api.adminWorkspaceNavigation).toHaveBeenCalledTimes(1);
});

it('stops before navigation when the global authority changes during project creation', async () => {
  let finish!: (value: any) => void;
  vi.mocked(api.adminCreateProject).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  const enter = vi.fn(); await open(true, enter); await create();
  expect(api.adminCreateProject).toHaveBeenCalledWith(workspace.id, path.project_name, '', { sessionToken: 'original-session' });
  setCollaborationContext({ sessionToken: 'different-session' });
  await act(async () => finish({ id: path.project_id, title: path.project_name }));
  await screen.findByText('创作空间已改变。项目已保留，请从原空间重新打开。');
  expect(api.adminWorkspaceNavigation).toHaveBeenCalledTimes(1);
  expect(fetchMock).not.toHaveBeenCalled(); expect(enter).not.toHaveBeenCalled();
});

it('keeps navigation bound to the captured context and rejects a late result after authority changes', async () => {
  let finish!: (value: any) => void;
  const enter = vi.fn(); await open(true, enter);
  vi.mocked(api.adminWorkspaceNavigation).mockImplementation(() => new Promise(resolve => { finish = resolve; }));
  await create();
  await waitFor(() => expect(api.adminWorkspaceNavigation).toHaveBeenLastCalledWith(workspace.id, { sessionToken: 'original-session' }));
  setCollaborationContext({ sessionToken: 'different-session' });
  await act(async () => finish({ workspace_id: workspace.id, eligible_paths: [path], default_path: path }));
  await screen.findByText('创作空间已改变。项目已保留，请重新选择。');
  expect(fetchMock).not.toHaveBeenCalled(); expect(enter).not.toHaveBeenCalled();
});
