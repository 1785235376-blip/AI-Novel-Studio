// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError, type AssetRelationship } from '../api';
import { AssetRelationshipsPanel } from './AssetRelationshipsPanel';
import type { StudioAsset, StudioReference, StudioReferenceKind, StudioRelationshipGraph } from './studioClient';

const digest = 'a'.repeat(64);
const source = (): StudioAsset => ({ id: 'source', novel_id: 'project', branch_id: null, filename: 'source.png', kind: 'image', media_type: 'image/png', size: 3, sha256: digest, version: 4, created_at: '', updated_at: '', relationships: [] });
const reference = (kind: StudioReferenceKind = 'ASSET', patch: Partial<StudioReference> = {}): StudioReference => ({ kind, id: 'target', version: 2, digest, label: '可访问目标', deleted: false, ...patch });
const link = (patch: Partial<Extract<AssetRelationship, { state: 'CURRENT' | 'STALE' | 'DELETED' }>> = {}): AssetRelationship => ({ id: 'link', type: 'REFERENCES', state: 'CURRENT', target: reference(), expected: { kind: 'ASSET', id: 'target', version: 2, digest }, reason: '构图参考', created_by: 'author', created_at: '', semantics: 'DECLARED_LINK_NOT_RIGHTS_GRANT_OR_EXECUTION', ...patch });
function setup(options: { asset?: StudioAsset; canMutate?: boolean; canReview?: boolean; blocked?: boolean; current?: () => boolean } = {}) {
  const client = { references: vi.fn(async (kind: StudioReferenceKind) => ({ items: [reference(kind)], read_only: true as const, content_copied: false as const })), relationships: vi.fn<() => Promise<StudioRelationshipGraph>>(), addRelationship: vi.fn(async () => source()), removeRelationship: vi.fn(async () => source()) };
  const onDirtyChange = vi.fn(), mutate = vi.fn(async (operation: () => Promise<StudioAsset>) => operation());
  const props = { asset: options.asset || source(), client, canMutate: options.canMutate ?? true, canReview: options.canReview ?? false, blocked: options.blocked ?? false, busy: false, isCurrent: options.current || (() => true), read: async <T,>(operation: () => Promise<T>) => operation(), mutate, onDirtyChange };
  const result = render(<AssetRelationshipsPanel {...props} />);
  return { ...result, props, client, onDirtyChange, mutate };
}
async function open() { fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); await screen.findByRole('option', { name: '可访问目标 · v2' }); }
function choose() { const option = screen.getByRole('option', { name: '可访问目标 · v2' }) as HTMLOptionElement; fireEvent.change(screen.getByLabelText('关联目标'), { target: { value: option.value } }); }
afterEach(() => { cleanup(); vi.restoreAllMocks(); });

describe('optional descriptive asset relationships', () => {
  it('does not fetch or mutate until opened and never requires another module', async () => {
    const { client } = setup(); expect(client.references).not.toHaveBeenCalled(); expect(client.addRelationship).not.toHaveBeenCalled();
    await open(); expect(client.references).toHaveBeenCalledWith('ASSET', expect.any(AbortSignal));
    expect(screen.getByText('尚未添加关联。独立导入和导出无需关联。')).toBeTruthy();
    expect(screen.getByText(/不复制章节或剧本/)).toBeTruthy();
  });

  it('saves exact source and target versions only after explicit submit', async () => {
    const { client, onDirtyChange } = setup(); await open(); choose();
    fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '构图参考' } });
    expect(client.addRelationship).not.toHaveBeenCalled();
    expect(onDirtyChange).toHaveBeenLastCalledWith(true);
    fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await waitFor(() => expect(client.addRelationship).toHaveBeenCalledWith('source', { expected_version: 4, type: 'REFERENCES', target: { kind: 'ASSET', id: 'target', version: 2, digest }, reason: '构图参考' }));
    await waitFor(() => expect(onDirtyChange).toHaveBeenLastCalledWith(false));
    expect(client.removeRelationship).not.toHaveBeenCalled();
  });

  it('keeps CAS-conflicted input and never silently rebases or retries', async () => {
    const { client } = setup(); client.addRelationship.mockRejectedValue(new ApiError({ status: 409, code: 'VERSION_CONFLICT', message: '版本冲突，输入已保留。' }));
    await open(); choose(); fireEvent.change(screen.getByLabelText('关联理由'), { target: { value: '保留这个理由' } }); fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await screen.findByRole('alert');
    expect((screen.getByLabelText('关联理由') as HTMLTextAreaElement).value).toBe('保留这个理由');
    expect(client.addRelationship).toHaveBeenCalledTimes(1);
    expect((screen.getByLabelText('关联目标') as HTMLSelectElement).selectedOptions[0].text).toBe('可访问目标 · v2');
  });

  it('keeps a changed target snapshot until the author explicitly chooses the new version', async () => {
    const { client } = setup(); await open(); choose();
    client.references.mockResolvedValue({ items: [reference('ASSET', { version: 3, digest: 'b'.repeat(64) })], read_only: true, content_copied: false });
    fireEvent.click(screen.getByRole('button', { name: '重新读取引用目录' }));
    await screen.findByText('所选目标已变化或不可用。原选择已保留；请核对后重新选择目标。');
    expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.getByText(`已选 ASSET · v2 · SHA-256 ${digest}`)).toBeTruthy();
    const newOption = screen.getByRole('option', { name: '可访问目标 · v3' }) as HTMLOptionElement;
    fireEvent.change(screen.getByLabelText('关联目标'), { target: { value: newOption.value } });
    expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(false);
    expect(client.addRelationship).not.toHaveBeenCalled();
  });

  it('lists chapter and screenplay references without copying content or creating records', async () => {
    const { client, onDirtyChange } = setup({ canMutate: false }); await open();
    fireEvent.change(screen.getByLabelText('引用类型'), { target: { value: 'CHAPTER' } }); await waitFor(() => expect(client.references).toHaveBeenLastCalledWith('CHAPTER', expect.any(AbortSignal)));
    fireEvent.change(screen.getByLabelText('引用类型'), { target: { value: 'SCREENPLAY' } }); await waitFor(() => expect(client.references).toHaveBeenLastCalledWith('SCREENPLAY', expect.any(AbortSignal)));
    expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(true);
    expect(onDirtyChange).toHaveBeenLastCalledWith(false); expect(client.addRelationship).not.toHaveBeenCalled();
  });

  it('requires review capability for APPROVED_FOR even when ordinary writes are allowed', async () => {
    setup(); await open(); expect((screen.getByRole('option', { name: '审核适用' }) as HTMLOptionElement).disabled).toBe(true);
    fireEvent.change(screen.getByLabelText('关系类型'), { target: { value: 'APPROVED_FOR' } });
    expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('allows a review-only actor to explicitly declare review without authoring permission', async () => {
    const { client } = setup({ canMutate: false, canReview: true }); await open();
    fireEvent.change(screen.getByLabelText('关系类型'), { target: { value: 'APPROVED_FOR' } }); choose();
    fireEvent.click(screen.getByRole('button', { name: '保存关联' }));
    await waitFor(() => expect(client.addRelationship).toHaveBeenCalledWith('source', expect.objectContaining({ type: 'APPROVED_FOR' })));
    expect((screen.getByRole('option', { name: '参考' }) as HTMLOptionElement).disabled).toBe(true);
  });

  it('shows stale and unavailable links without inventing redacted target metadata', async () => {
    const asset = source(); asset.relationships = [link({ state: 'STALE', target: reference('ASSET', { version: 3 }) }), { id: 'redacted', type: 'LINKED_CONTEXT', state: 'UNAVAILABLE', target: { label: '关联内容不可用或无权访问' } }];
    setup({ asset }); await open(); expect(screen.getByText('关联时 v2 · 当前 v3')).toBeTruthy(); expect(screen.getByText('目标已更新')).toBeTruthy();
    const unavailable = screen.getByText('关联内容不可用或无权访问').closest('li')!;
    expect(unavailable.textContent).not.toContain('undefined'); expect(unavailable.textContent).not.toContain('target'); expect(unavailable.textContent).not.toContain('理由');
  });

  it('requires a separate confirmation before removing only a relation', async () => {
    const asset = source(); asset.relationships = [link()]; const { client } = setup({ asset }); await open();
    fireEvent.click(screen.getByRole('button', { name: '移除关联 参考' }));
    expect(client.removeRelationship).not.toHaveBeenCalled(); expect((screen.getByRole('button', { name: '确认移除' }) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByLabelText('确认移除此关联')); fireEvent.click(screen.getByRole('button', { name: '确认移除' }));
    await waitFor(() => expect(client.removeRelationship).toHaveBeenCalledWith('source', 'link', 4)); expect(client.addRelationship).not.toHaveBeenCalled();
  });

  it('blocks cross-form writes and ignores a delayed directory after authority changes', async () => {
    let active = true, finish!: (value: { items: StudioReference[]; read_only: true; content_copied: false }) => void;
    const { client } = setup({ blocked: true, current: () => active }); client.references.mockImplementation(() => new Promise(resolve => { finish = resolve; }));
    fireEvent.click(screen.getByRole('button', { name: '可选资产关联' })); active = false;
    await act(async () => finish({ items: [reference()], read_only: true, content_copied: false }));
    expect(screen.queryByRole('option', { name: '可访问目标 · v2' })).toBeNull();
    expect((screen.getByRole('button', { name: '保存关联' }) as HTMLButtonElement).disabled).toBe(true); expect(client.addRelationship).not.toHaveBeenCalled();
  });

  it('shows a lazy descriptive graph with read-only lineage edges and no execution controls', async () => {
    const { client } = setup(); client.relationships.mockResolvedValue({ graph_kind: 'ASSET_RELATIONSHIPS', nodes: [{ id: 'source', kind: 'ASSET', asset_kind: 'image', label: 'source.png', version: 4, digest }], edges: [{ id: 'lineage-1', from: 'source', owner: 'ASSET_LINEAGE', type: 'DERIVED_FROM', state: 'CURRENT', target: reference() }], executable: false, knowledge_graph: false, automatic_regeneration: false });
    await open(); expect(client.relationships).not.toHaveBeenCalled(); fireEvent.click(screen.getByRole('button', { name: '读取项目关联概览' }));
    const graph = await screen.findByRole('region', { name: '项目关联概览' });
    expect(within(graph).getByText(/原始来源关系（只读）/)).toBeTruthy(); expect(graph.textContent).toContain('不会执行'); expect(client.addRelationship).not.toHaveBeenCalled();
  });
});
