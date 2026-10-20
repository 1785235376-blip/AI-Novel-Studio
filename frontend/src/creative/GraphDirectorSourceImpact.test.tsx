// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphDirectorSourceImpact } from './GraphDirectorSourceImpact';
import { newDocument, newScene, type CreativeDocument } from './types';
import type { GraphDirectorSource } from './GraphDirectorConsole';
import { directorContentChanges, directorDownstream } from './directorSourceImpact';
import type { StudioGraphDefinition } from './studioGraphTypes';
const pin = { id: 'director', version: 1, digest: 'a'.repeat(64) };
const old: CreativeDocument = { ...newDocument('DIRECTOR'), id: pin.id, title: '旧标题', version: 1, status: 'DRAFT', created_at: '', updated_at: '', actor_id: '', source_evidence: {}, scenes: [{ ...newScene(1), id: 'scene', action: '停顿' }] };
const current = { ...old, version: 2, title: '新标题', scenes: [{ ...old.scenes[0], action: '转身' }] };
const graph: StudioGraphDefinition = { schema_version: 2, title: 'graph', viewport: { x: 0, y: 0, zoom: 1 }, nodes: [
  { id: 'director-node', definition_id: 'director_plan', definition_version: 1, enabled: true, position: { x: 0, y: 0 }, parameters: { document_snapshot: pin } },
  { id: 'board-node', definition_id: 'storyboard_plan', definition_version: 1, enabled: false, position: { x: 0, y: 0 }, parameters: { document_snapshot: { ...pin, id: 'board' } } }], edges: [{ id: 'edge', source_node_id: 'director-node', source_port: 'plan', target_node_id: 'board-node', target_port: 'plan' }] };
function setup() {
  const client: GraphDirectorSource = { capabilities: vi.fn(), create: vi.fn(), update: vi.fn(), derive: vi.fn(),
    export: vi.fn().mockResolvedValue({ document: current, document_digest: 'b'.repeat(64) }),
    history: vi.fn().mockResolvedValue({ document_id: pin.id, current_version: 2, items: [old, current], snapshot_digests: [pin, { version: 2, digest: 'b'.repeat(64) }] }),
    list: vi.fn().mockResolvedValue({ items: [{ ...current, id: 'board-new', title: '可读分镜', mode: 'STORYBOARD', source_documents: { [pin.id]: { version: 2, digest: 'b'.repeat(64) } } }] }) };
  return { client, pin, graph, selectedNodeId: 'director-node', active: true, busy: false, isCurrent: () => true, read: async <T,>(work: () => Promise<T>) => work() };
}
const inspect = () => fireEvent.click(screen.getByRole('button', { name: '读取／刷新导演来源影响' }));
afterEach(cleanup);
describe('read-only exact director source impact', () => {
  it('explicitly reads exact history and current source, structural downstream pins and readable references without writes', async () => {
    const props = setup(); render(<GraphDirectorSourceImpact {...props} />);
    expect(props.client.export).not.toHaveBeenCalled(); inspect();
    await screen.findByText(/历史快照版本与原 Owner 摘要匹配/);
    expect(screen.getByText('绑定版本："旧标题"')).toBeTruthy(); expect(screen.getByText('当前版本："转身"')).toBeTruthy();
    expect(screen.getByText(/board-node · storyboard_plan/)).toBeTruthy(); expect(screen.getByText(/可读分镜 · board-new/)).toBeTruthy();
    expect(screen.getByText(/零条不代表/)).toBeTruthy(); expect(props.client.create).not.toHaveBeenCalled(); expect(props.client.update).not.toHaveBeenCalled(); expect(props.client.derive).not.toHaveBeenCalled();
    expect(graph.nodes[0].parameters.document_snapshot).toEqual(pin);
  });
  it.each(['missing', 'mismatch', 'unavailable'])('uses metadata only for %s historical proof', async kind => {
    const props = setup();
    if (kind === 'unavailable') vi.mocked(props.client.history).mockRejectedValue(new ApiError({ status: 409, code: 'STALE', message: 'stale' }));
    else vi.mocked(props.client.history).mockResolvedValue({ document_id: pin.id, current_version: 2, items: [old, current], ...(kind === 'mismatch' ? { snapshot_digests: [{ version: 1, digest: 'c'.repeat(64) }] } : {}) });
    render(<GraphDirectorSourceImpact {...props} />); inspect(); await screen.findByText(/仅元数据比较/);
    expect(screen.queryByText('绑定版本："旧标题"')).toBeNull();
  });
  it.each(['duplicate-receipt', 'duplicate-item', 'null-scene', 'null-note', 'null-history', 'bad-items', 'bad-receipts'])('falls back to metadata for %s history', async kind => {
    const props = setup();
    const history = { document_id: pin.id, current_version: 2, items: [old, current], snapshot_digests: [pin, { version: 2, digest: 'b'.repeat(64) }] };
    const bad: unknown = kind === 'duplicate-receipt' ? { ...history, snapshot_digests: [...history.snapshot_digests, { version: 1, digest: 'c'.repeat(64) }] }
      : kind === 'duplicate-item' ? { ...history, items: [...history.items, old] }
      : kind === 'null-scene' ? { ...history, items: [{ ...old, scenes: [null] }, current] }
      : kind === 'null-note' ? { ...history, items: [{ ...old, director_notes: [null] }, current] }
      : kind === 'null-history' ? null : kind === 'bad-items' ? { ...history, items: {} } : { ...history, snapshot_digests: [null] };
    vi.mocked(props.client.history).mockResolvedValue(bad as Awaited<ReturnType<GraphDirectorSource['history']>>);
    render(<GraphDirectorSourceImpact {...props} />); inspect(); await screen.findByText(/仅元数据比较/);
    expect(screen.queryByText('绑定版本："旧标题"')).toBeNull();
  });
  it('clears previous results on refresh failure and never reads related content after denial', async () => {
    const props = setup(); render(<GraphDirectorSourceImpact {...props} />); inspect(); await screen.findByText(/历史快照版本/);
    vi.mocked(props.client.history).mockRejectedValue(new ApiError({ status: 403, code: 'DENIED', message: '无权读取' }));
    inspect(); await screen.findByText('无权读取'); expect(screen.queryByText('绑定版本："旧标题"')).toBeNull(); expect(props.client.list).toHaveBeenCalledTimes(1);
  });
  it('rejects late A→inactive→A reads and client replacement', async () => {
    const props = setup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
    vi.mocked(props.client.export).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorSourceImpact {...props} />); inspect(); view.rerender(<GraphDirectorSourceImpact {...props} active={false} />); view.rerender(<GraphDirectorSourceImpact {...props} />);
    await act(async () => resolve({ document: current, document_digest: 'b'.repeat(64), format: '', boundary: '' }));
    expect(props.client.history).not.toHaveBeenCalled(); expect(screen.queryByText(/历史快照版本/)).toBeNull();
    inspect(); view.rerender(<GraphDirectorSourceImpact {...props} client={setup().client} />);
    await act(async () => resolve({ document: current, document_digest: 'b'.repeat(64), format: '', boundary: '' }));
    expect(screen.queryByText(/历史快照版本/)).toBeNull();
  });
  it('invalidates previews when graph topology changes and bounds rendered differences', async () => {
    const props = setup(); const many = { ...current, scenes: Array.from({ length: 70 }, (_, i) => ({ ...old.scenes[0], id: `scene-${i}` })) };
    vi.mocked(props.client.export).mockResolvedValue({ document: many, document_digest: 'b'.repeat(64), format: '', boundary: '' });
    const view = render(<GraphDirectorSourceImpact {...props} />); inspect(); await screen.findByText(/历史快照版本/);
    expect(screen.getAllByText(/绑定版本：/)).toHaveLength(40);
    view.rerender(<GraphDirectorSourceImpact {...props} graph={{ ...graph, edges: [] }} />);
    await waitFor(() => expect(screen.queryByText(/历史快照版本/)).toBeNull());
  });
  it.each(['pin', 'node', 'graph'])('rejects late %s A→B→A preview responses', async kind => {
    const props = setup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
    vi.mocked(props.client.export).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorSourceImpact {...props} />); inspect();
    const changed = kind === 'pin' ? { pin: { ...pin, id: 'other' } } : kind === 'node' ? { selectedNodeId: 'other-node' } : { graph: { ...graph, edges: [] } };
    view.rerender(<GraphDirectorSourceImpact {...props} {...changed} />); view.rerender(<GraphDirectorSourceImpact {...props} />);
    await act(async () => resolve({ document: current, document_digest: 'b'.repeat(64), format: '', boundary: '' }));
    expect(props.client.history).not.toHaveBeenCalled(); expect(screen.queryByText(/历史快照版本/)).toBeNull();
  });
  it('escapes field text and labels truncated previews without expanding unbounded content', async () => {
    const props = setup(); const changed = { ...current, title: '<img src=x onerror=alert(1)>' + '长'.repeat(2200) };
    vi.mocked(props.client.export).mockResolvedValue({ document: changed, document_digest: 'b'.repeat(64), format: '', boundary: '' });
    render(<GraphDirectorSourceImpact {...props} />); inspect(); await screen.findByText(/字段预览已截断/);
    expect(screen.getByText(/当前版本：.*<img src=x/).textContent!.length).toBeLessThan(2050);
    expect(screen.queryByRole('img')).toBeNull();
  });
  it('compares stable field values, preserves scene identity and terminates cycles', () => {
    expect(directorContentChanges(old, { ...old, scenes: [{ ...old.scenes[0] }] })).toEqual([]);
    expect(directorContentChanges(old, current).map(row => row.field)).toEqual(['title', 'scenes/scene/action']);
    expect(directorDownstream({ ...graph, edges: [...graph.edges, { ...graph.edges[0], id: 'cycle', source_node_id: 'board-node', target_node_id: 'director-node' }] }, 'director-node').map(row => row.id)).toEqual(['board-node']);
  });
});
