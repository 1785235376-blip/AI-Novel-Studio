// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import { newDocument, type CreativeDocument, type CreativeInput } from './types';
const pin = { id: 'director-one', version: 1, digest: 'a'.repeat(64) };
const document = (version = 1): CreativeDocument => ({ ...newDocument('DIRECTOR'), source_independent: true, title: '原导演',
  id: pin.id, version, status: 'DRAFT', created_at: '', updated_at: '', actor_id: 'author', source_evidence: {} });
function setup() {
  let stored = document();
  const client: GraphDirectorSource = { history: vi.fn(),
    derive: vi.fn(),
    list: vi.fn(async () => ({ items: [stored] })),
    capabilities: vi.fn().mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] }),
    create: vi.fn(async (input: CreativeInput) => stored = { ...stored, ...input }),
    update: vi.fn(async (id: string, version: number, input: CreativeInput) => stored = { ...stored, ...input, id, version: version + 1 }),
    export: vi.fn(async () => ({ document: stored, document_digest: stored.version === 1 ? pin.digest : 'b'.repeat(64), format: 'creative-json/1', boundary: 'original-owner' })),
  };
  const props = { client, active: true, canMutate: true, busy: false, isCurrent: () => true,
    read: async <T,>(work: () => Promise<T>) => work(), mutate: async <T,>(work: () => Promise<T>) => work(), onDirtyChange: vi.fn() };
  return { client, props };
}
const click = (name: string) => fireEvent.click(screen.getByRole('button', { name }));
const change = (name: string, value: string) => fireEvent.change(screen.getByLabelText(name), { target: { value } });
async function open() { click('打开导演总控台'); await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false)); }
afterEach(cleanup);
describe('optional mounted graph director source authoring', () => {
  it('rejects A→B→A source reads and a changed node with the same source pin', async () => {
    const { client, props } = setup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
    vi.mocked(client.export).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorConsole {...props} pin={pin} selectionKey="node-a" />); await open(); click('读取选中导演节点原文档');
    view.rerender(<GraphDirectorConsole {...props} pin={{ ...pin, id: 'other' }} selectionKey="node-b" />);
    view.rerender(<GraphDirectorConsole {...props} pin={pin} selectionKey="node-a" />);
    await act(async () => resolve({ document: document(), document_digest: pin.digest, format: '', boundary: '' }));
    expect(screen.queryByDisplayValue('原导演')).toBeNull();
    vi.mocked(client.export).mockReturnValue(new Promise(yes => resolve = yes)); click('读取选中导演节点原文档');
    view.rerender(<GraphDirectorConsole {...props} pin={pin} selectionKey="node-c" />);
    await act(async () => resolve({ document: document(), document_digest: pin.digest, format: '', boundary: '' }));
    expect(screen.queryByDisplayValue('原导演')).toBeNull();
  });
  it('does not adopt late capabilities after the source client is replaced', async () => {
    const { client, props } = setup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['capabilities']>>) => void;
    vi.mocked(client.capabilities).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorConsole {...props} />); click('打开导演总控台');
    view.rerender(<GraphDirectorConsole {...props} client={setup().client} />);
    await act(async () => resolve({ enabled: true, can_mutate: true, modes: ['DIRECTOR'] } as Awaited<ReturnType<GraphDirectorSource['capabilities']>>));
    expect(screen.getByText('导演来源连接已改变，请重新打开工作区。')).toBeTruthy(); expect(screen.queryByLabelText('文档标题')).toBeNull();
  });
  it('locks an invalid success receipt instead of claiming a saved first create', async () => {
    const { client, props } = setup(); vi.mocked(client.create).mockResolvedValue({ ...document(), id: '', version: 0 });
    render(<GraphDirectorConsole {...props} />); await open(); change('文档标题', '保留无效回执草稿'); click('保存草稿');
    await screen.findByText(/保存冲突或回执不确定/); expect(screen.queryByText(/导演原文档已保存/)).toBeNull();
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
  });
  it('keeps a save uncertain after an active A→inactive→A lifetime change', async () => {
    const { client, props } = setup(); let resolve!: (value: CreativeDocument) => void;
    vi.mocked(client.create).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorConsole {...props} />); await open(); change('文档标题', '保存中断'); click('保存草稿');
    view.rerender(<GraphDirectorConsole {...props} active={false} />); view.rerender(<GraphDirectorConsole {...props} />);
    await act(async () => resolve(document()));
    expect(screen.queryByText(/导演原文档已保存/)).toBeNull(); expect(props.onDirtyChange).not.toHaveBeenCalledWith(false);
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
  });

  it('does no background reads, saves authored scenes through original owner and reopens exact source', async () => {
    const { client, props } = setup(); const view = render(<GraphDirectorConsole {...props} />);
    expect(client.capabilities).not.toHaveBeenCalled(); expect(client.export).not.toHaveBeenCalled(); await open();
    change('文档标题', ' 清晨 🎬 '); click('添加场景'); click('添加导演调度'); change('导演意图', '先停顿，再转身');
    expect(props.onDirtyChange).toHaveBeenCalledWith(true); click('保存草稿');
    await waitFor(() => expect(client.create).toHaveBeenCalledTimes(1));
    expect(vi.mocked(client.create).mock.calls[0][0]).toMatchObject({ mode: 'DIRECTOR', title: ' 清晨 🎬 ', source_independent: true,
      director_notes: [expect.objectContaining({ note: '先停顿，再转身' })] });
    await screen.findByText(/导演原文档已保存/); expect(props.onDirtyChange).toHaveBeenLastCalledWith(false);
    view.unmount(); render(<GraphDirectorConsole {...props} pin={pin} />); await open(); click('读取选中导演节点原文档');
    await waitFor(() => expect((screen.getByLabelText('文档标题') as HTMLInputElement).value).toBe(' 清晨 🎬 ')); expect(screen.getByDisplayValue('先停顿，再转身')).toBeTruthy();
    expect(client.export).toHaveBeenCalledWith(pin.id); expect(client.update).not.toHaveBeenCalled();
  });
  it('hands a saved human director to the existing storyboard owner and reopens its status', async () => {
    const { client, props } = setup();
    vi.mocked(client.capabilities).mockResolvedValue({ enabled: true, can_mutate: true, modes: ['DIRECTOR', 'STORYBOARD'] });
    let board: CreativeDocument | undefined;
    vi.mocked(client.derive).mockImplementation(async (source) => board = { ...source, id: 'board', mode: 'STORYBOARD', version: 1, source_documents: { [source.id]: { version: source.version, digest: pin.digest } } });
    const originalExport = client.export;
    client.export = vi.fn(async id => id === 'board' ? { document: board!, document_digest: 'c'.repeat(64), format: '', boundary: '' } : originalExport(id));
    const view = render(<GraphDirectorConsole {...props} />); await open();
    change('文档标题', '人工导演'); click('添加场景'); click('添加导演调度'); change('导演意图', '停顿'); click('保存草稿');
    await screen.findByText(/导演原文档已保存/); expect((screen.getByRole('button', { name: '交接到原分镜草稿' }) as HTMLButtonElement).disabled).toBe(true);
    click('核对导演原文档版本'); await screen.findByText(/交接来源/);
    fireEvent.click(screen.getByLabelText('已核对来源，明确建立新的分镜草稿，仍需人工复审')); click('交接到原分镜草稿');
    await screen.findByRole('complementary', { name: '分镜原文档状态回传' }); expect(client.derive).toHaveBeenCalledTimes(1);
    vi.mocked(client.list).mockResolvedValue({ items: [board!] });
    view.unmount(); render(<GraphDirectorConsole {...props} pin={pin} />); await open(); click('读取选中导演节点原文档'); await screen.findByDisplayValue('人工导演');
    click('读取关联分镜与状态'); await screen.findByRole('button', { name: '读取分镜 人工导演 · v1' }); click('读取分镜 人工导演 · v1');
    await screen.findByText(new RegExp('c'.repeat(64))); expect(client.derive).toHaveBeenCalledTimes(1); expect(client.update).not.toHaveBeenCalled();
  });
  it('source edits keep the immutable graph pin and expose changed version impact', async () => {
    const { client, props } = setup(); render(<GraphDirectorConsole {...props} pin={pin} />); await open(); click('读取选中导演节点原文档');
    await screen.findByDisplayValue('原导演'); change('文档标题', '新导演'); click('保存草稿');
    await screen.findByText('节点来源已变更，原绑定没有自动更新；请核对下游影响。');
    expect(client.update).toHaveBeenCalledWith(pin.id, 1, expect.objectContaining({ title: '新导演' }));
    click('核对导演原文档版本'); await screen.findByText(/来源已变化：这里是当前原文档/);
    expect(screen.getByText(/选中节点绑定：/).textContent).toContain(pin.digest);
    expect(screen.getByText(/当前原文档：/).textContent).toContain('b'.repeat(64));
  });
  it('keeps conflict draft locked until explicit checked-source adoption', async () => {
    const { client, props } = setup(); vi.mocked(client.update).mockRejectedValue(new ApiError({ status: 409, code: 'CONFLICT', message: '版本冲突' }));
    render(<GraphDirectorConsole {...props} pin={pin} />); await open(); click('读取选中导演节点原文档'); await screen.findByDisplayValue('原导演');
    change('文档标题', '未保存'); click('保存草稿'); await screen.findByText(/保存冲突或回执不确定/);
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    click('核对导演原文档版本'); await screen.findByText(/已核对服务端：/); expect(screen.getByDisplayValue('未保存')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('确认放弃导演本地草稿并采用已核对原版本')); click('处理导演本地草稿');
    expect(screen.getByDisplayValue('原导演')).toBeTruthy(); expect(client.update).toHaveBeenCalledTimes(1);
  });
  it('does not retry an uncertain first create or clear its pending state on read', async () => {
    const { client, props } = setup(); vi.mocked(client.create).mockRejectedValue(new Error('offline'));
    render(<GraphDirectorConsole {...props} />); await open(); change('文档标题', '保留文本'); click('保存草稿');
    await screen.findByText(/保存冲突或回执不确定/); expect(screen.getByDisplayValue('保留文本')).toBeTruthy();
    expect(client.create).toHaveBeenCalledTimes(1); expect(props.onDirtyChange).toHaveBeenLastCalledWith(true);
    expect((screen.getByRole('button', { name: '折叠导演总控台' }) as HTMLButtonElement).disabled).toBe(true);
    click('读取导演原文档目录'); await screen.findByRole('option', { name: '原导演 · v1' }); change('总控台原导演文档', pin.id);
    click('读取所选导演原文档'); await screen.findByText(/已核对服务端：/);
    expect(screen.getByDisplayValue('保留文本')).toBeTruthy();
    fireEvent.click(screen.getByLabelText('确认放弃导演本地草稿并采用已核对原版本')); click('处理导演本地草稿');
    expect(screen.getByDisplayValue('原导演')).toBeTruthy(); expect(client.create).toHaveBeenCalledTimes(1);
  });
  it('reads source impact while a conflict draft stays locked and unchanged', async () => {
    const { client, props } = setup();
    vi.mocked(client.history).mockResolvedValue({ document_id: pin.id, current_version: 1, items: [document()], snapshot_digests: [pin] });
    vi.mocked(client.update).mockRejectedValue(new ApiError({ status: 409, code: 'CONFLICT', message: '版本冲突' }));
    render(<GraphDirectorConsole {...props} pin={pin} selectedNodeId="director-node" />); await open(); click('读取选中导演节点原文档'); await screen.findByDisplayValue('原导演');
    change('文档标题', '不可丢失草稿'); click('保存草稿'); await screen.findByText(/保存冲突或回执不确定/);
    click('读取／刷新导演来源影响'); await screen.findByText(/历史快照版本与原 Owner 摘要匹配/);
    expect(screen.getByDisplayValue('不可丢失草稿')).toBeTruthy();
    expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
    expect(props.onDirtyChange).toHaveBeenLastCalledWith(true); expect(client.update).toHaveBeenCalledTimes(1);
    expect(screen.getByText(/选中节点绑定：/).textContent).toContain(pin.digest);
  });
  it('ignores a late original-source read after leaving the graph', async () => {
    const { client, props } = setup(); let resolve!: (value: Awaited<ReturnType<GraphDirectorSource['export']>>) => void;
    vi.mocked(client.export).mockReturnValue(new Promise(yes => resolve = yes));
    const view = render(<GraphDirectorConsole {...props} pin={pin} />); await open(); click('读取选中导演节点原文档');
    view.rerender(<GraphDirectorConsole {...props} pin={pin} active={false} />);
    await act(async () => resolve({ document: document(), document_digest: pin.digest, format: '', boundary: '' }));
    view.rerender(<GraphDirectorConsole {...props} pin={pin} />); expect(screen.queryByDisplayValue('原导演')).toBeNull();
  });
});
