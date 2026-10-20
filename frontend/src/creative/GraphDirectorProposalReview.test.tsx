// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { ApiError } from '../api';
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

it('loads sources only explicitly and keeps the original client stable across pending and busy renders', async () => {
  const { client, props } = setup(); const view = render(<GraphDirectorProposalReview {...props} />);
  expect(client.list).not.toHaveBeenCalled(); await open(); const original = probe.current!.client;
  act(() => probe.current!.onPendingChange!(true));
  expect(props.onPendingChange).toHaveBeenLastCalledWith(true);
  expect((screen.getByRole('button', { name: '收起导演建议审核' }) as HTMLButtonElement).disabled).toBe(true);
  view.rerender(<GraphDirectorProposalReview {...props} busy />); expect(probe.current!.client).toBe(original);
  view.rerender(<GraphDirectorProposalReview {...props} />); act(() => probe.current!.onPendingChange!(false));
  expect(probe.current!.client).toBe(original); expect(props.onPendingChange).toHaveBeenLastCalledWith(false);
  expect(client.dispatchModel).not.toHaveBeenCalled();
});

it('uses the parent read and mutation owners rather than calling around them', async () => {
  const { client, props } = setup(); render(<GraphDirectorProposalReview {...props} />); await open();
  await probe.current!.client.get('original-id'); expect(props.read).toHaveBeenCalledTimes(2); expect(client.get).toHaveBeenCalledWith('original-id', undefined);
  await probe.current!.client.propose(document); expect(props.mutate).toHaveBeenCalledTimes(1); expect(client.propose).toHaveBeenCalledWith(document);
});

it.each(['busy', 'readonly', 'retired'] as const)('refuses %s proposal writes before entering the original owner', async state => {
  const { client, props } = setup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const bound = probe.current!.client;
  view.rerender(<GraphDirectorProposalReview {...props} busy={state === 'busy'} canMutate={state !== 'readonly'} isCurrent={() => state !== 'retired'} />);
  await expect(bound.propose(document)).rejects.toThrow(); expect(client.propose).not.toHaveBeenCalled(); expect(props.mutate).not.toHaveBeenCalled();
});

it.each(['read', 'write'] as const)('rejects late %s receipts across active A→inactive→A without borrowing the new lifetime', async kind => {
  const { client, props } = setup(); const view = render(<GraphDirectorProposalReview {...props} />); await open();
  const pending = deferred<CreativeDocument>();
  if (kind === 'read') client.get.mockReturnValue(pending.promise); else client.propose.mockReturnValue(pending.promise);
  const result = (kind === 'read' ? probe.current!.client.get('original') : probe.current!.client.propose(document)).catch(error => error);
  view.rerender(<GraphDirectorProposalReview {...props} active={false} />); view.rerender(<GraphDirectorProposalReview {...props} />);
  await act(async () => pending.resolve(document));
  expect(await result).toMatchObject({ status: 403 }); expect(props.onDocument).not.toHaveBeenCalled();
});

it('does not display delayed screenplay sources after an A→inactive→A read', async () => {
  const { client, props } = setup(), pending = deferred<{ items: CreativeDocument[] }>(); client.list.mockReturnValue(pending.promise);
  const view = render(<GraphDirectorProposalReview {...props} />); fireEvent.click(screen.getByRole('button', { name: '从已保存剧本打开导演建议审核' }));
  view.rerender(<GraphDirectorProposalReview {...props} active={false} />); view.rerender(<GraphDirectorProposalReview {...props} />);
  await act(async () => pending.resolve({ items: [document] })); expect(screen.queryByText(document.title)).toBeNull(); expect(probe.current).toBeUndefined();
});

it('clears source output when a refresh is denied by its original owner', async () => {
  const { client, props } = setup(); render(<GraphDirectorProposalReview {...props} />); await open();
  client.list.mockRejectedValue(new ApiError({ status: 403, code: 'PROJECT_SCOPE_FORBIDDEN', message: 'revoked' }));
  fireEvent.click(screen.getByRole('button', { name: '刷新原剧本来源' })); await waitFor(() => expect(props.onDenied).toHaveBeenCalledTimes(1));
  expect(screen.queryByText(document.title)).toBeNull(); expect(client.dispatchModel).not.toHaveBeenCalled();
});
