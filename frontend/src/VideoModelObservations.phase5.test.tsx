// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {api, setCollaborationContext} from './api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from './localHostSession';
import {useStudio} from './store';
import {localAiDiscoveryApi, localAiDiscoveryClient, checkedVideoObservations} from './localAiDiscoveryApi';
import {VideoModelObservationSummary} from './AIEnvironmentSummary';
import {ModelCenter} from './ui/ModelCenter';
import captured from './creative/fixtures/phase5.file-api-video-environment.json';

// Actual mounted API capture with tiny synthetic metadata. Only the generated
// test root was replaced; this is not proof of weights, GPU or real inference.
const copy = <T,>(value: T): T => structuredClone(value);
const observed = () => copy(captured.video_observations);
const wan = () => observed().models.find(model => model.family === 'WAN')!;
const fetchMock = vi.fn();
const owner = {context: {sessionToken: ''}, projectId: 'project'};
beforeEach(() => {
  setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: '', novelId: 'project', actor: undefined, scope: undefined});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); bindLocalHostSession('synthetic-host', {session_mode: 'LOCAL_HOST', actor_id: 'synthetic'});
  fetchMock.mockReset(); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); setCollaborationContext({sessionToken: ''});
  useStudio.setState({sessionToken: '', novelId: '', actor: undefined, scope: undefined}); useLocalHostSession.setState({token: '', actorId: '', epoch: 0});});

describe('Optional exact video observation contract keeps original controls separate', () => {
  it('decodes the mounted synthetic report and preserves unknown model total and VRAM', () => {
    expect(checkedVideoObservations(observed())).toEqual(captured.video_observations);
    expect(wan().file_association.status).toBe('MATCHED'); expect(wan().model_total_bytes).toBeNull(); expect(wan().required_vram_bytes).toBeNull();
    expect(wan().enable_eligible).toBe(false); expect(wan().file_association.runtime_path_verified).toBe(false);
  });
  it.each(['health_probed', 'credentials_read', 'automatic_runtime_start'] as const)('rejects a claimed %s side effect', field => {
    const value = observed(); (value as unknown as Record<string, unknown>)[field] = true; expect(() => checkedVideoObservations(value)).toThrow();
  });
  it.each(['inference_verified', 'model_total_bytes', 'required_vram_bytes', 'structural_only', 'registered'] as const)('rejects unsafe claimed model %s', field => {
    const value = observed(), model = value.models[0] as unknown as Record<string, unknown>;
    model[field] = field === 'structural_only' ? false : field === 'registered' ? 'true' : field === 'inference_verified' ? true : 1234;
    expect(() => checkedVideoObservations(value)).toThrow();
  });
  it('rejects extra commands, duplicate identities and an unevidenced path on ambiguity', () => {
    const extra = {...observed(), argv: ['never-run']}; expect(() => checkedVideoObservations(extra)).toThrow();
    const repeated = observed(); repeated.models.push(copy(repeated.models[0])); expect(() => checkedVideoObservations(repeated)).toThrow();
    const ambiguous = observed(), model = ambiguous.models.find(model => model.family === 'WAN')!;
    model.file_association.status = 'AMBIGUOUS'; expect(() => checkedVideoObservations(ambiguous)).toThrow();
  });
  it('never interprets Diffusers index bytes as model size', () => {
    const value = observed(), file = value.files[0]; file.format = 'DIFFUSERS'; file.size_semantics = 'INDEX_METADATA';
    expect(checkedVideoObservations(value).files[0].model_total_bytes).toBeNull(); file.size_semantics = 'WEIGHT_FILE';
    expect(() => checkedVideoObservations(value)).toThrow();
  });
  it('retains original absent-field compatibility and decodes both existing protected GETs', async () => {
    fetchMock.mockResolvedValueOnce(new Response('{}')).mockResolvedValueOnce(new Response(JSON.stringify(captured)))
      .mockResolvedValueOnce(new Response(JSON.stringify({scan: null, video_observations: observed()})));
    expect(await localAiDiscoveryApi.environment()).toEqual({});
    expect((await localAiDiscoveryClient(owner.context).environment()).video_observations).toEqual(observed());
    expect((await localAiDiscoveryClient(owner.context).snapshot()).video_observations).toEqual(observed());
    expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET' && init.body === undefined && init.headers['X-Session-Token'] === 'synthetic-host')).toBe(true);
  });
  it('rejects a malformed optional report instead of lending enable authority', async () => {
    const unsafe = observed(); unsafe.models[0].enabled = true;
    fetchMock.mockResolvedValueOnce(new Response(JSON.stringify({...captured, video_observations: unsafe})));
    await expect(localAiDiscoveryClient(owner.context).environment()).rejects.toMatchObject({problem: {code: 'LOCAL_AI_VIDEO_OBSERVATION_INVALID'}});
    expect(fetchMock).toHaveBeenCalledOnce();
  });
});

describe('Existing Model Center presents observation without model control or private paths', () => {
  function center() {
    vi.spyOn(api, 'modelCenterModels').mockResolvedValue({items: []}); vi.spyOn(api, 'modelCenterRuntimes').mockResolvedValue({items: []});
    vi.spyOn(api, 'modelCenterPipelines').mockResolvedValue({items: []}); vi.spyOn(api, 'modelCenterHealth').mockResolvedValue({status: 'READY', mutation_authorization: {can_mutate: true, mutation_auth_mode: 'TRUSTED_SESSION'}});
    fetchMock.mockImplementation(async (url: string) => new Response(JSON.stringify(url.endsWith('/environment') ? captured : {scan: null, registrations: [], settings: {scan_roots: [], runtimes: []}, hardware: {gpus: []}})));
    return render(<ModelCenter onboarding={owner}/>);
  }
  it('shows filenames and honest registration/association labels without paths or requests', () => {
    const value = checkedVideoObservations(observed()), view = render(<VideoModelObservationSummary report={value}/>);
    expect(screen.getByText(/配置目录已观察，运行时路径未确认/)).toBeTruthy(); expect(screen.getAllByText(/未登记 · 未启用 · 原路由未确认/)).toHaveLength(value.models.length);
    expect(view.container.textContent).not.toContain('/SYNTHETIC_MODEL_ROOT'); expect(view.container.textContent).not.toContain('http://');
    expect(fetchMock).not.toHaveBeenCalled(); expect(screen.queryByRole('button')).toBeNull();
  });
  it('only reads observations after an explicit action on the original owner', async () => {
    const view = center(); await screen.findByText('暂无模型');
    expect(fetchMock.mock.calls.some(([url]) => url.endsWith('/environment'))).toBe(false);
    fireEvent.click(screen.getByRole('button', {name: '读取已有视频模型观察'})); await screen.findByText(/配置目录已观察，运行时路径未确认/);
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/environment'))).toHaveLength(1);
    expect(fetchMock.mock.calls.every(([, init]) => init.method === 'GET')).toBe(true);
    expect(view.container.textContent).not.toContain('/SYNTHETIC_MODEL_ROOT');
  });
  it('drops private observations on existing health revocation', async () => {
    center(); await screen.findByText('暂无模型'); fireEvent.click(screen.getByRole('button', {name: '读取已有视频模型观察'})); await screen.findByText(/配置目录已观察，运行时路径未确认/);
    vi.mocked(api.modelCenterHealth).mockResolvedValue({status: 'READY', mutation_authorization: {can_mutate: false, mutation_auth_mode: 'TRUSTED_SESSION_REQUIRED'}});
    fireEvent.click(screen.getByRole('button', {name: '刷新'})); await waitFor(() => expect(screen.queryByText(/配置目录已观察，运行时路径未确认/)).toBeNull());
    expect((screen.getByRole('button', {name: '读取已有视频模型观察'}) as HTMLButtonElement).disabled).toBe(true);
  });
  it('retires an in-flight observation when the same Host health refresh revokes permission', async () => {
    center(); await screen.findByText('暂无模型'); let resolve!: (value: Response) => void;
    const late = new Promise<Response>(accept => {resolve = accept;}); fetchMock.mockImplementationOnce(() => late);
    vi.mocked(api.modelCenterHealth).mockResolvedValue({status: 'READY', mutation_authorization: {can_mutate: false, mutation_auth_mode: 'TRUSTED_SESSION_REQUIRED'}});
    // Both requests leave the last authorized render before the original
    // refresh resolves; a same-Host result cannot restore its retired report.
    act(() => {fireEvent.click(screen.getByRole('button', {name: '刷新'})); fireEvent.click(screen.getByRole('button', {name: '读取已有视频模型观察'}));});
    expect(fetchMock.mock.calls.filter(([url]) => url.endsWith('/environment'))).toHaveLength(1);
    await waitFor(() => expect((screen.getByRole('button', {name: '读取已有视频模型观察'}) as HTMLButtonElement).disabled).toBe(true));
    await act(async () => {resolve(new Response(JSON.stringify(captured))); await late;});
    expect(screen.queryByText(/配置目录已观察，运行时路径未确认/)).toBeNull();
  });
  it('never adopts a late observation after Host ownership changes', async () => {
    center(); await screen.findByText('暂无模型'); let resolve!: (value: Response) => void;
    const late = new Promise<Response>(accept => {resolve = accept;}); fetchMock.mockImplementationOnce(() => late);
    fireEvent.click(screen.getByRole('button', {name: '读取已有视频模型观察'}));
    act(() => {clearLocalHostSession(); bindLocalHostSession('replacement-host', {session_mode: 'LOCAL_HOST', actor_id: 'replacement'});});
    await act(async () => {resolve(new Response(JSON.stringify(captured))); await late;});
    expect(screen.queryByText(/配置目录已观察，运行时路径未确认/)).toBeNull();
  });
});
