// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api, setCollaborationContext} from '../api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import {ModelCenter} from './ModelCenter';
const fetchMock = vi.fn();
const snapshot = (cpu = 'private-original-cpu') => ({scan: null, registrations: [], settings: {scan_roots: [], runtimes: []}, hardware: {cpu, gpus: []}});
const bind = (token = 'original-host') => bindLocalHostSession(token, {session_mode: 'LOCAL_HOST', actor_id: 'host'});
beforeEach(() => {
  setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: '', novelId: 'project', actor: undefined, scope: undefined}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); bind();
  vi.spyOn(api, 'modelCenterModels').mockResolvedValue({items: []}); vi.spyOn(api, 'modelCenterRuntimes').mockResolvedValue({items: []}); vi.spyOn(api, 'modelCenterPipelines').mockResolvedValue({items: []}); vi.spyOn(api, 'modelCenterHealth').mockResolvedValue({status: 'READY', mutation_authorization: {can_mutate: true, mutation_auth_mode: 'TRUSTED_SESSION'}});
  fetchMock.mockReset().mockImplementation(async () => new Response(JSON.stringify(snapshot()))); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});});
describe('default-off Model Center keeps existing shared controls and scoped discovery ownership', () => {
  it('loads health and discovery under the same bound host while preserving the legacy scan UI', async () => {
    render(<ModelCenter/>); await screen.findByText('暂无模型'); await screen.findByText('private-original-cpu');
    expect((screen.getByRole('button', {name: '检测本机 AI 环境'}) as HTMLButtonElement).disabled).toBe(false); expect(screen.queryByRole('button', {name: '预览 AI 检测范围'})).toBeNull();
    expect(fetchMock.mock.calls[0][1].headers['X-Session-Token']).toBe('original-host'); expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  });
  it.each(['different token', 'same token ABA'])('clears private view and refetches health on host epoch change: %s', async transition => {
    render(<ModelCenter/>); await screen.findByText('private-original-cpu'); await screen.findByText('暂无模型');
    fetchMock.mockImplementation(async () => new Response(JSON.stringify(snapshot('current-cpu'))));
    act(() => {clearLocalHostSession(); bind(transition === 'same token ABA' ? 'original-host' : 'next-host');}); await screen.findByText('current-cpu');
    expect(screen.queryByText('private-original-cpu')).toBeNull(); expect(api.modelCenterHealth).toHaveBeenCalledTimes(2); expect(fetchMock.mock.calls.at(-1)![1].headers['X-Session-Token']).toBe(transition === 'same token ABA' ? 'original-host' : 'next-host'); expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
  });
  it('purges discovery when shared health revokes mutation without changing shared registry access', async () => {
    render(<ModelCenter/>); await screen.findByText('private-original-cpu'); await screen.findByText('暂无模型');
    vi.mocked(api.modelCenterHealth).mockResolvedValue({status: 'READY', mutation_authorization: {can_mutate: false, mutation_auth_mode: 'TRUSTED_SESSION_REQUIRED'}}); fireEvent.click(screen.getByRole('button', {name: '刷新'}));
    await act(async () => {}); expect(screen.queryByText('private-original-cpu')).toBeNull(); expect((screen.getByRole('button', {name: '检测本机 AI 环境'}) as HTMLButtonElement).disabled).toBe(true); expect(api.modelCenterModels).toHaveBeenCalledTimes(2); expect(api.modelCenterRuntimes).toHaveBeenCalledTimes(2); expect(screen.getByText('暂无模型')).toBeTruthy();
  });
});
