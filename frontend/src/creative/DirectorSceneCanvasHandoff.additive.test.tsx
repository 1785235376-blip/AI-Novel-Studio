// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import { newDocument, type CreativeDocument } from './types';

const source: CreativeDocument = { ...newDocument('DIRECTOR'), id: 'parent', version: 3, title: 'Parent', status: 'APPROVED',
  actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, source_independent: true,
  scenes: ['a', 'b'].map((id, index) => ({ id, sequence: index + 1, heading: `Scene ${id.toUpperCase()}`, source_chapter_id: null,
    time: '', location: '', characters: [], action: id, dialogue: [], emotion: '', director_notes: [] })) };
const parentPin = { id: source.id, version: source.version, digest: 'a'.repeat(64) };
const child = (): CreativeDocument & { provenance: Record<string, unknown> } => ({ ...source, id: 'child', version: 1, status: 'DRAFT', title: 'Opening', source_independent: false,
  scenes: source.scenes.slice(0, 1), source_documents: { parent: { version: source.version, digest: parentPin.digest } },
  provenance: { method: 'STRUCTURED_DERIVATION', model_called: false, source_document_id: source.id, source_version: source.version,
    input_digest: parentPin.digest, parameters: { rule_version: 'creative-director-scene-scope-v1', responsibility: 'Opening',
      scene_ids: ['a'], copied_approval: false, execution_authority: false } } });
const childPin = { id: 'child', version: 1, digest: 'c'.repeat(64) };
const exported = (document: CreativeDocument, digest = document.id === 'parent' ? parentPin.digest : childPin.digest) => ({
  document: structuredClone(document), document_digest: digest, format: 'creative-json/1', boundary: 'original-owner' });
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const verifyLabel = '重读并核对子导演与来源';
const addLabel = '将子导演添加到当前画布草稿';
const consentLabel = '已核对子导演版本、来源与当前画布，确认只添加一个导演节点';
const retained = (name: string) => {
  const element = screen.getByRole('button', { name });
  return (element as any)[Object.keys(element).find(key => key.startsWith('__reactProps$'))!].onClick as () => void;
};
afterEach(cleanup);
async function fixture() {
  const client = { capabilities: vi.fn(async () => ({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] })),
    export: vi.fn(async (id: string) => exported(id === source.id ? source : child())),
    deriveDirectorScope: vi.fn(async () => child()), list: vi.fn(), history: vi.fn(), derive: vi.fn(), create: vi.fn(), update: vi.fn() };
  const insert = vi.fn(() => true), pending = vi.fn();
  const props: ComponentProps<typeof GraphDirectorConsole> = { client: client as unknown as GraphDirectorSource, pin: parentPin,
    active: true, canMutate: true, busy: false, isCurrent: () => true, read: work => work(), mutate: work => work(),
    selectionKey: 'graph:1:parent', onDirtyChange: pending,
    canvasHandoff: { available: true, scope: {}, verificationScope: {}, isVerificationCurrent: () => true, insert } };
  const view = render(<GraphDirectorConsole {...props} />); click('打开导演总控台');
  await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
  click('读取选中导演节点原文档'); await screen.findByLabelText('子导演职责');
  fireEvent.change(screen.getByLabelText('子导演职责'), { target: { value: 'Opening' } });
  fireEvent.click(screen.getByRole('checkbox', { name: '1 · Scene A' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对职责与场景，同意创建一个新子导演草稿' }));
  return { props, view, client, insert, pending };
}
async function created(f: Awaited<ReturnType<typeof fixture>>) {
  click('创建所选场景子导演'); await screen.findByText(/已创建 Opening/);
  await waitFor(() => expect(f.pending).toHaveBeenLastCalledWith(false));
  expect((screen.getByRole('button', { name: verifyLabel }) as HTMLButtonElement).disabled).toBe(false);
}
async function verified() {
  click(verifyLabel); await screen.findByRole('checkbox', { name: consentLabel });
  expect((screen.getByRole('button', { name: addLabel }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByRole('checkbox', { name: consentLabel }));
}

it('rereads both original owners, previews the exact pin, and inserts once only after explicit consent without save or inherited approval', async () => {
  const f = await fixture(); await created(f);
  expect(f.client.export.mock.calls.map(([id]) => id)).toEqual(['parent']); expect(f.insert).not.toHaveBeenCalled();
  expect(screen.getByDisplayValue('Parent')).toBeTruthy();
  await verified(); expect(f.client.export.mock.calls.map(([id]) => id)).toEqual(['parent', 'parent', 'child']);
  expect(screen.getByText(/核对子导演绑定：child · v1/).textContent).toContain(childPin.digest);
  const apply = retained(addLabel); act(() => { apply(); apply(); });
  expect(f.insert).toHaveBeenCalledTimes(1); expect(f.insert).toHaveBeenCalledWith(childPin, f.props.canvasHandoff!.scope);
  expect(f.client.deriveDirectorScope).toHaveBeenCalledTimes(1); expect(f.client.create).not.toHaveBeenCalled(); expect(f.client.update).not.toHaveBeenCalled();
  expect(screen.queryByRole('button', { name: '将此审核草稿添加到画布' })).toBeNull();
});
it.each(['source-version', 'source-digest', 'source-content', 'child-version', 'child-status', 'child-content', 'child-source', 'child-digest'])(
  'rejects a changed %s from the original owner without replacing either document', async failure => {
    const f = await fixture(); await created(f);
    f.client.export.mockImplementation(async id => {
      const row = exported(id === source.id ? source : child());
      if (id === source.id) {
        if (failure === 'source-version') row.document.version++;
        if (failure === 'source-digest') row.document_digest = 'd'.repeat(64);
        if (failure === 'source-content') row.document.title = 'Changed';
      } else {
        if (failure === 'child-version') row.document.version++;
        if (failure === 'child-status') row.document.status = 'APPROVED';
        if (failure === 'child-content') row.document.title = 'Changed';
        if (failure === 'child-source') row.document.source_documents = {};
        if (failure === 'child-digest') row.document_digest = 'bad';
      }
      return row;
    });
    click(verifyLabel); await waitFor(() => expect((screen.getByRole('button', { name: verifyLabel }) as HTMLButtonElement).disabled).toBe(false));
    expect(screen.queryByRole('checkbox', { name: consentLabel })).toBeNull(); expect(f.insert).not.toHaveBeenCalled();
    expect(screen.getByDisplayValue('Parent')).toBeTruthy(); expect(f.client.update).not.toHaveBeenCalled();
    if (failure.startsWith('source-')) expect(f.client.export).toHaveBeenCalledTimes(2);
  });
it.each(['target', 'selection', 'permission', 'busy', 'available', 'identity'])(
  'retires verified consent across %s ABA and refuses retained apply', async transition => {
    const f = await fixture(); await created(f); await verified(); const apply = retained(addLabel);
    const changed = transition === 'target' ? { canvasHandoff: { ...f.props.canvasHandoff!, scope: {}, verificationScope: {} } }
      : transition === 'selection' ? { selectionKey: 'other' } : transition === 'permission' ? { canMutate: false }
      : transition === 'busy' ? { busy: true } : transition === 'available' ? { canvasHandoff: { ...f.props.canvasHandoff!, available: false } }
      : { isCurrent: () => false };
    f.view.rerender(<GraphDirectorConsole {...f.props} {...changed} />); f.view.rerender(<GraphDirectorConsole {...f.props} />);
    act(() => apply()); expect(f.insert).not.toHaveBeenCalled(); expect(screen.queryByRole('checkbox', { name: consentLabel })).toBeNull();
  });
it.each(['edit', 'choice', 'ime'] as const)('rejects retained verify and apply after synchronous source %s', async transition => {
  const f = await fixture(); await created(f); await verified(); const apply = retained(addLabel), verify = retained(verifyLabel);
  act(() => {
    if (transition === 'edit') fireEvent.change(screen.getByLabelText('文档标题'), { target: { value: 'Authored' } });
    else if (transition === 'choice') fireEvent.change(screen.getByLabelText('总控台原导演文档'), { target: { value: '' } });
    else { fireEvent.compositionStart(screen.getByLabelText('文档标题')); fireEvent.compositionEnd(screen.getByLabelText('文档标题')); }
    verify(); apply();
  });
  expect(f.client.export).toHaveBeenCalledTimes(3); expect(f.insert).not.toHaveBeenCalled();
});
it.each(['parent', 'child'] as const)('ignores a late %s read after target ABA and does not continue its request chain', async phase => {
  const f = await fixture(); await created(f); let finish!: (value: ReturnType<typeof exported>) => void;
  f.client.export.mockImplementation(id => id === phase ? new Promise(resolve => { finish = resolve; }) : Promise.resolve(exported(source)));
  click(verifyLabel); await waitFor(() => expect(finish).toBeTruthy());
  f.view.rerender(<GraphDirectorConsole {...f.props} canvasHandoff={{ ...f.props.canvasHandoff!, verificationScope: {} }} />);
  f.view.rerender(<GraphDirectorConsole {...f.props} />);
  await act(async () => finish(exported(phase === 'parent' ? source : child())));
  expect(screen.queryByRole('checkbox', { name: consentLabel })).toBeNull(); expect(f.insert).not.toHaveBeenCalled();
  expect(f.client.export).toHaveBeenCalledTimes(phase === 'parent' ? 2 : 3);
});
it('consumes a capacity-rejected insertion and retains the child; a new read and consent are required to retry', async () => {
  const f = await fixture(); await created(f); await verified(); f.insert.mockReturnValue(false);
  const apply = retained(addLabel); act(() => { apply(); apply(); });
  expect(f.insert).toHaveBeenCalledTimes(1); expect(screen.getByText(/子导演原文档保留/)).toBeTruthy();
  f.insert.mockReturnValue(true); await verified(); click(addLabel); expect(f.insert).toHaveBeenCalledTimes(2);
  expect(f.client.deriveDirectorScope).toHaveBeenCalledTimes(1); expect(f.client.export).toHaveBeenCalledTimes(5);
});
it('keeps UNKNOWN creation blocked without a placement receipt or automatic retry', async () => {
  const f = await fixture(); f.client.deriveDirectorScope.mockRejectedValue(new Error('lost response'));
  const create = retained('创建所选场景子导演'); act(() => { create(); create(); }); await screen.findByText(/创建结果未确认/);
  act(() => create()); expect(f.client.deriveDirectorScope).toHaveBeenCalledTimes(1);
  expect(screen.queryByRole('button', { name: verifyLabel })).toBeNull(); expect(f.insert).not.toHaveBeenCalled();
});
