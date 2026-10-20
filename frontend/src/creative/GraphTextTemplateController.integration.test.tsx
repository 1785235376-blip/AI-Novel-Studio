// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphTextTemplateTools } from './GraphTextTemplateTools';
import { useStudioGraphEditorController, type StudioGraphEditorProps } from './useStudioGraphEditorController';
import { blankGraph } from './graphDraft';
import { exportTextGraphTemplate } from './graphTextTemplates';
import { modelCatalog } from './studioGraphModel.testFixtures';
import type { StudioGraphCreateInput } from './studioGraphTypes';
afterEach(cleanup);
it('imports through original draft history and explicit create without runs or implicit save', async () => {
 const create = vi.fn(async (input: StudioGraphCreateInput) => ({ project_id: 'p', scope: { mode: 'local', novel_id: 'p' }, id: 'saved', version: 1, definition: input.definition, definition_digest: 'a'.repeat(64), execution_digest: 'b'.repeat(64), reference_states: [], can_edit: true, created_at: '', updated_at: '' }));
 const createRun = vi.fn(), initial: StudioGraphEditorProps = { active: true, denied: false, identity: 'p:actor', canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent: () => true, read: f => f(), mutate: f => f(), client: { graphs: { catalog: vi.fn().mockResolvedValue(modelCatalog()), list: vi.fn().mockResolvedValue({ items: [] }), create, createRun } } as any };
 function Mounted() { const c = useStudioGraphEditorController(initial); return <>{c.catalog && <GraphTextTemplateTools definition={c.draft} catalog={c.catalog} owner={c.insertionScope} disabled={!c.editable} isCurrent={c.current} onApply={(d, selected) => { c.change(d); c.setSelected(selected); }} />}<output aria-label="node count">{c.draft.nodes.length}</output><output aria-label="presentation">{JSON.stringify(c.draft.presentation || {})}</output><button onClick={() => c.travel(false)}>Original undo</button><button onClick={() => c.travel(true)}>Original redo</button><button onClick={() => void c.save()}>Original save</button></>; }
 render(<Mounted />); await waitFor(() => expect((screen.getByLabelText('导入文字图模板 JSON') as HTMLInputElement).disabled).toBe(false));
 const source = blankGraph(); source.nodes = [{ id: 'Input', definition_id: 'text_input', definition_version: 1, enabled: true, parameters: { text: 'Reuse original owners' }, position: { x: 0, y: 0 } }]; source.presentation = { groups: [{ id: 'SourceGroup', name: '作者分组', node_ids: ['Input'] }], notes: [{ id: 'SourceNote', text: '保留便笺 🐈\n第二行', position: { x: 0, y: 200 } }] }; const raw = exportTextGraphTemplate(source);
 fireEvent.change(screen.getByLabelText('导入文字图模板 JSON'), { target: { files: [{ size: raw.length, text: async () => raw }] } }); await screen.findByText(/将新增 1 个节点/); fireEvent.click(screen.getByLabelText('确认仅把模板追加到当前本地草稿')); fireEvent.click(screen.getByText('明确追加模板节点'));
 expect(screen.getByLabelText('node count').textContent).toBe('1'); const presentation = JSON.parse(screen.getByLabelText('presentation').textContent!); expect(presentation.groups[0].id).not.toBe('SourceGroup'); expect(presentation.notes[0].text).toBe(source.presentation.notes![0].text);
 expect(create).not.toHaveBeenCalled(); expect(createRun).not.toHaveBeenCalled(); fireEvent.click(screen.getByText('Original undo')); expect(screen.getByLabelText('node count').textContent).toBe('0'); expect(screen.getByLabelText('presentation').textContent).toBe('{}'); fireEvent.click(screen.getByText('Original redo')); expect(screen.getByLabelText('node count').textContent).toBe('1'); expect(JSON.parse(screen.getByLabelText('presentation').textContent!)).toEqual(presentation);
 await act(async () => fireEvent.click(screen.getByText('Original save'))); expect(create).toHaveBeenCalledTimes(1); expect(create.mock.calls[0][0].definition.nodes[0].parameters.text).toBe('Reuse original owners'); expect(create.mock.calls[0][0].definition.presentation).toEqual(presentation); expect(createRun).not.toHaveBeenCalled();
});
