// @vitest-environment jsdom
import { beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { MultimodalDirectorWorkspace } from './MultimodalDirectorWorkspace';

vi.mock('../api', () => ({ api: { assets: vi.fn().mockResolvedValue([{ id: 'prop-1', filename: '怀表.png', media_type: 'image/png' }]) } }));

describe('MultimodalDirectorWorkspace', () => {
  beforeEach(() => { cleanup(); localStorage.clear(); });
  it('adds a semantic image reference and emits constraints', () => {
    const onChange = vi.fn();
    render(<MultimodalDirectorWorkspace mode="image" onConstraintsChange={onChange} />);
    fireEvent.change(screen.getByLabelText('参考语义'), { target: { value: '构图' } });
    fireEvent.change(screen.getByPlaceholderText('粘贴本地或已上传图片地址'), { target: { value: 'ref://hero' } });
    fireEvent.click(screen.getByText('添加'));
    expect(screen.getByText(/构图 · ref:\/\/hero/)).toBeTruthy();
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ references: [expect.objectContaining({ role: '构图', uri: 'ref://hero' })] }));
  });

  it('adds a director shot in video mode', () => {
    const onShotsChange = vi.fn();
    render(<MultimodalDirectorWorkspace mode="video" onShotsChange={onShotsChange} />);
    expect(screen.getAllByLabelText('镜头名称')).toHaveLength(1);
    fireEvent.click(screen.getByText('新增镜头'));
    expect(screen.getAllByLabelText('镜头名称')).toHaveLength(2);
    expect(onShotsChange).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ name: '镜头 01' })]));
  });

  it('emits updated prop asset constraints', async () => {
    const onChange = vi.fn();
    render(<MultimodalDirectorWorkspace mode="image" novelId="novel-props" onConstraintsChange={onChange} />);
    const checkbox = await screen.findByRole('checkbox');
    fireEvent.click(checkbox);
    expect(onChange).toHaveBeenLastCalledWith(expect.objectContaining({ consistency: expect.objectContaining({ prop_asset_ids: ['prop-1'] }) }));
  });

  it('emits dialogue and subtitle fields on the director shot', () => {
    const onShotsChange = vi.fn();
    render(<MultimodalDirectorWorkspace mode="video" onShotsChange={onShotsChange} />);
    fireEvent.change(screen.getByLabelText('镜头对白'), { target: { value: '快走！' } });
    fireEvent.change(screen.getByLabelText('镜头字幕'), { target: { value: '快走！' } });
    expect(onShotsChange).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ dialogue: '快走！', subtitle: '快走！' })]));
  });

  it('opens the advanced shot cards with shared shot state', () => {
    const onShotsChange = vi.fn();
    render(<MultimodalDirectorWorkspace mode="video" onShotsChange={onShotsChange} />);
    fireEvent.click(screen.getByText('使用高级镜头卡片'));
    expect(screen.getAllByLabelText('镜头名称').length).toBeGreaterThan(1);
    fireEvent.change(screen.getAllByLabelText('镜头名称').at(-1)!, { target: { value: '高级镜头' } });
    expect(onShotsChange).toHaveBeenLastCalledWith(expect.arrayContaining([expect.objectContaining({ name: '高级镜头' })]));
  });

  it('requires confirmation before clearing local workspace data', () => {
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<MultimodalDirectorWorkspace mode="image" />);
    fireEvent.change(screen.getByPlaceholderText('粘贴本地或已上传图片地址'), { target: { value: 'ref://keep' } });
    fireEvent.click(screen.getByText('添加'));
    fireEvent.click(screen.getByLabelText('清空本地工作区'));
    expect(confirm).toHaveBeenCalled();
    expect(screen.getAllByText(/ref:\/\/keep/).length).toBeGreaterThan(0);
  });
  it('adds semantic references to the local binding summary', () => {
    render(<MultimodalDirectorWorkspace mode="image" novelId="bindings-test" />);
    fireEvent.change(screen.getByPlaceholderText('粘贴本地或已上传图片地址'), { target: { value: 'ref://character' } });
    fireEvent.click(screen.getByText('添加'));
    expect(screen.getByText(/绑定清单：角色 1/)).toBeTruthy();
  });

  it('restores binding manifest entries when importing a confirmed constraint package', async () => {
    render(<MultimodalDirectorWorkspace mode="image" novelId="import-bindings" />);
    const file = new File([JSON.stringify({
      mode: 'image',
      references: [{ uri: 'ref://imported', role: '角色', position: { x: 20, y: 30 } }],
      bindings: { characters: ['导入角色'], scenes: ['导入场景'], props: ['导入道具'] },
    })], 'constraints.json', { type: 'application/json' });
    fireEvent.change(screen.getByLabelText('导入 JSON'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByRole('dialog')).toBeTruthy());
    fireEvent.click(screen.getByText('确认导入'));
    await waitFor(() => expect(screen.getByText(/绑定清单：角色 2 · 场景 1 · 道具 1/)).toBeTruthy());
    expect(screen.getAllByText(/ref:\/\/imported/).length).toBeGreaterThan(0);
  });

  it('does not overwrite bindings when an invalid package is selected', async () => {
    render(<MultimodalDirectorWorkspace mode="image" novelId="invalid-bindings" />);
    fireEvent.change(screen.getByPlaceholderText('粘贴本地或已上传图片地址'), { target: { value: 'ref://existing' } });
    fireEvent.click(screen.getByText('添加'));
    const file = new File([JSON.stringify({ bindings: { characters: 'not-an-array' } })], 'invalid.json', { type: 'application/json' });
    fireEvent.change(screen.getByLabelText('导入 JSON'), { target: { files: [file] } });
    await waitFor(() => expect(screen.getByText('约束包格式无效')).toBeTruthy());
    expect(screen.getByText(/绑定清单：角色 1/)).toBeTruthy();
  });



  it('saves, restores, and deletes a consistency profile', () => {
    vi.spyOn(window, 'confirm').mockReturnValue(true);
    render(<MultimodalDirectorWorkspace mode="image" novelId="novel-1" />);
    fireEvent.change(screen.getByLabelText('角色外观'), { target: { value: '黑色短发' } });
    fireEvent.change(screen.getByLabelText('档案名称'), { target: { value: '主角标准造型' } });
    fireEvent.click(screen.getByText('保存档案'));
    fireEvent.change(screen.getByLabelText('角色外观'), { target: { value: '临时造型' } });
    fireEvent.change(screen.getByLabelText('一致性档案'), { target: { value: '主角标准造型' } });
    expect((screen.getByLabelText('角色外观') as HTMLInputElement).value).toBe('黑色短发');
    fireEvent.click(screen.getByLabelText('删除当前档案'));
    expect(window.confirm).toHaveBeenCalled();
  });

});


