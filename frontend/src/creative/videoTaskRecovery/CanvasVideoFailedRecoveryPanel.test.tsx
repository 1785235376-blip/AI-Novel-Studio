// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { CanvasVideoFailedRecoveryPanel as Panel, type CanvasVideoFailedRecoveryPanelProps as Props } from './CanvasVideoFailedRecoveryPanel';
import { recoveryFixture } from './recovery.testFixtures';

afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
function setup(patch: Partial<Props> = {}, strict = false) {
  const props: Props = { ...recoveryFixture(), owner: {}, current: true, busy: false, canMutate: true,
    isCurrent: () => true, newRequestId: vi.fn(() => 'new-request'), onDerive: vi.fn(), onRead: vi.fn(), ...patch };
  const view = render(strict ? <StrictMode><Panel {...props} /></StrictMode> : <Panel {...props} />);
  return { props, view };
}
const deriveButton = () => screen.getByRole('button', { name: '派生新的预览草稿' }) as HTMLButtonElement;
const readButton = () => screen.getByRole('button', { name: '读取原任务记录' }) as HTMLButtonElement;
const consent = () => screen.getByRole('checkbox') as HTMLInputElement;
function retained(element: HTMLElement, event = 'onClick') {
  return (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!][event] as (...args: any[]) => void;
}
it('allocates no identity until one explicit confirmed click and prepares only one draft', async () => {
  const fetch = vi.fn(); vi.stubGlobal('fetch', fetch); const { props } = setup();
  expect(deriveButton().disabled).toBe(true); expect(props.newRequestId).not.toHaveBeenCalled();
  fireEvent.click(consent()); const click = retained(deriveButton());
  await act(async () => { click(); click(); });
  expect(props.newRequestId).toHaveBeenCalledTimes(1); expect(props.onDerive).toHaveBeenCalledTimes(1);
  const draft = vi.mocked(props.onDerive).mock.calls[0][0];
  expect(draft).toMatchObject({ request_id: 'new-request', derived_from: { owner: 'timeline', job_id: 'original-failed-job', job_version: 5 } });
  expect(Object.hasOwn(draft, 'timeline_snapshot')).toBe(false); expect(props.onRead).not.toHaveBeenCalled(); expect(fetch).not.toHaveBeenCalled();
});
it.each([undefined, false, true])('shows the preserved audio choice %s without changing it', audio => {
  setup(recoveryFixture(audio)); expect(screen.getByText(`源音轨：${audio === true ? '明确包含' : audio === false ? '明确不包含' : '原请求未指定'}`)).toBeTruthy();
});
it.each(['UNKNOWN', 'RUNNING', 'CANCELLED', 'QUEUED'] as const)('only reads the original record for %s', status => {
  const f = recoveryFixture(); f.job.status = status; const { props } = setup(f);
  expect(consent().disabled).toBe(true); expect(deriveButton().disabled).toBe(true); fireEvent.click(readButton());
  expect(props.onRead).toHaveBeenCalledTimes(1); expect(props.newRequestId).not.toHaveBeenCalled(); expect(props.onDerive).not.toHaveBeenCalled();
});
it('does not call either old getter when current=false, even through retained callbacks', () => {
  const { props, view } = setup(); fireEvent.click(consent()); const click = retained(deriveButton()), read = retained(readButton());
  const ownerGetter = vi.fn(() => { throw new Error('must not read owner getter'); });
  const taskGetter = vi.fn(() => { throw new Error('must not read task getter'); });
  view.rerender(<Panel {...props} current={false} isCurrent={ownerGetter} task={{ ...props.task, isCurrent: taskGetter }} />);
  act(() => { click(); read(); }); expect(screen.queryByRole('checkbox')).toBeNull();
  expect(ownerGetter).not.toHaveBeenCalled(); expect(taskGetter).not.toHaveBeenCalled(); expect(props.newRequestId).not.toHaveBeenCalled();
});
it.each(['job', 'job-mutation', 'task', 'source', 'pin', 'owner', 'owner-mutation', 'permission', 'busy', 'isCurrent', 'task-getter', 'id-getter', 'derive', 'read'])(
  'retires confirmed callbacks across observed %s changes and ABA', kind => {
    const { props, view } = setup(); fireEvent.click(consent()); const click = retained(deriveButton()), read = retained(readButton());
    const next = { ...props };
    if (kind === 'job') next.job = { ...props.job, version: 6 };
    if (kind === 'job-mutation') props.job.version++;
    if (kind === 'task') next.task = { ...props.task };
    if (kind === 'source') next.task = { ...props.task, source: { ...props.task.source, version: 3 } };
    if (kind === 'pin') next.task = { ...props.task, returnBinding: { ...props.task.returnBinding!, card_id: 'other' } };
    if (kind === 'owner') next.owner = {};
    if (kind === 'owner-mutation') Object.assign(props.owner, { generation: 2 });
    if (kind === 'permission') next.canMutate = false;
    if (kind === 'busy') next.busy = true;
    if (kind === 'isCurrent') next.isCurrent = () => true;
    if (kind === 'task-getter') next.task = { ...props.task, isCurrent: () => true };
    if (kind === 'id-getter') next.newRequestId = vi.fn(() => 'other');
    if (kind === 'derive') next.onDerive = vi.fn();
    if (kind === 'read') next.onRead = vi.fn();
    view.rerender(<Panel {...next} />); act(() => { click(); read(); });
    view.rerender(<Panel {...props} />); act(() => { click(); read(); });
    expect(consent().checked).toBe(false); expect(props.newRequestId).not.toHaveBeenCalled(); expect(props.onDerive).not.toHaveBeenCalled(); expect(props.onRead).not.toHaveBeenCalled();
  });
it.each(['owner-getter', 'task-getter', 'job', 'source', 'pin', 'owner', 'method'])(
  'latches %s invalidation observed without rerender before an ABA restoration', kind => {
    let current = true; const f = recoveryFixture(), getter = () => current;
    if (kind === 'task-getter') f.task.isCurrent = getter;
    const { props, view } = setup({ ...f, isCurrent: kind === 'owner-getter' ? getter : () => true });
    fireEvent.click(consent()); const click = retained(deriveButton());
    const original = props.task.isCurrent;
    if (kind === 'owner-getter' || kind === 'task-getter') current = false;
    if (kind === 'job') props.job.version++;
    if (kind === 'source') props.task.source.version++;
    if (kind === 'pin') props.task.returnBinding!.canvas_version++;
    if (kind === 'owner') Object.assign(props.owner, { changed: true });
    if (kind === 'method') props.task.isCurrent = () => true;
    act(() => click());
    current = true;
    if (kind === 'job') props.job.version--;
    if (kind === 'source') props.task.source.version--;
    if (kind === 'pin') props.task.returnBinding!.canvas_version--;
    if (kind === 'owner') delete (props.owner as any).changed;
    if (kind === 'method') props.task.isCurrent = original;
    act(() => click()); view.rerender(<Panel {...props} />);
    expect(deriveButton().disabled).toBe(true); expect(consent().checked).toBe(false); expect(props.newRequestId).not.toHaveBeenCalled();
  });
it('rechecks after the identity getter changes the original origin', async () => {
  let current = true; const { props } = setup({ isCurrent: () => current, newRequestId: vi.fn(() => { current = false; return 'new'; }) });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(props.newRequestId).toHaveBeenCalledTimes(1); expect(props.onDerive).not.toHaveBeenCalled();
});
it('consumes a rejected operation and displays its error on the same current owner', async () => {
  const { props } = setup({ onDerive: vi.fn().mockRejectedValue(new Error('draft rejected')) });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(screen.getByRole('alert').textContent).toBe('draft rejected'); expect(deriveButton().disabled).toBe(true);
  fireEvent.click(deriveButton()); expect(props.onDerive).toHaveBeenCalledTimes(1);
});
it('consumes reused request identities and never calls the draft owner', async () => {
  const { props } = setup({ newRequestId: vi.fn(() => 'original-request') });
  fireEvent.click(consent()); await act(async () => { fireEvent.click(deriveButton()); });
  expect(screen.getByRole('alert')).toBeTruthy(); expect(props.onDerive).not.toHaveBeenCalled(); expect(deriveButton().disabled).toBe(true);
});
it('suppresses late rejected work after another owner arrives', async () => {
  let reject!: (e: Error) => void; const pending = new Promise<void>((_, fail) => { reject = fail; });
  const { props, view } = setup({ onDerive: vi.fn(() => pending) }); fireEvent.click(consent()); fireEvent.click(deriveButton());
  view.rerender(<Panel {...props} owner={{ next: true }} />);
  await act(async () => { reject(new Error('late failure')); await pending.catch(() => undefined); });
  expect(screen.queryByText('late failure')).toBeNull(); expect(consent().checked).toBe(false);
});
it('only reads once, retires consent and suppresses old callbacks', async () => {
  const { props } = setup(); fireEvent.click(consent()); const click = retained(deriveButton()), read = retained(readButton());
  await act(async () => { read(); read(); click(); });
  expect(props.onRead).toHaveBeenCalledTimes(1); expect(props.newRequestId).not.toHaveBeenCalled(); expect(consent().checked).toBe(false);
});
it('allows read-only checking of an unavailable task origin without mutation permission', () => {
  const f = recoveryFixture(); f.task.isCurrent = () => false; const { props } = setup({ ...f, canMutate: false });
  expect(deriveButton().disabled).toBe(true); fireEvent.click(readButton()); expect(props.onRead).toHaveBeenCalledTimes(1);
});
it('runs under StrictMode and invalidates retained handlers on unmount', async () => {
  const { props, view } = setup({}, true); fireEvent.click(consent());
  await act(async () => { fireEvent.click(deriveButton()); }); expect(props.onDerive).toHaveBeenCalledTimes(1);
  const read = retained(readButton()); view.unmount(); act(() => read()); expect(props.onRead).not.toHaveBeenCalled();
});
it('never displays unvalidated parameter payloads', () => {
  const f = recoveryFixture(); Object.assign(f.job.canvas_video.parameters, { private_payload: 'secret-marker' });
  setup(f); expect(screen.queryByText(/secret-marker/)).toBeNull(); expect(deriveButton().disabled).toBe(true);
});
it('retires retained read callbacks after observing an owner getter ABA without rerender', () => {
  let current = true; const { props } = setup({ isCurrent: () => current }); const read = retained(readButton());
  current = false; act(() => read()); current = true; act(() => read()); expect(props.onRead).not.toHaveBeenCalled();
});
it('does not expose a late read failure after unmount', async () => {
  let reject!: (error: Error) => void; const pending = new Promise<void>((_, fail) => { reject = fail; });
  const { props, view } = setup({ onRead: vi.fn(() => pending) }); fireEvent.click(readButton()); view.unmount();
  await act(async () => { reject(new Error('late read failure')); await pending.catch(() => undefined); });
  expect(props.onRead).toHaveBeenCalledTimes(1); expect(screen.queryByRole('alert')).toBeNull();
});
