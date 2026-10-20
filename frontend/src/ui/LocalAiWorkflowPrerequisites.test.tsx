// @vitest-environment jsdom
import {act, cleanup, fireEvent, render, screen, within} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it, vi} from 'vitest';
import {setCollaborationContext, type CollaborationContext} from '../api';
import {bindLocalHostSession, clearLocalHostSession, useLocalHostSession} from '../localHostSession';
import {useStudio} from '../store';
import type {LocalDiscoveryScan, LocalDiscoverySnapshot, LocalModelCandidate, WorkflowComponentDeclaration, WorkflowPrerequisiteEvidence, WorkflowPrerequisiteReport} from '../localAiDiscoveryApi';
import {LocalAiDiscovery} from './LocalAiDiscovery';

const context: CollaborationContext = {sessionToken: 'workflow-evidence-host'};
const workflow = (extra: Partial<WorkflowPrerequisiteEvidence> = {}): WorkflowPrerequisiteEvidence => ({
  runtime_id: 'comfy-a', adapter_id: 'adapter-a', display_name: '图像工作流 A', evidence_status: 'COMPLETE',
  nodes: [{node_class: 'CheckpointLoaderSimple', observation: 'observed'}, {node_class: 'KSampler', observation: 'not_observed'}, {node_class: 'SaveImage', observation: 'unknown'}],
  loader: {node_class: 'CheckpointLoaderSimple', input_field: 'ckpt_name', observation: 'observed', advertised_count: 2, candidate_ids: ['candidate-a']},
  metadata_status: 'NOT_VERIFIED', inference_status: 'NOT_RUN', ...extra,
});
const component = (extra: Partial<WorkflowComponentDeclaration> = {}): WorkflowComponentDeclaration => ({
  model_id: 'catalog-image', model_display_name: '目录模型 A', component_id: 'catalog-vae', component_type: 'VAE', observation: 'unknown',
  reason: 'NO_COMPONENT_IDENTITY_EVIDENCE', metadata_status: 'NOT_VERIFIED', inference_status: 'NOT_RUN', ...extra,
});
const report = (extra: Partial<WorkflowPrerequisiteReport> = {}): WorkflowPrerequisiteReport => ({
  schema_version: 1, scan_id: 'scan-prerequisites', scan_status: 'COMPLETED', definition_status: 'COMPLETE', workflows: [workflow()], components: [component()], ...extra,
});
const candidate = (extra: Partial<LocalModelCandidate> = {}): LocalModelCandidate => ({
  id: 'candidate-a', display_name: 'service-advertised-model', model_id: 'catalog-image', family: 'IMAGE', modality: 'IMAGE',
  declared_capabilities: ['IMAGE'], verified_capabilities: [], runtime_id: 'comfy-a', runtime_type: 'COMFYUI', source: 'COMFYUI',
  model_name: 'model.safetensors', status: 'DISCOVERED', compatible: 'NOT_VERIFIED', verified: false, validation_notes: [], evidence: {}, ...extra,
});
const scan = (extra: Partial<LocalDiscoveryScan> = {}): LocalDiscoveryScan => ({
  id: 'scan-prerequisites', status: 'COMPLETED', runtimes: [{id: 'comfy-a', type: 'COMFYUI', status: 'RUNNING'}], candidates: [], errors: [], environment_schema_version: 2,
  model_files: [], roots: [], workflow_prerequisites: report(), ...extra,
});
const snapshot = (value: LocalDiscoveryScan | null = scan()): LocalDiscoverySnapshot => ({scan: value, registrations: [], settings: {scan_roots: [], runtimes: []}, hardware: {}});
const response = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status});
const deferred = <T,>() => {let resolve!: (value: T) => void; const promise = new Promise<T>(done => {resolve = done;}); return {promise, resolve};};
const evidenceView = () => screen.getByRole('region', {name: '本次扫描的工作流前置条件观察'});
const workflowRow = (name = '图像工作流 A') => within(evidenceView()).getByRole('article', {name: `${name} 工作流观察`});
let currentSnapshot: LocalDiscoverySnapshot;
const fetchMock = vi.fn();
async function mount(owner = context, legacy = false) {
  let view!: ReturnType<typeof render>;
  await act(async () => {view = render(<LocalAiDiscovery canMutate {...(legacy ? {} : {onboarding: {context: owner, projectId: 'project-prerequisites'}})}/>);});
  return view;
}
beforeEach(() => {
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0});
  useStudio.setState({novelId: 'project-prerequisites', sessionToken: context.sessionToken, scope: undefined, actor: undefined});
  setCollaborationContext(context); currentSnapshot = snapshot(); fetchMock.mockReset();
  fetchMock.mockImplementation(async () => response(currentSnapshot)); vi.stubGlobal('fetch', fetchMock);
});
afterEach(() => {
  cleanup(); vi.restoreAllMocks(); vi.unstubAllGlobals(); vi.useRealTimers(); setCollaborationContext({sessionToken: ''});
  useLocalHostSession.setState({token: '', actorId: '', epoch: 0}); useStudio.setState({novelId: '', sessionToken: '', scope: undefined, actor: undefined});
});

describe('read-only same-scan workflow prerequisite evidence', () => {
  it('distinguishes observed, not observed and unknown without installing or verifying a model', async () => {
    await mount(); const row = workflowRow();
    expect(row.textContent).toContain('CheckpointLoaderSimple · 已观察到（observed）');
    expect(row.textContent).toContain('KSampler · 本次未观察到（not_observed）');
    expect(row.textContent).toContain('SaveImage · 未知（unknown）');
    expect(row.textContent).toContain('服务广告条目：2');
    expect(row.textContent).toContain('元数据验证：NOT_VERIFIED'); expect(row.textContent).toContain('实际生成：NOT_RUN');
    expect(row.textContent).not.toMatch(/READY|已启用|兼容|PASS/);
    expect(within(evidenceView()).queryAllByRole('button')).toHaveLength(0);
    expect(screen.getAllByText('COMPLETED', {exact: true})).toHaveLength(1);
    expect(fetchMock.mock.calls.every(([url, init]) => url === '/api/model-center/local-ai' && init.method === 'GET')).toBe(true);
  });
  it('labels catalog component declarations as unbound unknowns independently of workflow observations', async () => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({components: [component(), component({component_id: 'catalog-text', component_type: null, reason: 'COMPONENT_DEFINITION_UNAVAILABLE'})]})}));
    await mount(); const view = evidenceView();
    expect(view.textContent).toContain('目录模型的组件需求声明'); expect(view.textContent).toContain('不表示这些组件已安装或属于上述工作流');
    const details = within(view).getByText('目录组件声明（2）').parentElement as HTMLDetailsElement;
    expect(details.open).toBe(false); fireEvent.click(within(view).getByText('目录组件声明（2）'));
    expect(view.textContent).toContain('catalog-vae'); expect(view.textContent).toContain('组件身份无对应证据');
    expect(view.textContent).toContain('组件定义不可用'); expect(view.textContent).toContain('组件类型未知');
  });
  it.each([undefined, null])('keeps historical missing evidence %s unknown rather than an empty complete result', async value => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: value})); await mount();
    expect(evidenceView().textContent).toContain('本次扫描未提供工作流前置条件观察');
    expect(evidenceView().textContent).toContain('未知'); expect(within(evidenceView()).queryAllByRole('article')).toHaveLength(0);
  });
  it.each([
    {schema_version: 2}, {scan_id: 'old-scan'}, {scan_status: 'PARTIAL'}, {definition_status: 'READY'},
    {workflows: null}, {components: null}, {workflows: [{...workflow(), nodes: [null]}]},
    {workflows: [{...workflow(), loader: {...workflow().loader, advertised_count: -1}}]},
    {workflows: [{...workflow(), metadata_status: 'VERIFIED'}]}, {workflows: [{...workflow(), inference_status: 'PASS'}]},
    {components: [{...component(), observation: 'observed'}]},
  ])('fails closed for unsupported, mismatched or malformed evidence %j', async invalid => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: {...report(), ...invalid} as unknown as WorkflowPrerequisiteReport})); await mount();
    expect(evidenceView().textContent).toContain('观察数据无法确认');
    expect(within(evidenceView()).queryAllByRole('article')).toHaveLength(0); expect(evidenceView().textContent).not.toContain('图像工作流 A');
  });
  it.each(['UNAVAILABLE', 'MALFORMED', 'BOUNDED', 'CANCELLED', 'NOT_SCANNED'] as const)('does not turn %s evidence into a negative or positive observation', async evidence_status => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({workflows: [workflow({evidence_status})]})})); await mount(); const row = workflowRow();
    expect(row.textContent).toContain(evidence_status); expect(row.textContent).toContain('KSampler · 未知（unknown）');
    expect(row.textContent).not.toContain('（observed）'); expect(row.textContent).not.toContain('（not_observed）');
    expect(row.textContent).toContain('服务广告条目：未知');
  });
  it('keeps a complete empty loader enumeration distinct from unavailable evidence', async () => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({workflows: [workflow({loader: {...workflow().loader, observation: 'not_observed', advertised_count: 0, candidate_ids: []}})]})})); await mount();
    expect(workflowRow().textContent).toContain('服务广告条目：0'); expect(workflowRow().textContent).toContain('本次未观察到（not_observed）');
    expect(evidenceView().textContent).toContain('本次未观察到不等于未安装');
  });
  it.each(['RUNNING', 'PARTIAL', 'CANCELLED'] as const)('labels the overall %s scan separately and suppresses cancelled claims', async status => {
    currentSnapshot = snapshot(scan({status, workflow_prerequisites: report({scan_status: status})})); await mount();
    expect(evidenceView().textContent).toContain(status === 'CANCELLED' ? '扫描已取消' : status === 'PARTIAL' ? '本次扫描部分未完成' : '扫描尚未结束');
    expect(workflowRow().textContent).toContain(status === 'CANCELLED' ? 'CheckpointLoaderSimple · 未知（unknown）' : 'CheckpointLoaderSimple · 已观察到（observed）');
  });
  it.each(['BOUNDED', 'MALFORMED'] as const)('keeps %s requirement definitions explicitly incomplete', async definition_status => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({definition_status})})); await mount();
    expect(evidenceView().textContent).toContain('需求定义范围未完整确认'); expect(evidenceView().textContent).toContain(definition_status);
  });
  it('does not mistake an empty list for no prerequisites or a complete installation', async () => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({workflows: [], components: []})})); await mount();
    expect(evidenceView().textContent).toContain('本次没有可显示的工作流观察'); expect(evidenceView().textContent).toContain('不能推断没有前置条件');
  });
  it('associates only exact same-scan ComfyUI runtime candidate IDs without promoting registration evidence', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate(), candidate({id: 'candidate-b', runtime_id: 'other-runtime'})], workflow_prerequisites: report({workflows: [workflow({loader: {...workflow().loader, candidate_ids: ['candidate-a', 'candidate-b', 'absent']}})]})}));
    currentSnapshot.registrations = [{...candidate(), enabled: true, verified: true, evidence: {generation_verified: true}}];
    await mount(); const row = workflowRow(); expect(row.textContent).toContain('可对应同次 Runtime 候选：1');
    expect(row.textContent).toContain('部分候选引用无法对应本次 Runtime'); expect(row.textContent).not.toContain('已启用'); expect(row.textContent).toContain('实际生成：NOT_RUN');
  });
  it('does not show new evidence in default-off or unsupported environment schemas', async () => {
    for (const version of [undefined, 1, 3]) {
      currentSnapshot = snapshot(scan({environment_schema_version: version})); const view = await mount();
      expect(screen.queryByRole('region', {name: '本次扫描的工作流前置条件观察'})).toBeNull(); view.unmount();
    }
    currentSnapshot = snapshot(); await mount(context, true);
    expect(screen.queryByRole('region', {name: '本次扫描的工作流前置条件观察'})).toBeNull();
  });
  it('pages the bounded workflow and component declarations locally without probes', async () => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report({workflows: Array.from({length: 320}, (_, i) => workflow({adapter_id: `adapter-${i}`, display_name: `工作流 ${i}`})), components: Array.from({length: 512}, (_, i) => component({component_id: `part-${i}`}))})}));
    await mount(); const reads = fetchMock.mock.calls.length;
    expect(within(evidenceView()).getAllByRole('article')).toHaveLength(20);
    expect(evidenceView().textContent).toContain('1–20 / 320');
    fireEvent.click(within(evidenceView()).getByRole('button', {name: '下一页工作流观察'}));
    expect(workflowRow('工作流 20')).toBeTruthy();
    fireEvent.click(within(evidenceView()).getByText('目录组件声明（512）'));
    expect(within(evidenceView()).getAllByRole('listitem').filter(item => item.textContent?.includes('目录模型 A'))).toHaveLength(20);
    fireEvent.click(within(evidenceView()).getByRole('button', {name: '下一页组件声明'}));
    expect(evidenceView().textContent).toContain('part-20'); expect(evidenceView().textContent).not.toContain('part-0 ·');
    expect(fetchMock.mock.calls).toHaveLength(reads);
  });
  it.each(['workflows', 'components'] as const)('rejects a %s payload beyond the declared bounds', async key => {
    const invalid = report();
    if (key === 'workflows') invalid.workflows = Array.from({length: 321}, () => workflow());
    else invalid.components = Array.from({length: 513}, () => component());
    currentSnapshot = snapshot(scan({workflow_prerequisites: invalid})); await mount(); expect(evidenceView().textContent).toContain('观察数据无法确认');
  });
  it('masks observations after uncertain mutation and replaces evidence on explicit recovery', async () => {
    currentSnapshot = snapshot(scan({candidates: [candidate()]})); await mount();
    fetchMock.mockImplementation(async () => response({detail: {code: 'MODEL_CHANGED'}}, 409));
    await act(async () => {fireEvent.click(screen.getByRole('button', {name: '验证'}));});
    expect(evidenceView().textContent).toContain('状态待重新确认'); expect(workflowRow().textContent).not.toContain('（observed）');
    currentSnapshot = snapshot(scan({id: 'next-scan', workflow_prerequisites: report({scan_id: 'next-scan', workflows: [workflow({display_name: '新工作流'})]})}));
    fetchMock.mockImplementation(async () => response(currentSnapshot)); await act(async () => {fireEvent.click(screen.getByRole('button', {name: '重新读取状态'}));});
    expect(workflowRow('新工作流')).toBeTruthy(); expect(evidenceView().textContent).not.toContain('图像工作流 A');
  });
  it.each([401, 403])('clears all prerequisite data after an observed %s denial', async status => {
    vi.useFakeTimers(); currentSnapshot = snapshot(scan({status: 'RUNNING', workflow_prerequisites: report({scan_status: 'RUNNING'})})); await mount();
    fetchMock.mockImplementation(async () => response({detail: {code: 'FORBIDDEN'}}, status));
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);});
    expect(screen.queryByRole('region', {name: '本次扫描的工作流前置条件观察'})).toBeNull(); expect(document.body.textContent).not.toContain('catalog-vae');
  });
  it.each(['permission', 'project', 'session'] as const)('rejects late observations after %s owner changes', async change => {
    vi.useFakeTimers(); currentSnapshot = snapshot(scan({status: 'RUNNING', workflow_prerequisites: report({scan_status: 'RUNNING'})})); const view = await mount(); workflowRow();
    const late = deferred<Response>(); fetchMock.mockImplementation(() => late.promise);
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); const poll = fetchMock.mock.calls.find(([url]) => url.endsWith('/scan/scan-prerequisites'))!;
    if (change === 'permission') view.rerender(<LocalAiDiscovery canMutate={false} onboarding={{context, projectId: 'project-prerequisites'}}/>);
    else if (change === 'project') act(() => {useStudio.setState({novelId: 'new-project'}); useStudio.setState({novelId: 'project-prerequisites'});});
    else {
      const next = {sessionToken: 'next-owner'}; setCollaborationContext(next); currentSnapshot = snapshot(null); fetchMock.mockImplementation(async () => response(currentSnapshot));
      await act(async () => {view.rerender(<LocalAiDiscovery canMutate onboarding={{context: next, projectId: 'project-prerequisites'}}/>);});
    }
    expect(poll[1].signal.aborted).toBe(true); await act(async () => {late.resolve(response(scan()));});
    expect(screen.queryByRole('region', {name: '本次扫描的工作流前置条件观察'})).toBeNull(); expect(document.body.textContent).not.toContain('catalog-vae');
  });
  it('rejects a delayed snapshot after same-token host epoch replacement', async () => {
    setCollaborationContext({sessionToken: ''}); useStudio.setState({sessionToken: ''}); bindLocalHostSession('same-host', {session_mode: 'LOCAL_HOST', actor_id: 'host'});
    const late = deferred<Response>(); fetchMock.mockImplementationOnce(() => late.promise); await mount({sessionToken: ''}); const initial = fetchMock.mock.calls[0]; currentSnapshot = snapshot(null);
    await act(async () => {clearLocalHostSession(); bindLocalHostSession('same-host', {session_mode: 'LOCAL_HOST', actor_id: 'host'});});
    await act(async () => {late.resolve(response(snapshot()));});
    expect(initial[1].signal.aborted).toBe(true); expect(document.body.textContent).not.toContain('catalog-vae');
  });
  it('uses current poll evidence rather than the older hardware-refresh snapshot and keeps collapse read-only', async () => {
    vi.useFakeTimers(); currentSnapshot = snapshot(scan({status: 'RUNNING', workflow_prerequisites: report({scan_status: 'RUNNING', workflows: []})})); await mount();
    fetchMock.mockImplementation(async (url: string) => url.endsWith('/scan/scan-prerequisites') ? response(scan({workflow_prerequisites: report({workflows: [workflow({display_name: '最新工作流'})]})})) : response(snapshot()));
    await act(async () => {await vi.advanceTimersByTimeAsync(1000);}); expect(workflowRow('最新工作流')).toBeTruthy(); expect(evidenceView().textContent).not.toContain('图像工作流 A');
    const reads = fetchMock.mock.calls.length; fireEvent.click(screen.getByRole('button', {name: '收起'})); fireEvent.click(screen.getByRole('button', {name: '展开本地 AI'}));
    expect(workflowRow('最新工作流')).toBeTruthy(); expect(fetchMock.mock.calls).toHaveLength(reads);
  });
});


describe('workflow prerequisite semantic evidence validation', () => {
  it.each([
    {workflows: [workflow({loader: {...workflow().loader, advertised_count: null}})]},
    {workflows: [workflow({loader: {...workflow().loader, advertised_count: 0}})]},
    {workflows: [workflow({loader: {...workflow().loader, observation: 'not_observed', advertised_count: 1}})]},
    {workflows: [workflow({loader: {...workflow().loader, observation: 'not_observed', advertised_count: 0}})]},
    {workflows: [workflow({loader: {...workflow().loader, observation: 'unknown', advertised_count: 2}})]},
    {workflows: [workflow({loader: {...workflow().loader, observation: 'unknown', advertised_count: null}})]},
    {workflows: [workflow(), workflow()]},
    {components: [component(), component()]},
    {workflows: [workflow({nodes: [workflow().nodes[0], workflow().nodes[0]]})]},
    {workflows: [workflow({nodes: [workflow().nodes[1]]})]},
    {workflows: [workflow({nodes: [{...workflow().nodes[0], observation: 'not_observed'}]})]},
    {workflows: [workflow({loader: {...workflow().loader, candidate_ids: ['candidate-a', 'candidate-a']}})]},
    {workflows: [workflow({nodes: []})]},
    {workflows: [workflow({adapter_id: 'a'.repeat(101)})]},
    {workflows: [workflow({display_name: 'a'.repeat(257)})]},
    {workflows: [workflow({display_name: 'hidden\ncontrol'})]},
    {workflows: [workflow({nodes: Array.from({length: 65}, () => workflow().nodes[0])})]},
    {workflows: [workflow({loader: {...workflow().loader, candidate_ids: Array.from({length: 513}, () => 'candidate')}})]},
    {workflows: [workflow({loader: {...workflow().loader, advertised_count: 1.5}})]},
    {workflows: [workflow({loader: {...workflow().loader, advertised_count: 513}})]},
  ])('rejects contradictory or duplicate prerequisite evidence %j', async invalid => {
    currentSnapshot = snapshot(scan({workflow_prerequisites: report(invalid)})); await mount();
    expect(evidenceView().textContent).toContain('观察数据无法确认'); expect(within(evidenceView()).queryAllByRole('article')).toHaveLength(0);
  });
  it.each(([
    [], [{id: 'other', type: 'COMFYUI', status: 'RUNNING'}], [{id: 'comfy-a', type: 'OLLAMA', status: 'RUNNING'}],
    [{id: 'comfy-a', type: 'COMFYUI', status: 'NOT_FOUND'}],
    [{id: 'comfy-a', type: 'COMFYUI', status: 'RUNNING'}, {id: 'comfy-a', type: 'COMFYUI', status: 'RUNNING'}],
  ] as LocalDiscoveryScan['runtimes'][]).map(runtimes => ({runtimes})))('masks evidence without an unambiguous same-scan running ComfyUI runtime %j', async ({runtimes}) => {
    currentSnapshot = snapshot(scan({runtimes})); await mount();
    expect(workflowRow().textContent).toContain('Runtime 身份或运行状态未在本次扫描中确认');
    expect(workflowRow().textContent).toContain('CheckpointLoaderSimple · 未知（unknown）');
    expect(workflowRow().textContent).not.toContain('（not_observed）'); expect(workflowRow().textContent).toContain('服务广告条目：未知');
  });
});


it('resets local prerequisite pagination when explicit recovery replaces the scan', async () => {
  const many = report({workflows: Array.from({length: 21}, (_, index) => workflow({adapter_id: `page-adapter-${index}`, display_name: `分页工作流 ${index}`}))});
  currentSnapshot = snapshot(scan({workflow_prerequisites: many, candidates: [candidate()]})); await mount();
  fireEvent.click(within(evidenceView()).getByRole('button', {name: '下一页工作流观察'})); workflowRow('分页工作流 20');
  fetchMock.mockImplementation(async () => response({detail: {code: 'MODEL_CHANGED'}}, 409));
  await act(async () => {fireEvent.click(screen.getByRole('button', {name: '验证'}));});
  currentSnapshot = snapshot(scan({id: 'replacement-scan', workflow_prerequisites: {...many, scan_id: 'replacement-scan'}}));
  fetchMock.mockImplementation(async () => response(currentSnapshot));
  await act(async () => {fireEvent.click(screen.getByRole('button', {name: '重新读取状态'}));});
  workflowRow('分页工作流 0'); expect(evidenceView().textContent).toContain('1–20 / 21');
  expect(evidenceView().textContent).not.toContain('分页工作流 20');
});
