// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasAudioWorkflowTemplatePanel, type CanvasAudioWorkflowTemplatePanelProps } from './CanvasAudioWorkflowTemplatePanel';
import { templateGraph, templateOwner } from './canvasAudioWorkflowTemplate.testFixtures';
import type { StudioGraphRecord } from '../studioGraphTypes';
import type { CanvasAudioWorkflowTemplateRef } from './canvasAudioWorkflowTemplate';
afterEach(cleanup);
function props() {
  return { owner: templateOwner, ownerToken: {}, current: true, busy: false, canApply: true,
    isCurrent: vi.fn(() => true), list: vi.fn(async () => [templateGraph()]),
    read: vi.fn(async (_id: string) => templateGraph()), onApply: vi.fn<(reference: CanvasAudioWorkflowTemplateRef) => void | Promise<void>>() } satisfies CanvasAudioWorkflowTemplatePanelProps;
}
function deferred<T>() { let resolve!: (value: T) => void; const promise = new Promise<T>(done => { resolve = done; }); return { promise, resolve }; }
function handler(element: HTMLElement, event = 'onClick') {
  const key = Object.keys(element).find(value => value.startsWith('__reactProps$'))!;
  return (element as any)[key][event] as (...args: any[]) => any;
}
async function list() { fireEvent.click(screen.getByText('读取已保存工作流')); await screen.findByLabelText('已保存工作流'); }
async function choose() {
  await list(); fireEvent.change(screen.getByLabelText('已保存工作流'), { target: { value: templateGraph().id } });
  await screen.findByLabelText('已核对的音频截取节点');
  fireEvent.change(screen.getByLabelText('已核对的音频截取节点'), { target: { value: 'trim' } });
}
function approve() { fireEvent.click(screen.getByLabelText('确认把此版本截取区间复制到本次音频卡片任务')); }
const applyButton = () => screen.getByText('核对原图并应用到本次任务');

it('does not select, fetch or apply automatically; rereads the exact source after explicit consent', async () => {
  const p = props(); render(<CanvasAudioWorkflowTemplatePanel {...p} />);
  expect(p.list).not.toHaveBeenCalled(); expect(p.read).not.toHaveBeenCalled();
  await choose(); expect(p.read).toHaveBeenCalledTimes(1); expect(p.onApply).not.toHaveBeenCalled();
  expect(screen.getByText(/影响范围：只覆盖本次任务/)).toBeTruthy();
  expect(screen.getByText('a'.repeat(64))).toBeTruthy(); expect(screen.getByText('b'.repeat(64))).toBeTruthy();
  fireEvent.click(applyButton()); expect(p.read).toHaveBeenCalledTimes(1);
  approve(); fireEvent.click(applyButton()); await waitFor(() => expect(p.onApply).toHaveBeenCalledTimes(1));
  expect(p.read).toHaveBeenCalledTimes(2); expect(p.onApply.mock.calls[0][0]).toMatchObject({ graph_id: templateGraph().id, graph_version: 3, node_id: 'trim', parameters: { in_ms: 100, out_ms: 900 } });
  expect(Object.isFrozen(p.onApply.mock.calls[0][0].parameters)).toBe(true);
  await screen.findByText(/已准备本次任务参数副本/);
});
it.each(['version', 'definition', 'execution', 'parameters', 'source', 'readonly'])('retires confirmation if rereading changes %s', async change => {
  const p = props(); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve();
  const changed = templateGraph();
  if (change === 'version') changed.version++;
  if (change === 'definition') changed.definition_digest = 'd'.repeat(64);
  if (change === 'execution') changed.execution_digest = 'e'.repeat(64);
  if (change === 'parameters') changed.definition.nodes[1].parameters.parameters!.in_ms = 101;
  if (change === 'source') changed.reference_states[0].state = 'STALE';
  if (change === 'readonly') changed.can_edit = false;
  p.read.mockResolvedValue(changed); const retained = handler(applyButton());
  await act(async () => { await retained(); }); await screen.findByText(/未应用模板/);
  p.read.mockResolvedValue(templateGraph()); await act(async () => { await retained(); });
  expect(p.onApply).not.toHaveBeenCalled(); expect(screen.queryByLabelText(/确认把此版本/)).toBeNull();
});
it('requires list refresh when the selected saved version has changed before the first read', async () => {
  const p = props(); p.read.mockResolvedValue({ ...templateGraph(), version: 4 }); render(<CanvasAudioWorkflowTemplatePanel {...p} />);
  await list(); fireEvent.change(screen.getByLabelText('已保存工作流'), { target: { value: templateGraph().id } });
  await screen.findByText(/请刷新列表后重新读取/); expect(screen.queryByLabelText('已核对的音频截取节点')).toBeNull();
});
it.each(['owner', 'ownerToken ABA', 'current ABA', 'busy ABA', 'canApply ABA', 'client', 'unmount'])('retained confirmation cannot revive after %s', async mode => {
  const p = props(), view = render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve(); const retained = handler(applyButton());
  if (mode === 'owner') view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} owner={{ ...templateOwner, incarnation: 'file:replacement' }} />);
  if (mode === 'ownerToken ABA') { view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} ownerToken={{}} />); view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} />); }
  if (mode === 'current ABA') { view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} current={false} />); view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} />); }
  if (mode === 'busy ABA') { view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} busy />); view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} />); }
  if (mode === 'canApply ABA') { view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} canApply={false} />); view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} />); }
  if (mode === 'client') view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} read={async () => templateGraph()} />);
  if (mode === 'unmount') view.unmount();
  await act(async () => { await retained(); }); expect(p.onApply).not.toHaveBeenCalled(); expect(p.read).toHaveBeenCalledTimes(1);
});
it('a false current getter latches retirement even when the getter later returns true', async () => {
  const p = props(); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve(); const retained = handler(applyButton());
  p.isCurrent.mockReturnValue(false); await act(async () => { await retained(); });
  p.isCurrent.mockReturnValue(true); await act(async () => { await retained(); }); expect(p.onApply).not.toHaveBeenCalled(); expect(p.read).toHaveBeenCalledTimes(1);
});
it('retires an owner mutated in place before a retained apply without requiring a rerender', async () => {
  const p = props(); p.owner = { ...templateOwner }; render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve();
  const retained = handler(applyButton()); p.owner.incarnation = 'file:replacement';
  await act(async () => { await retained(); }); p.owner.incarnation = templateOwner.incarnation;
  await act(async () => { await retained(); }); expect(p.onApply).not.toHaveBeenCalled(); expect(p.read).toHaveBeenCalledTimes(1);
});
it('does not let a retained previous node checkbox restore its retired selection', async () => {
  const p = props(); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve();
  const retained = handler(applyButton()), confirm = handler(screen.getByLabelText('确认把此版本截取区间复制到本次音频卡片任务'), 'onChange');
  fireEvent.change(screen.getByLabelText('已核对的音频截取节点'), { target: { value: 'trim_other' } });
  act(() => { confirm({ target: { checked: true } }); }); await act(async () => { await retained(); }); expect(p.onApply).not.toHaveBeenCalled();
  expect((screen.getByLabelText('确认把此版本截取区间复制到本次音频卡片任务') as HTMLInputElement).checked).toBe(false);
  approve(); fireEvent.click(applyButton()); await waitFor(() => expect(p.onApply).toHaveBeenCalledTimes(1)); expect(p.onApply.mock.calls[0][0].node_id).toBe('trim_other');
});
it('captures immutable source snapshots and rejects an in-place source parameter change before consent', async () => {
  const p = props(), raw = templateGraph(); p.read.mockResolvedValue(raw); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose();
  raw.definition.nodes[1].parameters.parameters!.out_ms = 950; approve();
  expect(screen.queryByLabelText(/确认把此版本/)).toBeNull(); expect(p.onApply).not.toHaveBeenCalled();
});
it('rejects a changed list object before reading and keeps empty/no-trim/error states honest', async () => {
  const p = props(), raw = templateGraph(); p.list.mockResolvedValue([raw]); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await list();
  raw.version++; fireEvent.change(screen.getByLabelText('已保存工作流'), { target: { value: raw.id } });
  await screen.findByText(/请刷新列表后重新读取/); expect(p.read).not.toHaveBeenCalled();
});
it('requires a new confirmation after refresh and rejects retained previous graph callbacks', async () => {
  const p = props(); render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve();
  const retained = handler(applyButton()), select = handler(screen.getByLabelText('已核对的音频截取节点'), 'onChange');
  await list(); act(() => { select({ target: { value: 'trim' } }); }); await act(async () => { await retained(); });
  expect(p.onApply).not.toHaveBeenCalled(); expect(screen.queryByLabelText(/确认把此版本/)).toBeNull();
});
it.each(['list', 'read', 'apply-read'])('ignores a late %s response after an owner A/B/A change', async phase => {
  const p = props(), wait = deferred<StudioGraphRecord>(), listWait = deferred<StudioGraphRecord[]>();
  if (phase === 'list') p.list.mockReturnValue(listWait.promise);
  const view = render(<CanvasAudioWorkflowTemplatePanel {...p} />);
  if (phase === 'list') fireEvent.click(screen.getByText('读取已保存工作流'));
  if (phase === 'read') { await list(); p.read.mockReturnValue(wait.promise); fireEvent.change(screen.getByLabelText('已保存工作流'), { target: { value: templateGraph().id } }); }
  if (phase === 'apply-read') { await choose(); approve(); p.read.mockReturnValue(wait.promise); fireEvent.click(applyButton()); }
  view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} owner={{ ...templateOwner, actorId: 'other' }} />); view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} />);
  await act(async () => { wait.resolve(templateGraph()); listWait.resolve([templateGraph()]); });
  expect(screen.queryByLabelText(/确认把此版本/)).toBeNull(); expect(p.onApply).not.toHaveBeenCalled();
});
it('consumes consent synchronously for duplicate and reentrant apply clicks', async () => {
  const p = props(), wait = deferred<void>(); let retained: () => Promise<void>;
  p.onApply = vi.fn(() => { void retained(); return wait.promise; });
  render(<CanvasAudioWorkflowTemplatePanel {...p} />); await choose(); approve(); retained = handler(applyButton());
  await act(async () => { void retained(); void retained(); }); await waitFor(() => expect(p.onApply).toHaveBeenCalledTimes(1));
  await act(async () => { wait.resolve(); }); expect(p.read).toHaveBeenCalledTimes(2);
});
it('shows list and read failures without inventing a latest snapshot or automatic selection', async () => {
  const p = props(); p.list.mockRejectedValueOnce(new Error('unavailable')); render(<CanvasAudioWorkflowTemplatePanel {...p} />);
  fireEvent.click(screen.getByText('读取已保存工作流')); await screen.findByText(/已保存图读取失败/);
  p.list.mockResolvedValueOnce([]); await list(); await screen.findByText(/没有已保存工作流/);
  p.list.mockResolvedValueOnce([templateGraph()]); await list(); const invalid = templateGraph(); invalid.definition.nodes[1].enabled = false; invalid.definition.nodes[2].enabled = false;
  p.read.mockResolvedValue(invalid); fireEvent.change(screen.getByLabelText('已保存工作流'), { target: { value: templateGraph().id } }); await screen.findByText(/没有可用的音频截取节点/);
  expect(p.onApply).not.toHaveBeenCalled();
});

it('shows supported source effects and only forwards an immutable input copy after its explicit confirmation',async()=>{
 const p=props(),graph=templateGraph();Object.assign(graph.definition.nodes[1].parameters.parameters!,{gain_db:-6,fade_in_ms:100,fade_out_ms:200});p.list.mockResolvedValue([graph]);p.read.mockResolvedValue(graph);
 render(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={{in_ms:0,out_ms:1000,gain_db:-3,fade_in_ms:50,fade_out_ms:50}}/>);await choose();
 expect(screen.getByRole('table',{name:'模板参数与本次任务对照'})).toBeTruthy();expect(screen.getByText('-6 dB（本次覆盖）')).toBeTruthy();
 fireEvent.click(applyButton());expect(p.onApply).not.toHaveBeenCalled();fireEvent.click(screen.getByLabelText('确认把此版本截取与效果参数复制到本次音频卡片任务'));fireEvent.click(applyButton());
 await waitFor(()=>expect(p.onApply).toHaveBeenCalledTimes(1));expect(p.onApply.mock.calls[0][0].parameters).toEqual({in_ms:100,out_ms:900,gain_db:-6,fade_in_ms:100,fade_out_ms:200});expect(Object.isFrozen(p.onApply.mock.calls[0][0].parameters)).toBe(true);
});
it('keeps legacy interval confirmation and declares absent effect values preserved',async()=>{
 const p=props();render(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={{in_ms:0,out_ms:1000,gain_db:-3,fade_in_ms:50}}/>);await choose();
 expect(screen.getAllByText('保留本次设置')).toHaveLength(3);expect(screen.getByLabelText('确认把此版本截取区间复制到本次音频卡片任务')).toBeTruthy();approve();fireEvent.click(applyButton());
 await waitFor(()=>expect(p.onApply).toHaveBeenCalledTimes(1));expect(p.onApply.mock.calls[0][0].parameters).toEqual({in_ms:100,out_ms:900});
});
it('retires a copied-source consent when task parameter values change then return through rerenders',async()=>{
 const p=props(),current={in_ms:0,out_ms:1000,gain_db:-3},view=render(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={current}/>);await choose();approve();const retained=handler(applyButton());
 view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={{...current,gain_db:-6}}/>);view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={{...current}}/>);
 await act(async()=>retained());expect(p.onApply).not.toHaveBeenCalled();
});
it('latches an in-place task parameter ABA observed by a captured apply without rerender',async()=>{
 const p=props(),current={in_ms:0,out_ms:1000,gain_db:-3};render(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={current}/>);await choose();approve();const retained=handler(applyButton());
 current.gain_db=-6;await act(async()=>retained());current.gain_db=-3;await act(async()=>retained());expect(p.onApply).not.toHaveBeenCalled();expect(p.read).toHaveBeenCalledTimes(1);
});
it('does not retire consent for a detached equal-valued current parameter object',async()=>{
 const p=props(),current={in_ms:0,out_ms:1000,gain_db:-3},view=render(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={current}/>);await choose();approve();view.rerender(<CanvasAudioWorkflowTemplatePanel {...p} currentParameters={{...current}}/>);
 fireEvent.click(applyButton());await waitFor(()=>expect(p.onApply).toHaveBeenCalledTimes(1));
});
