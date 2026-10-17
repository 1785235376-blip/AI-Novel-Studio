// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useCallback, useState, type ComponentProps } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditor } from './useStudioGraphEditor';
import type { useStudioGraphEditorController } from './useStudioGraphEditorController';
import type { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { StudioClient } from './studioClient';
import type { StudioGraphSaveInput } from './studioGraphTypes';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import rawCatalog from './fixtures/productionGraph.catalog.json';
import { newDocument, type CreativeDocument } from './types';
const probe = vi.hoisted(() => ({ review: undefined as ComponentProps<typeof GraphDirectorProposalReview> | undefined }));
vi.mock('./GraphDirectorProposalReview', () => ({ hasDirectorProposalReview: () => true,
  GraphDirectorProposalReview: (props: ComponentProps<typeof GraphDirectorProposalReview>) => { probe.review = props; return null; } }));
// Keep the original state/owner wiring; only replace the large visual graph skin.
vi.mock('./studioGraphEditorView', () => ({ studioGraphEditorView: (controller: ReturnType<typeof useStudioGraphEditorController>) => ({
  content: <section><button onClick={() => void controller.open('image-graph')}>Open graph fixture</button>
    <button onClick={() => void controller.save()}>Save graph fixture</button>
    <button onClick={() => controller.travel(false)}>Undo graph fixture</button>
    <output aria-label="graph nodes">{JSON.stringify(controller.draft.nodes)}</output></section>, inspector: null,
}) }));
afterEach(() => { cleanup(); probe.review = undefined; });
it('wires reviewed Creative DRAFT through original export/read, real editor/controller insertion, and explicit Graph Save', async () => {
  const pin = { id: 'reviewed', version: 2, digest: 'b'.repeat(64) };
  const doc: CreativeDocument = { ...newDocument('DIRECTOR'), id: pin.id, version: pin.version, title: 'Reviewed', status: 'DRAFT',
    actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, source_independent: true };
  const record = imageGraphRecord(); record.definition.nodes = []; record.definition.edges = []; record.reference_states = [];
  const graphs = { catalog: vi.fn().mockResolvedValue(rawCatalog), imageCatalog: vi.fn().mockResolvedValue(rawCatalog),
    list: vi.fn().mockResolvedValue({ items: [] }), get: vi.fn().mockResolvedValue(record),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => ({ ...record, version: 2, definition: input.definition })) };
  const creative = { capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }),
    export: vi.fn().mockResolvedValue({ document: doc, document_digest: pin.digest }), create: vi.fn(), update: vi.fn() } as unknown as GraphDirectorSource;
  const client = { graphs } as unknown as StudioClient;
  const current = () => true;
  function Mounted() {
    const [busy, setBusy] = useState(false);
    const read = useCallback(async <T,>(work: () => Promise<T>) => { setBusy(true); try { return await work(); } finally { setBusy(false); } }, []);
    return useStudioGraphEditor({ active: true, denied: false, identity: 'actor:scope', client, directorSource: creative,
      canMutate: true, canReview: true, busy, externalDirty: false, isCurrent: current, read, mutate: read }).content;
  }
  render(<Mounted />);
  await waitFor(() => expect(graphs.catalog).toHaveBeenCalledTimes(1));
  fireEvent.click(screen.getByRole('button', { name: 'Open graph fixture' })); await waitFor(() => expect(graphs.get).toHaveBeenCalled());
  fireEvent.click(screen.getByRole('button', { name: '打开导演总控台' })); await waitFor(() => expect(probe.review).toBeTruthy());
  act(() => probe.review!.onDocument(doc));
  const add = () => screen.getByRole('button', { name: '将此审核草稿添加到画布' }) as HTMLButtonElement;
  expect(add().disabled).toBe(true); expect(graphs.save).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: '核对导演原文档版本' })); await waitFor(() => expect(add().disabled).toBe(false));
  fireEvent.click(add());
  expect(JSON.parse(screen.getByLabelText('graph nodes').textContent!)[0].parameters).toEqual({ document_snapshot: pin });
  expect(graphs.save).not.toHaveBeenCalled(); expect(creative.create).not.toHaveBeenCalled(); expect(creative.update).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Undo graph fixture' }));
  expect(JSON.parse(screen.getByLabelText('graph nodes').textContent!)).toEqual([]); expect(add().disabled).toBe(true);
  fireEvent.click(screen.getByRole('button', { name: '核对导演原文档版本' })); await waitFor(() => expect(add().disabled).toBe(false));
  fireEvent.click(add()); expect(JSON.parse(screen.getByLabelText('graph nodes').textContent!)).toHaveLength(1);
  expect(creative.export).toHaveBeenCalledTimes(2); expect(creative.create).not.toHaveBeenCalled();
  fireEvent.click(screen.getByRole('button', { name: 'Save graph fixture' })); await waitFor(() => expect(graphs.save).toHaveBeenCalledTimes(1));
  expect(graphs.save.mock.calls[0][1].expected_version).toBe(1);
});
