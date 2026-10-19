// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { useCallback, useState } from 'react';
import { afterEach, expect, it, vi } from 'vitest';
import { useStudioGraphEditor } from './useStudioGraphEditor';
import type { useStudioGraphEditorController } from './useStudioGraphEditorController';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import type { StudioClient } from './studioClient';
import type { StudioGraphSaveInput } from './studioGraphTypes';
import { imageGraphRecord } from './studioImageGraph.testFixtures';
import rawCatalog from './fixtures/productionGraph.catalog.json';
import { newDocument, type CreativeDocument } from './types';

// The real graph controller owns insertion, change/history and Save; only omit its large visual skin.
vi.mock('./studioGraphEditorView', () => ({ studioGraphEditorView: (controller: ReturnType<typeof useStudioGraphEditorController>) => ({
  content: <section><button onClick={() => void controller.open('image-graph')}>Open graph fixture</button>
    <button onClick={() => void controller.save()}>Save graph fixture</button>
    <button onClick={() => controller.travel(false)}>Undo graph fixture</button>
    <button onClick={() => controller.travel(true)}>Redo graph fixture</button>
    <output aria-label="graph definition">{JSON.stringify(controller.draft)}</output></section>, inspector: null,
}) }));
afterEach(cleanup);
it('creates a source-scoped DRAFT through the owner, then inserts/undoes/redoes/saves/reopens via the actual controller', async () => {
  const parent: CreativeDocument = { ...newDocument('DIRECTOR'), id: 'parent', version: 1, title: 'Parent', status: 'DRAFT',
    actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, source_independent: true,
    scenes: [{ id: 'a', sequence: 1, heading: 'Scene A', source_chapter_id: null, time: '', location: '', characters: [], action: 'A', dialogue: [], emotion: '', director_notes: [] }] };
  const parentPin = { id: parent.id, version: 1, digest: 'a'.repeat(64) }, childPin = { id: 'child', version: 1, digest: 'c'.repeat(64) };
  const child: CreativeDocument & { provenance: Record<string, unknown> } = { ...parent, id: 'child', title: 'Opening', source_independent: false,
    source_documents: { parent: { version: 1, digest: parentPin.digest } },
    provenance: { method: 'STRUCTURED_DERIVATION', model_called: false, source_document_id: 'parent', source_version: 1, input_digest: parentPin.digest,
      parameters: { rule_version: 'creative-director-scene-scope-v1', responsibility: 'Opening', scene_ids: ['a'], copied_approval: false, execution_authority: false } } };
  let record = imageGraphRecord(); record.definition.nodes = []; record.definition.edges = []; record.reference_states = [];
  const graphs = { catalog: vi.fn(async () => rawCatalog), imageCatalog: vi.fn(async () => rawCatalog),
    list: vi.fn(async () => ({ items: [] })), get: vi.fn(async () => structuredClone(record)),
    save: vi.fn(async (_id: string, input: StudioGraphSaveInput) => { record = { ...record, version: record.version + 1, definition: structuredClone(input.definition) }; return structuredClone(record); }) };
  const creative = { capabilities: vi.fn(async () => ({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] })),
    list: vi.fn(async () => ({ items: [parent] })), history: vi.fn(), derive: vi.fn(), create: vi.fn(), update: vi.fn(),
    deriveDirectorScope: vi.fn(async () => child),
    export: vi.fn(async (id: string) => ({ document: structuredClone(id === 'parent' ? parent : child), document_digest: id === 'parent' ? parentPin.digest : childPin.digest })) };
  const current = () => true, client = { graphs } as unknown as StudioClient;
  function Mounted() {
    const [busy, setBusy] = useState(false);
    const read = useCallback(async <T,>(work: () => Promise<T>) => work(), []);
    const mutate = useCallback(async <T,>(work: () => Promise<T>) => { setBusy(true); try { return await work(); } finally { setBusy(false); } }, []);
    return useStudioGraphEditor({ active: true, denied: false, identity: 'actor:scope', client,
      directorSource: creative as unknown as GraphDirectorSource, canMutate: true, canReview: true, busy, externalDirty: false, isCurrent: current, read, mutate }).content;
  }
  const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
  const definition = () => JSON.parse(screen.getByLabelText('graph definition').textContent!);
  render(<Mounted />); await waitFor(() => expect(graphs.catalog).toHaveBeenCalledTimes(1));
  click('Open graph fixture'); await waitFor(() => expect(graphs.get).toHaveBeenCalledTimes(1));
  click('打开导演总控台'); await waitFor(() => expect((screen.getByRole('button', { name: '读取导演原文档目录' }) as HTMLButtonElement).disabled).toBe(false));
  click('读取导演原文档目录'); await screen.findByRole('option', { name: 'Parent · v1' });
  fireEvent.change(screen.getByLabelText('总控台原导演文档'), { target: { value: 'parent' } }); click('读取所选导演原文档');
  await screen.findByLabelText('子导演职责'); fireEvent.change(screen.getByLabelText('子导演职责'), { target: { value: 'Opening' } });
  fireEvent.click(screen.getByRole('checkbox', { name: '1 · Scene A' }));
  fireEvent.click(screen.getByRole('checkbox', { name: '已核对职责与场景，同意创建一个新子导演草稿' }));
  click('创建所选场景子导演'); await screen.findByText(/已创建 Opening/);
  const verify = await screen.findByRole('button', { name: '重读并核对子导演与来源' });
  await waitFor(() => expect((verify as HTMLButtonElement).disabled).toBe(false)); fireEvent.click(verify);
  fireEvent.click(await screen.findByRole('checkbox', { name: '已核对子导演版本、来源与当前画布，确认只添加一个导演节点' }));
  click('将子导演添加到当前画布草稿'); expect(definition().nodes).toHaveLength(1);
  expect(definition().nodes[0]).toMatchObject({ definition_id: 'director_plan', parameters: { document_snapshot: childPin } });
  expect(definition().edges).toEqual([]); expect(graphs.save).not.toHaveBeenCalled();
  click('Undo graph fixture'); expect(definition().nodes).toEqual([]);
  click('Redo graph fixture'); expect(definition().nodes).toHaveLength(1);
  click('Save graph fixture'); await waitFor(() => expect(graphs.save).toHaveBeenCalledTimes(1));
  expect(graphs.save.mock.calls[0][1].expected_version).toBe(1);
  click('Open graph fixture'); await waitFor(() => expect(graphs.get).toHaveBeenCalledTimes(2));
  expect(definition().nodes[0].parameters).toEqual({ document_snapshot: childPin }); expect(definition().edges).toEqual([]);
  expect(creative.deriveDirectorScope).toHaveBeenCalledTimes(1); expect(creative.create).not.toHaveBeenCalled(); expect(creative.update).not.toHaveBeenCalled();
});
