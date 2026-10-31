// @vitest-environment jsdom
/** File-derived QUEUED metadata, replayed through original HTTP clients. No
 * provider execution, media inspection, review, approval or ingestion occurs. */
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { webcrypto } from 'node:crypto';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import native from '../../../tests/fixtures/cloud_canvas_node_resume.json';
import { prepareCanvasImageNodeResume, type CanvasImageNodeResumeInput } from './canvasImageNodeResume';
import { studioClient } from './studioClient';
import { studioProductionClient, type ProductionJob } from './studioProductionClient';
import { canvasImageNodeInCommand } from './canvasImageNode';
import type { StudioProductionTask } from '../taskcenter/studioProductionTask';
import { useStudioMediaExecution, type StudioMediaExecutionController, type StudioMediaExecutionProps } from './useStudioMediaExecution';
import { ExecutionImpactPanel } from '../experimental/executionImpact/ExecutionImpactPanel';

const base = `/api/projects/${native.project}/studio`;
const json = (value: unknown, status = 200) => new Response(JSON.stringify(value), {status, headers:{'Content-Type':'application/json'}});
const original = () => structuredClone(native.job) as unknown as StudioProductionTask;
let fetcher: ReturnType<typeof vi.fn>;
type Override = (url: string, init: RequestInit) => Response | Promise<Response> | undefined;
function server(override?: Override) {
  fetcher = vi.fn(async (url: string, init: RequestInit = {}) => {
    const value = override?.(url, init); if (value !== undefined) return await value;
    if (url === base) return json(native.overview);
    if (url.endsWith('/jobs/image/resolve-create')) return json(native.resolved_job);
    if (url.endsWith(`/canvas-views/${native.canvas.id}/history`)) return json(native.history);
    if (url.endsWith(`/canvas-views/${native.canvas.id}`)) return json(native.canvas);
    if (url.endsWith(`/jobs/image/${native.job.id}`)) return json(native.job);
    if (url.endsWith('/providers')) return json({items:[], health_probed:false, credentials_read:false});
    if (url.endsWith('/preview')) return json(native.preview);
    throw new Error(`Unexpected request in metadata-only fixture: ${init.method} ${url}`);
  });
  vi.stubGlobal('fetch', fetcher);
}
const input = (patch: Partial<CanvasImageNodeResumeInput> = {}): CanvasImageNodeResumeInput => ({
  selected: original(), projectId:native.project, branchId:null,
  client:studioClient(native.project, {sessionToken:''}),
  production:studioProductionClient(native.project, {sessionToken:''}),
  isCurrent:()=>true, read:work=>work(), ...patch,
});
const count = (suffix: string) => fetcher.mock.calls.filter(([url, init]) => url.endsWith(suffix) && init.method === 'POST').length;
function noDispatch() { expect(count('/jobs')).toBe(0); expect(count('/execute')).toBe(0); expect(count('/review')).toBe(0); }
beforeEach(() => { vi.stubGlobal('crypto', webcrypto); localStorage.clear(); server(); });
afterEach(() => { cleanup(); vi.useRealTimers(); vi.restoreAllMocks(); vi.unstubAllGlobals(); });

it('prepares the exact hintless File-derived original node, Canvas and Job through real clients without creating authority', async () => {
  const writes = vi.spyOn(Storage.prototype, 'setItem');
  const result = await prepareCanvasImageNodeResume(input());
  expect(native.evidence_type).toBe('REAL_ORIGINAL_FILE_API_QUEUED_METADATA_ONLY');
  expect(result.job).toMatchObject({id:native.job.id, status:'QUEUED', version:1, attempt:0, output_candidate:null});
  expect(result.binding).toEqual(native.command.canvas_image_node);
  expect(result.initialPrompt).toBe(native.node.prompt);
  expect(result.canvas).toEqual(native.canvas); expect(result.canReview).toBe(true);
  expect(fetcher.mock.calls.map(([url]) => url)).toEqual([base, `${base}/production/jobs/image/resolve-create`,
    `${base}/canvas-views/${native.canvas.id}`, `${base}/canvas-views/${native.canvas.id}/history`, `${base}/production/jobs/image/${native.job.id}`]);
  expect(writes).not.toHaveBeenCalled(); noDispatch();
});

it.each(['status', 'project', 'branch', 'capsule', 'prompt'] as const)('rejects changed selected %s before any HTTP dispatch', async kind => {
  const selected = original();
  if (kind === 'status') selected.status = 'RUNNING';
  if (kind === 'project') selected.novel_id = 'other-project';
  if (kind === 'branch') selected.branch_id = 'other-branch';
  if (kind === 'capsule') delete selected.command!.canvas_image_node;
  if (kind === 'prompt') selected.command!.prompt = 'different prompt';
  await expect(prepareCanvasImageNodeResume(input({selected}))).rejects.toThrow();
  expect(fetcher).not.toHaveBeenCalled(); noDispatch();
});

it.each(['resolved-version', 'resolved-request', 'resolved-capsule', 'latest-version', 'canvas-version', 'history-incarnation', 'project-incarnation', 'permission'] as const)(
  'does not choose a newer or other source after fresh %s changes', async kind => {
    server((url) => {
      if (url.endsWith('/resolve-create') && kind.startsWith('resolved-')) {
        const row = structuredClone(native.resolved_job);
        if (kind === 'resolved-version') row.version++;
        if (kind === 'resolved-request') row.request_id = 'another-request';
        if (kind === 'resolved-capsule') row.command.canvas_image_node.node_id = 'other-node';
        return json(row);
      }
      if (url.endsWith(`/jobs/image/${native.job.id}`) && kind === 'latest-version') return json({...native.job, version:2});
      if (url.endsWith(`/canvas-views/${native.canvas.id}`) && kind === 'canvas-version') return json({...native.canvas, version:2});
      if (url.endsWith('/history') && kind === 'history-incarnation') return json({...native.history, incarnation:'file:00000000-0000-0000-0000-000000000001'});
      if (url === base && kind === 'project-incarnation') return json({...native.overview, project:{...native.overview.project, incarnation:'file:00000000-0000-0000-0000-000000000001'}});
      if (url === base && kind === 'permission') return json({...native.overview, capabilities:{...native.overview.capabilities, can_mutate:false}});
    });
    await expect(prepareCanvasImageNodeResume(input())).rejects.toThrow();
    expect(fetcher.mock.calls.some(([url]) => url.endsWith('/production/jobs'))).toBe(false); noDispatch();
  });

it.each([401, 403, 404])('preserves original owner HTTP %s as a failure with no latest/list fallback', async status => {
  server(url => url.endsWith('/resolve-create') ? json({code:'ORIGINAL_OWNER_UNAVAILABLE', message:'unavailable'}, status) : undefined);
  await expect(prepareCanvasImageNodeResume(input())).rejects.toMatchObject({status});
  expect(fetcher.mock.calls).toHaveLength(2); noDispatch();
});

it('rechecks a deferred read lease at actual dispatch rather than trusting a previously selected row', async () => {
  let current = true, release!: () => void;
  const read: CanvasImageNodeResumeInput['read'] = async work => { await new Promise<void>(resolve => {release = resolve;}); return work(); };
  const result = prepareCanvasImageNodeResume(input({read, isCurrent:()=>current}));
  const rejected = expect(result).rejects.toThrow();
  await waitFor(() => expect(release).toBeTypeOf('function'));
  current = false; release(); await rejected;
  expect(fetcher).not.toHaveBeenCalled(); noDispatch();
});

it('rejects a late original response after cancellation, without doing the next read', async () => {
  let release!: (value: Response) => void;
  server(url => url === base ? new Promise<Response>(resolve => {release = resolve;}) : undefined);
  const signal = new AbortController();
  const result = prepareCanvasImageNodeResume(input({signal:signal.signal}));
  const rejected = expect(result).rejects.toThrow();
  await waitFor(() => expect(release).toBeTypeOf('function'));
  signal.abort(); release(json(native.overview)); await rejected;
  expect(fetcher.mock.calls).toHaveLength(1); noDispatch();
});

let state: StudioMediaExecutionController, props: StudioMediaExecutionProps;
function Hook() {
  state = useStudioMediaExecution(props);
  return state.impact?<ExecutionImpactPanel input={state.impact.input} owner={state.impact} current={state.impact.current()}
    canConfirm={props.canMutate} busy={state.locked} isCurrent={state.impact.current}
    onConfirm={proof=>void state.confirmImpact(state.impact!,proof)}/>:null;
}
function resumeProps(): StudioMediaExecutionProps {
  const job = original(), binding = canvasImageNodeInCommand(job.command)!;
  return {client:studioProductionClient(native.project,{sessionToken:''}), assets:[], externalJob:job as ProductionJob, resumeOnly:true,
    canvasNodeTask:{binding, initialPrompt:native.node.prompt, isCurrent:()=>true}, canMutate:true, canReview:true, busy:false,
    isCurrent:()=>true, read:work=>work(), mutate:work=>work(), onDirtyChange:vi.fn(), onUnavailable:vi.fn()};
}
async function hook() { props = resumeProps(); const view = render(<Hook/>); await waitFor(() => expect(state.selected?.id, state.error).toBe(native.job.id)); return view; }

it('blocks direct legacy edit/create/list/open-other callbacks in resume-only mode, including hidden actions', async () => {
  await hook(); const before = structuredClone(state.draft), reads = fetcher.mock.calls.length;
  act(() => { state.changeField('prompt','not the original'); state.changeField('allowCloud',true); state.changeField('providerKey','other');
    state.changeRoute('cloud'); state.changeParameter('steps','99'); state.clearInputs(); state.clearSources(); state.confirmPreview(true); });
  await act(async () => { await state.inspect(); await state.create(); await state.listJobs(); await state.openJob({...original(),id:'other-job'} as ProductionJob); });
  expect(state.resumeOnly).toBe(true); expect(state.canEdit).toBe(false); expect(state.canInspect).toBe(false); expect(state.canCreate).toBe(false);
  expect(state.draft).toEqual(before); expect(fetcher.mock.calls).toHaveLength(reads); expect(state.selected?.id).toBe(native.job.id); noDispatch();
});

it.each(['mode', 'client', 'capsule', 'job'] as const)('permanently retires old resume callbacks after observed %s A/B/A', async kind => {
  const view = await hook(), originalProps = props, inspect = state.inspectExecution, read = state.openJob;
  if (kind === 'mode') props = {...props, resumeOnly:false};
  if (kind === 'client') props = {...props, client:studioProductionClient(native.project,{sessionToken:''})};
  if (kind === 'capsule') props = {...props, canvasNodeTask:{...props.canvasNodeTask!,binding:{...props.canvasNodeTask!.binding,node_id:'other-node'}}};
  if (kind === 'job') props = {...props, externalJob:{...props.externalJob!,id:'other-job'}};
  view.rerender(<Hook/>); props = originalProps; view.rerender(<Hook/>);
  const reads = fetcher.mock.calls.length;
  await act(async () => { await inspect(); await read(original() as ProductionJob); await state.action('execute'); });
  expect(state.canAction('execute')).toBe(false); expect(fetcher.mock.calls).toHaveLength(reads); noDispatch();
});

it.each(['missing-binding', 'ordinary-global'] as const)('keeps a node Job execution closed for %s', async kind => {
  props = {...resumeProps(), canvasNodeTask:undefined, resumeOnly:kind === 'missing-binding'}; render(<Hook/>);
  await act(async () => { await state.openJob(original() as ProductionJob); await state.inspectExecution(); await state.action('execute'); });
  expect(state.canAction('execute')).toBe(false); noDispatch();
});

it('discards a same-job late GET after controller unmount without executing or reviewing', async () => {
  const view = await hook(); let release!: (value: Response) => void;
  server(url => url.endsWith(`/jobs/image/${native.job.id}`) ? new Promise<Response>(resolve => {release = resolve;}) : undefined);
  let pending!: Promise<void>; act(() => {pending = state.openJob(original() as ProductionJob);});
  await waitFor(() => expect(release).toBeTypeOf('function')); view.unmount();
  await act(async () => {release(json(native.job)); await pending;}); noDispatch();
});

it('blocks a deferred provider read at actual send after resume mode A/B/A', async () => {
  const view = await hook(); const source = props; let release!: () => void;
  props = {...props,read:async work=>{await new Promise<void>(resolve=>{release=resolve;});return work();}};
  view.rerender(<Hook/>); const before=fetcher.mock.calls.length;
  let pending!:Promise<void>; act(()=>{pending=state.loadProviders();});
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  props={...source,resumeOnly:false};view.rerender(<Hook/>);props=source;view.rerender(<Hook/>);
  await act(async()=>{release();await pending;});expect(fetcher.mock.calls).toHaveLength(before);noDispatch();
});

it.each(['mode','permission'] as const)('blocks a previously confirmed execute at deferred mutation dispatch after %s A/B/A',async kind=>{
  const view=await hook();await act(async()=>state.inspectExecution());
  const check=await screen.findByLabelText('已核对本次输入变化与影响范围');
  await waitFor(()=>expect((check as HTMLInputElement).disabled).toBe(false));
  fireEvent.click(check);fireEvent.click(screen.getByRole('button',{name:'确认本次输入核对'}));
  await waitFor(()=>expect(state.canAction('execute')).toBe(true));
  const source=props;let release!:()=>void;
  props={...props,mutate:async work=>{await new Promise<void>(resolve=>{release=resolve;});return work();}};view.rerender(<Hook/>);
  let pending!:Promise<void>;act(()=>{pending=state.action('execute');});
  await waitFor(()=>expect(release).toBeTypeOf('function'));
  props=kind==='mode'?{...source,resumeOnly:false}:{...source,canMutate:false};view.rerender(<Hook/>);
  props=source;view.rerender(<Hook/>);
  await act(async()=>{release();await pending;});noDispatch();expect(state.canAction('execute')).toBe(false);
});
