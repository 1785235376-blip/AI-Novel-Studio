// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasAudioFailedRecoveryPanel as Panel, type CanvasAudioFailedRecoveryPanelProps as Props } from './CanvasAudioFailedRecoveryPanel';
import { recoveryFixture } from './recovery.testFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(patch: Partial<Props> = {}) {
  const f = recoveryFixture(); const props: Props = { ...f, owner: {}, current: true, busy: false, canMutate: true,
    isCurrent: () => true, newRequestId: vi.fn(() => 'new-request'), onDerive: vi.fn(), onRead: vi.fn(), ...patch };
  const view = render(<Panel {...props} />); return { ...f, props, view };
}
const deriveButton = () => screen.getByRole('button', { name: '派生新任务草稿' }) as HTMLButtonElement;
const consent = () => screen.getByRole('checkbox') as HTMLInputElement;
function retained(element: HTMLElement, event = 'onClick') {
  return (element as any)[Object.keys(element).find(k => k.startsWith('__reactProps$'))!][event] as (...args: any[]) => void;
}
it('requires explicit consent, generates one new identity only on click, and calls only the draft owner', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const { props } = setup();
  expect(screen.getByText(/原任务 original-failed-job/)).toBeTruthy(); expect(screen.getByText(/原请求 original-request/)).toBeTruthy();
  expect(screen.getByText(/原参数/).textContent).toContain('fade_out_ms');
  expect(deriveButton().disabled).toBe(true); expect(props.newRequestId).not.toHaveBeenCalled();
  fireEvent.click(consent()); expect(deriveButton().disabled).toBe(false); const old = retained(deriveButton());
  await act(async () => { old(); old(); });
  expect(props.newRequestId).toHaveBeenCalledTimes(1); expect(props.onDerive).toHaveBeenCalledTimes(1);
  expect(vi.mocked(props.onDerive).mock.calls[0][0]).toMatchObject({ request_id: 'new-request', derived_from: { job_id: 'original-failed-job', job_version: 4 } });
  expect(props.onRead).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
});
it.each(['UNKNOWN', 'RUNNING', 'QUEUED', 'APPROVED'] as const)('allows only original-record reading for %s', status => {
  const f = recoveryFixture(); f.job.status = status; const { props } = setup({ job: f.job });
  expect(consent().disabled).toBe(true); expect(deriveButton().disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }));
  expect(props.onRead).toHaveBeenCalledTimes(1); expect(props.onDerive).not.toHaveBeenCalled(); expect(props.newRequestId).not.toHaveBeenCalled();
});
it('hides stale-owner content immediately when current becomes false', () => {
  const { props, view } = setup(); fireEvent.click(consent()); const old = retained(deriveButton());
  view.rerender(<Panel {...props} current={false} />); expect(screen.queryByRole('region')).toBeNull();
  act(() => old()); expect(props.onDerive).not.toHaveBeenCalled();
  view.rerender(<Panel {...props} />); expect(consent().checked).toBe(false); act(() => old()); expect(props.newRequestId).not.toHaveBeenCalled();
});
it.each(['job', 'parameters', 'task', 'pin', 'owner', 'owner mutation', 'client', 'permission', 'busy'])(
  'retires confirmed callbacks after %s changes, including observed ABA', change => {
    const { props, view } = setup(); fireEvent.click(consent()); const old = retained(deriveButton());
    const next = { ...props };
    if (change === 'job') next.job = { ...props.job, version: 5 };
    if (change === 'parameters') { next.job = structuredClone(props.job); next.job.command!.parameters.gain_db = -3; next.job.execution_recipe.parameters = { ...next.job.command!.parameters }; }
    if (change === 'task') next.task = { ...props.task };
    if (change === 'pin') next.task = { ...props.task, returnBinding: { ...props.task.returnBinding!, card_id: 'other' } };
    if (change === 'owner') next.owner = {};
    if (change === 'owner mutation') Object.assign(props.owner, { generation: 2 });
    if (change === 'client') next.isCurrent = () => true;
    if (change === 'permission') next.canMutate = false;
    if (change === 'busy') next.busy = true;
    view.rerender(<Panel {...next} />); act(() => old());
    view.rerender(<Panel {...props} />); act(() => old());
    expect(consent().checked).toBe(false); expect(props.onDerive).not.toHaveBeenCalled(); expect(props.newRequestId).not.toHaveBeenCalled();
  });
it.each(['client', 'task', 'parameters'])( 'latches a false or mutated %s observed by a retained callback before ABA', kind => {
  let valid = true; const f = recoveryFixture(), isCurrent = () => valid;
  if (kind === 'task') f.task.isCurrent = isCurrent;
  const { props, view } = setup({ ...f, isCurrent: kind === 'client' ? isCurrent : () => true });
  fireEvent.click(consent()); const old = retained(deriveButton());
  if (kind === 'parameters') props.job.command!.parameters.gain_db = -1; else valid = false;
  act(() => old());
  if (kind === 'parameters') props.job.command!.parameters.gain_db = -6; else valid = true;
  act(() => old()); view.rerender(<Panel {...props} />);
  expect(deriveButton().disabled).toBe(true); expect(props.onDerive).not.toHaveBeenCalled(); expect(props.newRequestId).not.toHaveBeenCalled();
});
it('drops a callback whose request-id generator changes the current origin', async () => {
  let valid = true; const f = recoveryFixture();
  const { props } = setup({ ...f, isCurrent: () => valid, newRequestId: vi.fn(() => { valid = false; return 'new'; }) });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(props.newRequestId).toHaveBeenCalledTimes(1); expect(props.onDerive).not.toHaveBeenCalled();
});
it('does not expose a late rejected derive on another owner or restore the old consent', async () => {
  let reject!: (error: Error) => void; const pending = new Promise<void>((_, fail) => { reject = fail; });
  const { props, view } = setup({ onDerive: vi.fn(() => pending) });
  fireEvent.click(consent()); fireEvent.click(deriveButton()); expect(deriveButton().disabled).toBe(true);
  view.rerender(<Panel {...props} owner={{ generation: 2 }} />);
  await act(async () => { reject(new Error('old owner failure')); await pending.catch(() => undefined); });
  expect(screen.queryByText('old owner failure')).toBeNull(); expect(consent().checked).toBe(false);
});
it('keeps a rejected action consumed and presents its error without a second draft', async () => {
  const { props } = setup({ onDerive: vi.fn().mockRejectedValue(new Error('draft owner rejected')) });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(screen.getByRole('alert').textContent).toBe('draft owner rejected'); expect(deriveButton().disabled).toBe(true);
  fireEvent.click(deriveButton()); expect(props.onDerive).toHaveBeenCalledTimes(1);
});
it('permits read-only reload for changed task target and denies stale mutation', () => {
  const f = recoveryFixture(); f.task.isCurrent = () => false; const { props } = setup(f);
  expect(deriveButton().disabled).toBe(true); fireEvent.click(screen.getByRole('button', { name: '读取原任务记录' }));
  expect(props.onRead).toHaveBeenCalledTimes(1); expect(props.onDerive).not.toHaveBeenCalled();
});
it('works under StrictMode and drops retained callbacks after unmount', async () => {
  const f = recoveryFixture(), props: Props = { ...f, owner: {}, current: true, busy: false, canMutate: true,
    isCurrent: () => true, newRequestId: vi.fn(() => 'new'), onDerive: vi.fn(), onRead: vi.fn() };
  const view = render(<StrictMode><Panel {...props} /></StrictMode>);
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); }); expect(props.onDerive).toHaveBeenCalledTimes(1);
  const old = retained(screen.getByRole('button', { name: '读取原任务记录' })); view.unmount(); act(() => old()); expect(props.onRead).not.toHaveBeenCalled();
});

it('does not display arbitrary parameter extensions or disclose rejected receipt payloads', () => {
  const f = recoveryFixture(); Object.assign(f.job.command!.parameters, { credential: 'private-payload' });
  setup(f); expect(screen.queryByText(/private-payload/)).toBeNull(); expect(deriveButton().disabled).toBe(true);
});
it('rejects a reused identity from the generator and consumes that explicit operation', async () => {
  const { props } = setup({ newRequestId: vi.fn(() => 'original-request') });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(props.newRequestId).toHaveBeenCalledTimes(1); expect(props.onDerive).not.toHaveBeenCalled();
  expect(screen.getByRole('alert')).toBeTruthy(); expect(deriveButton().disabled).toBe(true);
});
it('retires retained checkbox callbacks when their render is replaced', () => {
  const { props, view } = setup(); const old = retained(consent(), 'onChange');
  view.rerender(<Panel {...props} owner={{ generation: 2 }} />);
  act(() => old({ target: { checked: true } }));
  expect(consent().checked).toBe(false); expect(props.newRequestId).not.toHaveBeenCalled();
});

it('does not revive an old read callback after an observed owner mutation and ABA', () => {
  const { props } = setup(); const old = retained(screen.getByRole('button', { name: '读取原任务记录' }));
  Object.assign(props.owner, { generation: 2 }); act(() => old());
  delete (props.owner as { generation?: number }).generation; act(() => old());
  expect(props.onRead).not.toHaveBeenCalled(); expect(props.newRequestId).not.toHaveBeenCalled();
});
it('permits only one original-record read from retained repeated clicks', async () => {
  let finish!: () => void; const pending = new Promise<void>(resolve => { finish = resolve; });
  const { props } = setup({ onRead: vi.fn(() => pending) }); const old = retained(screen.getByRole('button', { name: '读取原任务记录' }));
  act(() => { old(); old(); }); expect(props.onRead).toHaveBeenCalledTimes(1);
  await act(async () => { finish(); await pending; }); act(() => old()); expect(props.onRead).toHaveBeenCalledTimes(1);
});
