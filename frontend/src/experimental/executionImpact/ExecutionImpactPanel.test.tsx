// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { webcrypto } from 'node:crypto';
import { ExecutionImpactPanel, type ExecutionImpactPanelProps } from './ExecutionImpactPanel';
import type { ExecutionImpactConfirmation } from './executionImpact';
import { impactInput } from './executionImpact.testFixtures';

beforeEach(() => vi.stubGlobal('crypto', webcrypto));
afterEach(() => { cleanup();vi.unstubAllGlobals();vi.restoreAllMocks(); });
const checkbox = () => screen.getByLabelText('已核对本次输入变化与影响范围') as HTMLInputElement;
const button = () => screen.getByRole('button', {name:'确认本次输入核对'}) as HTMLButtonElement;
const retained = (node:HTMLElement) => (node as unknown as Record<string, {onClick:()=>void}>)[Object.keys(node).find(key=>key.startsWith('__reactProps$'))!].onClick;
function setup() {
  const onConfirm=vi.fn(), props:ExecutionImpactPanelProps={input:impactInput(),owner:{},current:true,canConfirm:true,isCurrent:vi.fn(()=>true),onConfirm};
  return {...render(<ExecutionImpactPanel {...props}/>),props,onConfirm};
}
async function acknowledge() { await waitFor(()=>expect(checkbox().disabled).toBe(false));fireEvent.click(checkbox()); }
async function confirm() { await acknowledge();fireEvent.click(button()); }
it('returns one explicitly checked local receipt and performs no transport or persistence', async () => {
  const fetch=vi.fn();vi.stubGlobal('fetch',fetch);const save=vi.spyOn(Storage.prototype,'setItem');const f=setup();
  expect(button().disabled).toBe(true);await confirm();expect(f.onConfirm).toHaveBeenCalledTimes(1);
  const proof=f.onConfirm.mock.calls[0][0] as ExecutionImpactConfirmation;
  expect(proof.contract).toBe('studio-execution-impact-confirmation/1');expect(proof.scope).toBe('TASK');expect(proof.inputFingerprint).toMatch(/^[a-f0-9]{64}$/);expect(proof.isCurrent()).toBe(true);
  expect(button().disabled).toBe(true);expect(fetch).not.toHaveBeenCalled();expect(save).not.toHaveBeenCalled();
  expect(screen.getByText(/费用、运行时长和资源用量.*均为未知/)).toBeTruthy();expect(screen.queryByText(/免费|￥0|0 元/)).toBeNull();
});
it.each(['prompt','provider','model','parameter','source pin','recipe','future binding'])('invalidates confirmation and a retained callback when %s changes, including A/B/A', async kind => {
  const f=setup();await acknowledge();const oldClick=retained(button());fireEvent.click(button());const oldProof=f.onConfirm.mock.calls[0][0] as ExecutionImpactConfirmation;
  const input=structuredClone(f.props.input);
  if(kind==='prompt')input.command.prompt+=' changed';if(kind==='provider')input.command.provider_id='next';if(kind==='model')input.command.model_id='next';
  if(kind==='parameter')input.command.parameters.seed=42;if(kind==='source pin')input.command.source_snapshots[0].version=2;if(kind==='recipe')input.recipe!.parameters={steps:37};
  if(kind==='future binding')Object.assign(input.command,{canvas_return:{card_id:'another-card'}});
  f.rerender(<ExecutionImpactPanel {...f.props} input={input}/>);expect(oldProof.isCurrent()).toBe(false);
  f.rerender(<ExecutionImpactPanel {...f.props}/>);await act(async()=>oldClick());
  expect(oldProof.isCurrent()).toBe(false);expect(f.onConfirm).toHaveBeenCalledTimes(1);expect(checkbox().checked).toBe(false);
});
it.each(['owner','current','permission'])('does not revive old confirmation after %s A/B/A', async kind => {
  const f=setup();await confirm();const old=f.onConfirm.mock.calls[0][0] as ExecutionImpactConfirmation;
  const changed={...f.props,...(kind==='owner'?{owner:{}}:kind==='current'?{current:false}:{canConfirm:false})};
  f.rerender(<ExecutionImpactPanel {...changed}/>);f.rerender(<ExecutionImpactPanel {...f.props}/>);
  expect(old.isCurrent()).toBe(false);expect(checkbox().checked).toBe(false);
});
it('refuses unrendered in-place mutation at the action boundary', async () => {
  const f=setup();await acknowledge();const old=retained(button());f.props.input.command.parameters.seed=99;
  await act(async()=>old());expect(f.onConfirm).not.toHaveBeenCalled();
});
it('ignores a late fingerprint from an earlier input', async () => {
  const completions:((value:ArrayBuffer)=>void)[]=[];
  vi.stubGlobal('crypto',{subtle:{digest:vi.fn(()=>new Promise<ArrayBuffer>(resolve=>completions.push(resolve)))}});
  const f=setup(), next=structuredClone(f.props.input);next.command.prompt='next';f.rerender(<ExecutionImpactPanel {...f.props} input={next}/>);
  await act(async()=>completions[0](new Uint8Array(32).buffer));expect(checkbox().disabled).toBe(true);
  await act(async()=>completions[1](new Uint8Array(32).fill(1).buffer));expect(checkbox().disabled).toBe(false);expect(checkbox().checked).toBe(false);
});
it.each(['missing incarnation','cross project','cross branch','shared template'])('does not confirm %s', async kind => {
  const f=setup(), input=structuredClone(f.props.input);
  if(kind==='missing incarnation')input.scope.incarnation='';if(kind==='cross project')input.previousJob!.novel_id='other';
  if(kind==='cross branch')input.previousJob!.branch_id='other';if(kind==='shared template')input.editScope='SHARED_TEMPLATE';
  f.rerender(<ExecutionImpactPanel {...f.props} input={input}/>);await act(async()=>{});expect(checkbox().disabled).toBe(true);expect(button().disabled).toBe(true);expect(f.onConfirm).not.toHaveBeenCalled();
});
it('hides retired input content and refuses an external current guard', async () => {
  const f=setup();await confirm();const proof=f.onConfirm.mock.calls[0][0] as ExecutionImpactConfirmation;vi.mocked(f.props.isCurrent).mockReturnValue(false);
  expect(proof.isCurrent()).toBe(false);f.rerender(<ExecutionImpactPanel {...f.props} current={false}/>);
  expect(screen.queryByText('Synthetic original prompt')).toBeNull();expect(screen.getByText(/原输入范围已失效/)).toBeTruthy();
});
it('retires receipts on unmount and fails closed if an owner guard throws', async () => {
  const f=setup();await confirm();const proof=f.onConfirm.mock.calls[0][0] as ExecutionImpactConfirmation;
  vi.mocked(f.props.isCurrent).mockImplementation(()=>{throw new Error('synthetic retired owner');});expect(proof.isCurrent()).toBe(false);
  f.unmount();expect(proof.isCurrent()).toBe(false);
});
it('fails closed when hashing fails', async () => {
  vi.stubGlobal('crypto',{subtle:{digest:vi.fn(async()=>{throw new Error('synthetic digest failure');})}});const f=setup();
  await screen.findByText(/输入指纹核对失败/);expect(button().disabled).toBe(true);expect(f.onConfirm).not.toHaveBeenCalled();
});
