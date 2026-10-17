// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import type { Button } from '../ui/primitives';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import type { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import { newDocument, type CreativeDocument } from './types';
const callbacks = vi.hoisted(() => new Map<string, NonNullable<ComponentProps<typeof Button>['onClick']>>());
vi.mock('../ui/primitives', async original => {
  const actual = await original<typeof import('../ui/primitives')>();
  return { ...actual, Button: (props: ComponentProps<typeof Button>) => {
    if (typeof props.children === 'string' && props.onClick) callbacks.set(props.children, props.onClick);
    return <actual.Button {...props} />;
  } };
});
const probe = vi.hoisted(() => ({ review: undefined as ComponentProps<typeof GraphDirectorProposalReview> | undefined }));
vi.mock('./GraphDirectorProposalReview', () => ({ hasDirectorProposalReview: () => true,
  GraphDirectorProposalReview: (props: ComponentProps<typeof GraphDirectorProposalReview>) => { probe.review = props; return null; } }));
const pin = { id: 'reviewed', version: 3, digest: 'a'.repeat(64) };
const document = (): CreativeDocument => ({ ...newDocument('DIRECTOR'), source_independent: true, id: pin.id, version: pin.version,
  title: 'Reviewed draft', status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {} });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const button = () => screen.getByRole('button', { name: '将此审核草稿添加到画布' }) as HTMLButtonElement;
afterEach(() => { cleanup(); probe.review = undefined; callbacks.clear(); });
async function fixture() {
  const client = { capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }),
    export: vi.fn().mockResolvedValue({ document: document(), document_digest: pin.digest }), list: vi.fn(), history: vi.fn(), derive: vi.fn(), create: vi.fn(), update: vi.fn() } as unknown as GraphDirectorSource;
  const insert = vi.fn().mockReturnValue(true);
  const props: ComponentProps<typeof GraphDirectorConsole> = { client, active: true, canMutate: true, busy: false, isCurrent: () => true,
    read: work => work(), mutate: work => work(), onDirtyChange: vi.fn(), selectionKey: 'graph:1:node',
    canvasHandoff: { available: true, scope: {}, verificationScope: {}, isVerificationCurrent: () => true, insert } };
  const view = render(<GraphDirectorConsole {...props} />); click('打开导演总控台');
  await waitFor(() => expect(probe.review).toBeTruthy());
  act(() => probe.review!.onDocument(document()));
  return { props, view, client, insert };
}
it('does not insert on review or export; explicit add sends only the scalar pin once and never saves either owner', async () => {
  const { insert, client, props } = await fixture(); expect(button().disabled).toBe(true); expect(insert).not.toHaveBeenCalled();
  click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false)); expect(insert).not.toHaveBeenCalled();
  click('将此审核草稿添加到画布'); click('将此审核草稿添加到画布');
  expect(insert).toHaveBeenCalledTimes(1); expect(insert).toHaveBeenCalledWith(pin, props.canvasHandoff!.scope);
  expect(client.create).not.toHaveBeenCalled(); expect(client.update).not.toHaveBeenCalled();
});
it.each(['version', 'status', 'digest'] as const)('does not enable placement for a mismatched %s export', async field => {
  const { client, insert } = await fixture();
  vi.mocked(client.export).mockResolvedValue({ document: { ...document(), ...(field === 'version' ? { version: 4 } : field === 'status' ? { status: 'APPROVED' as const } : {}) }, document_digest: field === 'digest' ? 'bad' : pin.digest, format: '', boundary: '' });
  click('核对导演原文档版本'); await waitFor(() => expect(screen.getByRole('button', { name: '核对导演原文档版本' }).hasAttribute('disabled')).toBe(false));
  expect(button().disabled).toBe(true); expect(insert).not.toHaveBeenCalled();
});
it('rejects late export after Graph authority ABA or source IME activity', async () => {
  const { client, view, props } = await fixture();
  let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
  vi.mocked(client.export).mockReturnValue(new Promise(yes => resolve = yes)); click('核对导演原文档版本');
  view.rerender(<GraphDirectorConsole {...props} canvasHandoff={{ ...props.canvasHandoff!, verificationScope: {} }} />);
  view.rerender(<GraphDirectorConsole {...props} canvasHandoff={{ ...props.canvasHandoff!, verificationScope: {} }} />);
  await act(async () => resolve({ document: document(), document_digest: pin.digest, format: '', boundary: '' }));
  expect(button().disabled).toBe(true);
  vi.mocked(client.export).mockReturnValue(new Promise(yes => resolve = yes)); click('核对导演原文档版本');
  fireEvent.compositionStart(screen.getByLabelText('文档标题')); fireEvent.compositionEnd(screen.getByLabelText('文档标题'));
  await act(async () => resolve({ document: document(), document_digest: pin.digest, format: '', boundary: '' }));
  expect(button().disabled).toBe(true);
});
it('source edits retire verification and a failed placement retains the reviewed Creative draft', async () => {
  const { insert } = await fixture(); click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  insert.mockReturnValue(false); click('将此审核草稿添加到画布');
  expect(screen.getByDisplayValue('Reviewed draft')).toBeTruthy(); expect(button().disabled).toBe(true);
  click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Edited draft' } }); expect(button().disabled).toBe(true);
});

it('retires a verified pin after target Graph or selection changes rather than borrowing the new insertion token', async () => {
  const { props, view, insert } = await fixture(); click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  view.rerender(<GraphDirectorConsole {...props} canvasHandoff={{ ...props.canvasHandoff!, scope: {}, verificationScope: {} }} />);
  expect(button().disabled).toBe(true); click('将此审核草稿添加到画布'); expect(insert).not.toHaveBeenCalled();
  view.rerender(<GraphDirectorConsole {...props} />); expect(button().disabled).toBe(true);
  view.rerender(<GraphDirectorConsole {...props} selectionKey="other-graph" />);
  view.rerender(<GraphDirectorConsole {...props} />); expect(button().disabled).toBe(true);
});

it.each(['edit', 'fresh', 'new-review'] as const)('rejects retained Add after synchronous source %s', async operation => {
  const { insert } = await fixture(); click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  const retained = callbacks.get('将此审核草稿添加到画布')!;
  act(() => {
    if (operation === 'edit') fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Changed' } });
    else if (operation === 'fresh') click('新建文档');
    else probe.review!.onDocument({ ...document(), id: 'new-review' });
    retained({} as never);
  });
  expect(insert).not.toHaveBeenCalled();
});
it('rejects an old Verify handler after a different reviewed receipt has been adopted', async () => {
  const { client, insert } = await fixture(); const retained = callbacks.get('核对导演原文档版本')!;
  act(() => { probe.review!.onDocument({ ...document(), id: 'new-review' }); retained({} as never); });
  expect(client.export).not.toHaveBeenCalled(); expect(insert).not.toHaveBeenCalled();
});

it.each(['edit', 'choice', 'ime'] as const)('rejects retained Verify before export after same-receipt %s', async operation => {
  const { client } = await fixture(); const retained = callbacks.get('核对导演原文档版本')!;
  act(() => {
    if (operation === 'edit') fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Keep this edited draft' } });
    else if (operation === 'choice') fireEvent.change(screen.getByLabelText('总控台原导演文档'), { target: { value: '' } });
    else { fireEvent.compositionStart(screen.getByLabelText('文档标题')); fireEvent.compositionEnd(screen.getByLabelText('文档标题')); }
    retained({} as never);
  });
  expect(client.export).not.toHaveBeenCalled();
  if (operation === 'edit') expect(screen.getByDisplayValue('Keep this edited draft')).toBeTruthy();
});

it('requires a fresh explicit original-owner verification before placing into a different target', async () => {
  const { props, view, insert, client } = await fixture(); click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  const next = { ...props.canvasHandoff!, scope: {}, verificationScope: {} };
  view.rerender(<GraphDirectorConsole {...props} canvasHandoff={next} />);
  expect(button().disabled).toBe(true); expect(client.export).toHaveBeenCalledTimes(1);
  click('核对导演原文档版本'); await waitFor(() => expect(button().disabled).toBe(false));
  click('将此审核草稿添加到画布'); expect(insert).toHaveBeenCalledTimes(1); expect(insert).toHaveBeenCalledWith(pin, next.scope);
  expect(client.export).toHaveBeenCalledTimes(2);
});
