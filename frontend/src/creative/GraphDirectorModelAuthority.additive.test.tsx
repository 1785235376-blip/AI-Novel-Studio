// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { AIDirectorPanel } from './AIDirectorPanel';
import { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import { newDocument, type CreativeDocument } from './types';

type PanelProps = ComponentProps<typeof AIDirectorPanel>;
type ReviewProps = ComponentProps<typeof GraphDirectorProposalReview>;
const probe = vi.hoisted(() => ({ current: undefined as PanelProps | undefined }));
vi.mock('./AIDirectorPanel', () => ({ AIDirectorPanel: (props: PanelProps) => {
  probe.current = props;
  return <section aria-label="original panel probe">{props.documents.map(row => <p key={row.id}>{row.title}</p>)}</section>;
} }));
const deferred = <T,>() => { let resolve!: (value: T) => void; const promise = new Promise<T>(yes => resolve = yes); return { promise, resolve }; };
const document: CreativeDocument = { ...newDocument('SCREENPLAY'), id: 'source', version: 2, title: 'Original saved script', status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} };
function setup() {
  const client = { list: vi.fn().mockResolvedValue({ items: [document] }), proposals: vi.fn(), proposal: vi.fn(), get: vi.fn(),
    modelRoutes: vi.fn(), propose: vi.fn(), review: vi.fn().mockResolvedValue({ document }), cancelProposal: vi.fn(),
    previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn() };
  const props = { client, active: true, canMutate: true, busy: false, isCurrent: () => true,
    read: vi.fn(async (work: () => Promise<unknown>) => work()) as ReviewProps['read'],
    mutate: vi.fn(async (work: () => Promise<unknown>) => work()) as ReviewProps['mutate'],
    onPendingChange: vi.fn(), onDocument: vi.fn(), onDenied: vi.fn() };
  return { client, props };
}
async function open() { fireEvent.click(screen.getByRole('button', { name: '从已保存剧本打开导演建议审核' })); await screen.findByRole('region', { name: 'original panel probe' }); }
beforeEach(() => { probe.current = undefined; }); afterEach(cleanup);


const readMethods = ['readStatus', 'readAdoptedDraft', 'readPreview', 'readPending', 'reconcileReview'] as const;
const writeMethods = ['preview', 'dispatch', 'prepareReview', 'review', 'cancel'] as const;
function modelSetup() {
  const base = setup();
  const model = Object.fromEntries([...readMethods, ...writeMethods].map(name => [name, vi.fn().mockResolvedValue({ receipt: name })]));
  const factory = vi.fn(() => model as unknown as import('./directorModelClient').DirectorModelClient);
  const props = { ...base.props, client: { ...base.client, independentDirector: factory } };
  return { props, model, factory };
}
function invoke(client: import('./directorModelClient').DirectorModelClient, name: string) {
  // This test isolates the boundary wrapper; strict payload decoding has its own captured-wire suite.
  return (client as unknown as Record<string, (...args: unknown[]) => Promise<unknown>>)[name]('proposal', 'argument');
}

it.each([...readMethods, ...writeMethods])('routes %s through its original parent owner without implicit calls', async name => {
  const { props, model, factory } = modelSetup(); render(<GraphDirectorProposalReview {...props} />); await open();
  expect(factory).not.toHaveBeenCalled(); const client = probe.current!.client.independentDirector!();
  expect(factory).toHaveBeenCalledTimes(1); for (const fn of Object.values(model)) expect(fn).not.toHaveBeenCalled();
  const beforeRead = vi.mocked(props.read).mock.calls.length;
  const beforeWrite = vi.mocked(props.mutate).mock.calls.length;
  await invoke(client, name); expect(model[name]).toHaveBeenCalledTimes(1); expect(model[name]).toHaveBeenCalledWith('proposal', 'argument');
  const write = (writeMethods as readonly string[]).includes(name);
  expect(props.read).toHaveBeenCalledTimes(beforeRead + (write ? 0 : 1));
  expect(props.mutate).toHaveBeenCalledTimes(beforeWrite + (write ? 1 : 0));
});

it.each(writeMethods)('blocks retained %s when mutation permission is lost before dispatch', async name => {
  const { props, model } = modelSetup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const client = probe.current!.client.independentDirector!();
  view.rerender(<GraphDirectorProposalReview {...props} canMutate={false} />);
  await expect(invoke(client,name)).rejects.toThrow(); expect(model[name]).not.toHaveBeenCalled();
});

it.each([...readMethods, ...writeMethods])('retires retained %s across inactive then active even before a new request', async name => {
  const { props, model } = modelSetup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const client = probe.current!.client.independentDirector!();
  view.rerender(<GraphDirectorProposalReview {...props} active={false} />); view.rerender(<GraphDirectorProposalReview {...props} />);
  await expect(invoke(client,name)).rejects.toMatchObject({status:403}); expect(model[name]).not.toHaveBeenCalled();
});

it.each(writeMethods)('rejects late %s success when authority changes while the original owner is running', async name => {
  const { props, model } = modelSetup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const pending = deferred<unknown>(); model[name].mockReturnValue(pending.promise);
  const result = invoke(probe.current!.client.independentDirector!(),name).catch(error=>error);
  view.rerender(<GraphDirectorProposalReview {...props} canMutate={false} />);
  await act(async()=>pending.resolve({ receipt:'late' })); expect(await result).toMatchObject({status:403});
  expect(model[name]).toHaveBeenCalledTimes(1); expect(props.onDocument).not.toHaveBeenCalled();
});

it.each(['readPending', 'review'] as const)('does not revive %s after canMutate A→denied→A', async name => {
  const { props, model } = modelSetup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const client = probe.current!.client.independentDirector!();
  view.rerender(<GraphDirectorProposalReview {...props} canMutate={false} />);
  view.rerender(<GraphDirectorProposalReview {...props} canMutate />);
  await expect(invoke(client,name)).rejects.toMatchObject({status:403}); expect(model[name]).not.toHaveBeenCalled();
});
