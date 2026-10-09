// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import { GraphRunPanel } from './GraphRunPanel';
import { blankGraph } from './graphDraft';
import type { StudioAsset, StudioClient, StudioReference, StudioReferenceKind } from './studioClient';
import type { StudioGraphCatalog, StudioGraphRecord, StudioGraphRun, StudioGraphSaveInput } from './studioGraphTypes';
import { useStudioGraphEditor } from './useStudioGraphEditor';

const digest = 'a'.repeat(64);
const owner = { project_id: 'project', scope: { mode: 'local' as const, novel_id: 'project' } };
const perform = <T,>(work: () => Promise<T>) => work();
const isCurrent = () => true;
const asset = (id = 'source'): StudioAsset => ({ id, novel_id: 'project', branch_id: null, filename: `${id}.png`, kind: 'image', media_type: 'image/png', size: 3, sha256: digest, version: 4, created_at: '', updated_at: '', relationships: [] });
const reference = (kind: StudioReferenceKind, id: string): StudioReference => ({ kind, id, version: 2, digest, label: `${kind} ${id}`, deleted: false });
const record = (id: string): StudioGraphRecord => ({ ...owner, id, version: 1, definition_digest: digest, execution_digest: digest, can_edit: true, reference_states: [], created_at: '', updated_at: '',
  definition: { ...blankGraph(), title: `已保存图 ${id}`, nodes: [
    { id: 'source', definition_id: 'text_input', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { text: '作者文本' } },
    { id: 'target', definition_id: 'text_reference', definition_version: 1, enabled: true, position: { x: 300, y: 0 }, parameters: {} },
  ] } });
const run = (id: string): StudioGraphRun => ({ ...owner, id, graph_id: 'graph_one', graph_version: 1, version: 2, status: 'QUEUED', current_node_id: null, node_states: {}, review: null,
  cache: { hits: 0, misses: 0, mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' }, created_at: '', updated_at: '', model_called: false, external_calls: 0, applied: false, stale: false, reviewed: false,
  timeout_seconds: 3600, deadline_at: '2026-10-09T15:00:00Z' });
const catalog: StudioGraphCatalog = {
  definitions: [
    { id: 'text_input', version: 1, inputs: [], outputs: [{ id: 'text', type: 'TEXT', required: false, multiple: false }], parameters_schema: { type: 'object', additionalProperties: false, properties: { text: { type: 'string' } } }, default_parameters: { text: '' }, executable: true, model_called: false, blockers: [] },
    { id: 'text_reference', version: 1, inputs: [{ id: 'text', type: 'TEXT', required: true, multiple: false }], outputs: [{ id: 'text', type: 'TEXT', required: false, multiple: false }], parameters_schema: { type: 'object', additionalProperties: false, properties: {} }, default_parameters: {}, executable: true, model_called: false, blockers: [] },
    { id: 'asset_reference', version: 1, inputs: [], outputs: [{ id: 'asset', type: 'ASSET_REF', required: false, multiple: false }], parameters_schema: { type: 'object', additionalProperties: false, properties: {} }, default_parameters: null, executable: false, model_called: false, blockers: ['CREATIVE_GRAPH_ATOMIC_INPUT_OWNER_ADAPTER_REQUIRED'] },
  ],
  limits: { nodes: 16, edges: 40, definition_bytes: 96000, output_bytes: 64000, graphs: 25, runs: 100, history: 20, runtime_timeout_seconds: 3600, node_timeout_seconds: 5 },
  capabilities: { local_execution: true, chapter_required: false, model_execution: false, external_reference_execution: false, external_reference_detach: false, binary_cache: false, parallel_execution: false, automatic_retry: false, actor_private: true, cache_mode: 'SAME_GRAPH_VERSION_REVIEWED_LOCAL_ONLY' },
};

function graphClient() {
  return { catalog: vi.fn().mockResolvedValue(catalog), list: vi.fn().mockResolvedValue({ items: [record('graph_one'), record('graph_two')] }),
    get: vi.fn(async (id: string) => record(id)), create: vi.fn(), save: vi.fn(async (id: string, input: StudioGraphSaveInput) => ({ ...record(id), version: 2, definition: input.definition })),
    preflight: vi.fn(), runs: vi.fn().mockResolvedValue({ items: [run('run_one'), run('run_two')] }), getRun: vi.fn(async (id: string) => run(id)), createRun: vi.fn(), action: vi.fn() };
}
function GraphEditor({ client }: { client: StudioClient }) {
  const editor = useStudioGraphEditor({ active: true, denied: false, identity: 'project:author', client, canMutate: true, canReview: true, busy: false, externalDirty: false, isCurrent, read: perform, mutate: perform });
  return <>{editor.content}{editor.inspector}</>;
}

// Playwright 1.62.1 exact getByLabel prefers aria-label; its native-label
// fallback includes option descendants. Require that stable DOM contract here,
// alongside the accessible combobox name. This jsdom test is not browser proof.
function namedSelect(name: string): HTMLSelectElement {
  const select = screen.getByLabelText(name, { exact: true }) as HTMLSelectElement;
  expect(select.tagName).toBe('SELECT');
  expect(select.getAttribute('aria-label')).toBe(name);
  expect(select.labels?.[0]?.firstChild?.textContent).toBe(name);
  expect(screen.getByRole('combobox', { name })).toBe(select);
  return select;
}
function choose(name: string, value: string) {
  fireEvent.change(namedSelect(name), { target: { value } });
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('stable exact names for Studio selects with populated options', () => {
  it('documents why a Testing Library label query alone missed nested option text', () => {
    render(<label>旧关联目标<select defaultValue="one"><option value="">请选择</option><option value="one">目标甲</option><option value="two">目标乙</option></select></label>);
    const select = screen.getByLabelText('旧关联目标', { exact: true }) as HTMLSelectElement;
    expect(select.getAttribute('aria-label')).toBeNull();
    expect(select.labels?.[0]?.textContent).toBe('旧关联目标请选择目标甲目标乙');
    fireEvent.change(select, { target: { value: 'two' } });
    expect(screen.getByLabelText('旧关联目标', { exact: true })).toBe(select);
    expect(select.value).toBe('two');
  });

  it('keeps relationship, reference-kind and target names stable through selection and saving', async () => {
    const client = { references: vi.fn(async (kind: StudioReferenceKind) => ({ items: [reference(kind, 'one'), reference(kind, 'two')], read_only: true as const, content_copied: false as const })),
      relationships: vi.fn(), addRelationship: vi.fn(async () => asset()), removeRelationship: vi.fn() };
    render(<AssetRelationshipsPanel asset={asset()} client={client} canMutate canReview blocked={false} busy={false} isCurrent={isCurrent} read={perform} mutate={perform} onDirtyChange={vi.fn()} />);
    click('可选资产关联');
    await screen.findByRole('option', { name: 'ASSET one · v2' });
    expect(namedSelect('关联目标').options).toHaveLength(3);
    choose('关系类型', 'USED_IN');
    expect(namedSelect('关系类型').value).toBe('USED_IN');
    choose('引用类型', 'CHAPTER');
    await screen.findByRole('option', { name: 'CHAPTER one · v2' });
    expect(namedSelect('引用类型').value).toBe('CHAPTER');
    expect(client.references).toHaveBeenLastCalledWith('CHAPTER', expect.any(AbortSignal));
    for (const id of ['one', 'two']) {
      const value = JSON.stringify(['CHAPTER', id, 2, digest]);
      choose('关联目标', value);
      expect(namedSelect('关联目标').value).toBe(value);
    }
    click('保存关联');
    await waitFor(() => expect(client.addRelationship).toHaveBeenCalledWith('source', { expected_version: 4, type: 'USED_IN', target: { kind: 'CHAPTER', id: 'two', version: 2, digest }, reason: '' }));
    await waitFor(() => expect(namedSelect('关联目标').value).toBe(''));
    expect(namedSelect('关系类型').value).toBe('REFERENCES');
    expect(namedSelect('引用类型').value).toBe('ASSET');
  });

  it('keeps saved-graph, node, asset and port names stable while editing the real graph hook', async () => {
    const graphs = graphClient(), assets = vi.fn().mockResolvedValue({ items: [asset('asset_one'), asset('asset_two')] });
    render(<GraphEditor client={{ graphs, assets } as unknown as StudioClient} />);
    await screen.findByRole('option', { name: '已保存图 graph_one · v1' });
    for (const id of ['graph_one', 'graph_two']) {
      choose('已保存创作图', id);
      await waitFor(() => expect(namedSelect('已保存创作图').value).toBe(id));
      expect((screen.getByLabelText('创作图标题') as HTMLInputElement).value).toBe(`已保存图 ${id}`);
      expect(graphs.get).toHaveBeenLastCalledWith(id);
    }
    choose('节点类型', 'asset_reference');
    await screen.findByRole('option', { name: 'asset_one.png · image · v4' });
    expect(namedSelect('节点类型').value).toBe('asset_reference');
    for (const id of ['asset_one', 'asset_two']) {
      choose('原资产', id);
      expect(namedSelect('原资产').value).toBe(id);
    }
    expect(assets).toHaveBeenCalledTimes(1);
    choose('节点类型', 'text_reference');
    expect(namedSelect('节点类型').value).toBe('text_reference');
    const output = JSON.stringify(['source', 'text']), input = JSON.stringify(['target', 'text']);
    choose('起始输出端口', output);
    choose('目标输入端口', input);
    expect(namedSelect('起始输出端口').value).toBe(output);
    expect(namedSelect('目标输入端口').value).toBe(input);
    click('连接所选端口');
    expect(within(screen.getByRole('region', { name: '图连接列表' })).getByText('source.text → target.text')).toBeTruthy();
    expect(namedSelect('起始输出端口').value).toBe('');
    expect(namedSelect('目标输入端口').value).toBe('');
    click('保存创作图');
    await waitFor(() => expect(graphs.save).toHaveBeenCalledWith('graph_two', { expected_version: 1, definition: expect.objectContaining({ edges: [{ id: expect.any(String), source_node_id: 'source', source_port: 'text', target_node_id: 'target', target_port: 'text' }] }) }));
    await screen.findByText('创作图已保存 · v2。没有自动创建运行。');
    expect(namedSelect('已保存创作图').value).toBe('graph_two');
    expect(graphs.createRun).not.toHaveBeenCalled();
  });

  it('keeps the saved-run name stable after loading and selecting different records', async () => {
    const client = graphClient();
    render(<GraphRunPanel client={client} graph={record('graph_one')} targetNodeIds={[]} dirty={false} busy={false} canMutate canReview isCurrent={isCurrent} read={perform} mutate={perform} />);
    click('读取运行记录');
    await screen.findByRole('option', { name: 'run_one · 待执行 · v2' });
    expect(namedSelect('已保存运行').options).toHaveLength(3);
    for (const id of ['run_one', 'run_two']) {
      choose('已保存运行', id);
      await waitFor(() => expect(namedSelect('已保存运行').value).toBe(id));
      expect(client.getRun).toHaveBeenLastCalledWith(id);
      expect(within(screen.getByRole('region', { name: '当前创作图运行' })).getByText(`运行 ${id} · v2 · 图 v1`)).toBeTruthy();
    }
    expect(client.action).not.toHaveBeenCalled();
    expect(client.createRun).not.toHaveBeenCalled();
  });
});
