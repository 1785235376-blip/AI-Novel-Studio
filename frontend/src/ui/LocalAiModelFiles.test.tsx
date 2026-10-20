// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type CollaborationContext} from '../api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import type {EnvironmentModelFile, LocalDiscoveryScan, LocalDiscoverySnapshot, LocalModelCandidate, LocalModelRegistration} from '../localAiDiscoveryApi';
import {LocalAiDiscovery} from './LocalAiDiscovery';

const context: CollaborationContext = {sessionToken: 'model-file-host'};
const candidate = (extra: Partial<LocalModelCandidate> = {}): LocalModelCandidate => ({
  id: 'candidate-a', display_name: 'same-model', model_id: 'same-model', family: 'QWEN', modality: 'TEXT',
  declared_capabilities: ['TEXT'], verified_capabilities: [], runtime_id: 'runtime-a', runtime_type: 'LLAMA_CPP',
  source: 'GGUF', model_name: 'same-model.gguf', status: 'DISCOVERED', compatible: 'NOT_VERIFIED',
  verified: false, validation_notes: [], evidence: {}, ...extra,
});
const file = (extra: Partial<EnvironmentModelFile> = {}): EnvironmentModelFile => ({
  id: 'path-identity-a', path: '/private/models/same-model.safetensors', name: 'same-model.safetensors',
  format: 'SAFETENSORS', source: 'CONFIGURED', root: '/private/models', size_bytes: 8192, modified_ns: 123,
  header_valid: true, family: 'STABLE_DIFFUSION', declared_capabilities: ['IMAGE'], candidate_ids: [],
  notes: [], inference_verified: false, ...extra,
});
// The additive scan projection deliberately allows historical scans with absent fields.
type ScanFixture = LocalDiscoveryScan & {environment_schema_version?: number; model_files?: EnvironmentModelFile[]; roots?: {path: string; source: 'CONFIGURED' | 'COMMON'; status: 'SCANNED' | 'BOUNDED' | 'NOT_FOUND' | 'CANCELLED'}[]};
const scan = (extra: Partial<ScanFixture> = {}): ScanFixture => ({
  id: 'scan-files-1', status: 'COMPLETED', runtimes: [], candidates: [], errors: [],
  started_at: '2026-10-09T12:00:00Z', finished_at: '2026-10-09T12:00:02Z', environment_schema_version: 2,
  model_files: [file()], roots: [{path: '/private/models', source: 'CONFIGURED', status: 'SCANNED'}], ...extra,
});
const snapshot = (value: LocalDiscoveryScan | null = scan(), registrations: LocalModelRegistration[] = []): LocalDiscoverySnapshot => ({
  scan: value, registrations, settings: {scan_roots: [], runtimes: []}, hardware: {},
});
const registration = (extra: Partial<LocalModelRegistration> = {}): LocalModelRegistration => ({...candidate(), id: 'registration-a', candidate_id: 'candidate-a', enabled: true, ...extra});
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status});
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};};
let currentSnapshot: LocalDiscoverySnapshot;
const fetchMock = vi.fn();
const observationView = () => screen.getByRole('region', {name: '本次扫描的文件与索引观察'});
const observation = (name = 'same-model.safetensors') => within(observationView()).getByRole('article', {name: `${name} 文件观察`});
async function mount(owner = context, legacy = false) {
  let view!: ReturnType<typeof render>;
  await act(async () => {view = render(<LocalAiDiscovery canMutate {...(legacy ? {} : {onboarding: {context: owner, projectId: 'project-files'}})}/>);});
  return view;
}
beforeEach(() => {
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  useStudio.setState({novelId: 'project-files', sessionToken: context.sessionToken, scope: undefined, actor: undefined});
  setCollaborationContext(context); currentSnapshot = snapshot();
  fetchMock.mockReset(); fetchMock.mockImplementation(async () => response(currentSnapshot)); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); useStudio.setState({novelId: '', sessionToken: '', scope: undefined, actor: undefined});
});

describe('V2 same-scan model file observations', () => {
  it('shows Safetensors without claiming no models or runtime absence, and reads no additional endpoint', async () => {
    await mount(); const row = observation();
    expect(row.textContent).toContain('SAFETENSORS'); expect(row.textContent).toContain('8192 bytes');
    expect(row.textContent).toContain('Runtime 绑定未知'); expect(row.textContent).toContain('名称推断提示');
    expect(row.textContent).toContain('有界元数据结构检查通过'); expect(row.textContent).toContain('NOT_RUN');
    expect(screen.queryByText('尚未发现模型')).toBeNull(); expect(screen.getByText('尚无可接入候选')).toBeTruthy();
    expect(observationView().textContent).toContain('2026-10-09T12:00:02Z');
    expect(fetchMock.mock.calls.every(([url, init]) => url === '/api/model-center/local-ai' && init.method === 'GET')).toBe(true);
    for (const summary of within(observationView()).getAllByText(/高级：查看/)) expect((summary.parentElement as HTMLDetailsElement).open).toBe(false);
    expect(row.textContent).toContain('路径身份 ID（非内容哈希）');
  });
  it('labels Diffusers path and size as model_index.json evidence, never whole weights or a complete installation', async () => {
    currentSnapshot = snapshot(scan({model_files: [file({format: 'DIFFUSERS', name: 'image-pipeline', path: '/private/models/image-pipeline/model_index.json', size_bytes: 512})]}));
    await mount(); const row = observation('image-pipeline');
    expect(row.textContent).toContain('索引大小'); expect(row.textContent).toContain('512 bytes');
    expect(row.textContent).toContain('model_index.json'); expect(row.textContent).toContain('不代表目录或权重总大小');
    expect(row.textContent).toContain('未验证组件完整性'); expect(row.textContent).toContain('Runtime 绑定未知');
    expect(within(row).queryByText('模型大小')).toBeNull();
  });
  it('links a GGUF only to exact candidates in this scan and their exact registration IDs', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate(), candidate({id: 'candidate-b', runtime_id: 'runtime-b', runtime_type: 'OLLAMA'})], model_files: [file({format: 'GGUF', name: 'same-model.gguf', candidate_ids: ['candidate-a']})]}), [registration(), registration({id: 'registration-b', candidate_id: 'candidate-b', enabled: false})]);
    await mount(); const row = observation('same-model.gguf');
    expect(row.textContent).toContain('LLAMA_CPP · runtime-a'); expect(row.textContent).toContain('已授权路由');
    expect(row.textContent).not.toContain('runtime-b'); expect(row.textContent).not.toContain('已注册 · 未启用');
    expect(row.textContent).toContain('尚未实际生成验证');
  });
  it('preserves same-name observations at different paths and distinct runtime bindings without content deduplication', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate(), candidate({id: 'candidate-b', runtime_id: 'runtime-b', runtime_type: 'OLLAMA'})], model_files: [file({candidate_ids: ['candidate-a']}), file({id: 'path-identity-b', path: '/private/other/same-model.safetensors', candidate_ids: ['candidate-b']})]}), [registration({enabled: false}), registration({id: 'registration-b', candidate_id: 'candidate-b', enabled: true})]);
    await mount(); const rows = within(observationView()).getAllByRole('article'); expect(rows).toHaveLength(2);
    expect(rows[0].textContent).toContain('/private/models/same-model.safetensors'); expect(rows[0].textContent).toContain('runtime-a'); expect(rows[0].textContent).not.toContain('runtime-b');
    expect(rows[1].textContent).toContain('/private/other/same-model.safetensors'); expect(rows[1].textContent).toContain('runtime-b'); expect(rows[1].textContent).not.toContain('runtime-a');
    expect(rows[0].textContent).toContain('已注册 · 未启用'); expect(rows[1].textContent).toContain('已授权路由');
  });
  it('treats dangling candidate IDs as unknown even when a registration or matching model name exists', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate()], model_files: [file({candidate_ids: ['missing-candidate']})]}), [registration({candidate_id: 'missing-candidate'})]);
    await mount(); const row = observation(); expect(row.textContent).toContain('Runtime 绑定未知');
    expect(row.textContent).toContain('候选关联未在本次扫描中找到'); expect(row.textContent).not.toContain('已授权路由'); expect(row.textContent).not.toContain('runtime-a');
  });
  it('accepts exact registration.id linkage but never guesses a registration by name or family', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate(), candidate({id: 'candidate-b', runtime_id: 'runtime-b'})], model_files: [file({candidate_ids: ['candidate-a', 'candidate-b']})]}), [registration({id: 'candidate-a', candidate_id: undefined})]);
    await mount(); const row = observation(); expect(within(row).getAllByText('已授权路由')).toHaveLength(1);
    expect(within(row).getAllByText('候选 · 未注册')).toHaveLength(1);
  });
  it.each(['PARTIAL', 'CANCELLED'])('retains observations honestly for %s and reports finite directory outcomes', async status => {
    currentSnapshot = snapshot(scan({status, roots: [{path: '/private/models', source: 'CONFIGURED', status: 'BOUNDED'}, {path: '/private/common', source: 'COMMON', status: 'NOT_FOUND'}]}));
    await mount(); const view = observationView(); expect(observation()).toBeTruthy();
    expect(view.textContent).toContain(status === 'PARTIAL' ? '部分检测未完成' : '扫描已取消');
    expect(view.textContent).toContain('保留已观察结果'); expect(view.textContent).toContain('达到扫描上限');
    expect(view.textContent).toContain('本次未找到目录'); expect(view.textContent).toContain('不代表整盘模型清单');
  });
  it('distinguishes empty observations from a schema-2 scan that did not return observations or roots', async () => {
    currentSnapshot = snapshot(scan({model_files: [], roots: []})); let view = await mount();
    expect(observationView().textContent).toContain('本次有限范围内未观察到模型文件或索引');
    view.unmount(); currentSnapshot = snapshot(scan({model_files: undefined, roots: undefined, finished_at: null, started_at: null})); view = await mount();
    expect(observationView().textContent).toContain('本次扫描未提供文件观察数据');
    expect(observationView().textContent).toContain('未提供目录范围记录'); expect(observationView().textContent).toContain('未记录');
    expect(observationView().textContent).not.toContain('本次有限范围内未观察到');
  });
  it('leaves absent/old-schema scans and the default V1 path unchanged', async () => {
    for (const schema of [undefined, 1]) {
      currentSnapshot = snapshot(scan({environment_schema_version: schema})); const view = await mount();
      expect(screen.queryByRole('region', {name: '本次扫描的文件与索引观察'})).toBeNull(); expect(screen.getByText('尚未发现模型')).toBeTruthy(); view.unmount();
    }
    currentSnapshot = snapshot(scan()); await mount(context, true);
    expect(screen.queryByRole('region', {name: '本次扫描的文件与索引观察'})).toBeNull(); expect(screen.getByText('尚未发现模型')).toBeTruthy();
  });
  it('marks registration status pending after an uncertain write and replaces observations on explicit recovery', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate()], model_files: [file({candidate_ids: ['candidate-a']})]}), [registration()]);
    await mount(); fetchMock.mockImplementation(async () => response({detail: {code: 'MODEL_CHANGED'}}, 409));
    await act(async () => {fireEvent.click(screen.getByRole('button', {name: '验证'}));});
    expect(observation().textContent).toContain('注册状态待确认'); expect(observation().textContent).not.toContain('已授权路由');
    currentSnapshot = snapshot(scan({id: 'scan-new', model_files: [file({id: 'path-new', name: 'new.safetensors', path: '/new/models/new.safetensors'})]}));
    fetchMock.mockImplementation(async () => response(currentSnapshot));
    await act(async () => {fireEvent.click(screen.getByRole('button', {name: '重新读取状态'}));});
    expect(observation('new.safetensors')).toBeTruthy(); expect(document.body.textContent).not.toContain('/private/models/same-model.safetensors');
  });
  it('reopens from the latest snapshot without retaining observations from the previous mount', async () => {
    const view = await mount(); expect(observation()).toBeTruthy(); view.unmount(); currentSnapshot = snapshot(scan({id: 'scan-reloaded', model_files: []}));
    await mount(); expect(within(observationView()).queryAllByRole('article')).toHaveLength(0); expect(document.body.textContent).not.toContain('/private/models/same-model.safetensors');
  });
  it.each(['permission', 'project', 'session'] as const)('cannot restore private observations from a late poll after %s authority changes', async change => {
    vi.useFakeTimers(); currentSnapshot = snapshot(scan({status: 'RUNNING'})); const view = await mount(); expect(observation().textContent).toContain('/private/models'); const late = deferred<Response>();
    fetchMock.mockImplementation(() => late.promise); await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    const poll = fetchMock.mock.calls.find(([url]) => url.endsWith('/scan/scan-files-1'))!;
    if (change === 'permission') view.rerender(<LocalAiDiscovery canMutate={false} onboarding={{context, projectId: 'project-files'}}/>);
    else if (change === 'project') act(() => {useStudio.setState({novelId: 'another-project'}); useStudio.setState({novelId: 'project-files'});});
    else {
      const next = {sessionToken: 'new-host'}; currentSnapshot = snapshot(null); fetchMock.mockImplementation(async () => response(currentSnapshot)); setCollaborationContext(next);
      await act(async () => {view.rerender(<LocalAiDiscovery canMutate onboarding={{context: next, projectId: 'project-files'}}/>);});
    }
    expect(poll[1].signal.aborted).toBe(true);
    await act(async () => {late.resolve(response(scan()));});
    expect(document.body.textContent).not.toContain('/private/models'); expect(screen.queryByRole('region', {name: '本次扫描的文件与索引观察'})).toBeNull();
    expect(poll[1].headers['X-Session-Token']).toBe('model-file-host');
  });
  it('rejects a late snapshot after same-token LOCAL_HOST epoch replacement', async () => {
    setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: ''}); bindLocalHostSession('epoch-host', {session_mode: 'LOCAL_HOST', actor_id: 'host'});
    const late = deferred<Response>(); fetchMock.mockImplementationOnce(() => late.promise); await mount({sessionToken: ''});
    const initial = fetchMock.mock.calls[0]; currentSnapshot = snapshot(null);
    await act(async () => {clearLocalHostSession(); bindLocalHostSession('epoch-host', {session_mode: 'LOCAL_HOST', actor_id: 'host'});});
    await act(async () => {late.resolve(response(snapshot(scan())));});
    expect(initial[1].signal.aborted).toBe(true); expect(initial[1].headers['X-Session-Token']).toBe('epoch-host');
    expect(document.body.textContent).not.toContain('/private/models'); expect(screen.queryByRole('region', {name: '本次扫描的文件与索引观察'})).toBeNull();
  });
  it('uses current poll observations rather than an older terminal snapshot returned for hardware refresh', async () => {
    vi.useFakeTimers(); currentSnapshot = snapshot(scan({status: 'RUNNING', model_files: []})); await mount();
    fetchMock.mockImplementation(async (url: string) => url.endsWith('/scan/scan-files-1') ? response(scan({model_files: [file({name: 'current.safetensors', path: '/current/model.safetensors'})]})) : response(snapshot(scan())));
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    expect(observation('current.safetensors')).toBeTruthy(); expect(document.body.textContent).not.toContain('/private/models/same-model.safetensors');
  });
});

it('bounds 2000 observations to local pages without extra reads and resets the page on scan replacement', async () => {
  currentSnapshot = snapshot(scan({model_files: Array.from({length: 2000}, (_, index) => file({id: `path-${index}`, name: `model-${index}.safetensors`, path: `/private/models/model-${index}.safetensors`}))}));
  const view = await mount(); const readCount = fetchMock.mock.calls.length;
  expect(within(observationView()).getAllByRole('article')).toHaveLength(20);
  expect(observationView().textContent).toContain('1–20 / 2000');
  fireEvent.click(within(observationView()).getByRole('button', {name: '下一页文件观察'}));
  expect(observation('model-20.safetensors')).toBeTruthy(); expect(observationView().textContent).toContain('21–40 / 2000');
  expect(fetchMock.mock.calls).toHaveLength(readCount); view.unmount();
  currentSnapshot = snapshot(scan({id: 'scan-next-page-reset'})); await mount(); expect(observation()).toBeTruthy();
});


it('keeps metadata checks separate from runtime inference and does not read when advanced paths open', async () => {
  currentSnapshot = snapshot(scan({candidates: [candidate()], model_files: [file({header_valid: false, size_bytes: 0, candidate_ids: ['candidate-a']})]}), [registration({verified: true, evidence: {generation_verified: false}})]);
  await mount(); const row = observation(), readCount = fetchMock.mock.calls.length;
  expect(row.textContent).toContain('有界元数据结构未确认'); expect(row.textContent).toContain('0 bytes');
  expect(row.textContent).toContain('已授权路由'); expect(row.textContent).toContain('尚未实际生成验证');
  expect(within(row).queryAllByRole('button')).toHaveLength(0);
  fireEvent.click(within(row).getByText('高级：查看文件路径与身份'));
  expect(fetchMock.mock.calls).toHaveLength(readCount);
});

it('does not present stale verified registration evidence as current while state is uncertain', async () => {
  currentSnapshot = snapshot(scan({candidates: [candidate()], model_files: [file({candidate_ids: ['candidate-a']})]}), [registration({verified: true, evidence: {generation_verified: true}})]);
  await mount(); expect(observation().textContent).toContain('关联记录报告实际生成已验证');
  fetchMock.mockImplementation(async () => response({detail: {code: 'MODEL_CHANGED'}}, 409));
  await act(async () => {fireEvent.click(screen.getByRole('button', {name: '验证'}));});
  expect(observation().textContent).toContain('注册状态待确认');
  expect(observation().textContent).not.toContain('关联记录报告实际生成已验证');
});
