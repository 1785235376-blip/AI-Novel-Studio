// @vitest-environment jsdom
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { DirectorShotList, buildVoiceManifest, buildMotionBatchCsv } from './DirectorShotList';

vi.mock('../api', () => ({ api: { synthesizeDirectorShotDialogue: vi.fn() } }));
describe('DirectorShotList', () => {
  beforeEach(() => { localStorage.clear(); });
  afterEach(cleanup);
  it('updates the matching shot without mutating other shots', () => {
    const onChange = vi.fn();
    render(<DirectorShotList shots={[{ shot_id: 'a', name: '一', duration: '2s', camera: '', action: '' }, { shot_id: 'b', name: '二', duration: '2s', camera: '', action: '' }]} profiles={[]} onChange={onChange} />);
    fireEvent.change(screen.getAllByLabelText('镜头名称')[1], { target: { value: '二号镜头' } });
    expect(onChange).toHaveBeenLastCalledWith([expect.objectContaining({ name: '一' }), expect.objectContaining({ name: '二号镜头' })]);
  });
  it('builds a stable voice manifest for export', () => {
    const rows = buildVoiceManifest([{ shot_id:'a', name:'一', duration:'2s', camera:'', action:'', dialogue:'开始', voice:'hero' }], [{ shot_id:'a', status:'succeeded', result:{ audio_uri:'audio://a' } }]);
    expect(rows[0]).toEqual(expect.objectContaining({ shot_id:'a', dialogue:'开始', voice:'hero', status:'succeeded', audio_uri:'audio://a' }));
  });
  it('escapes motion batch CSV fields', () => {
    const csv = buildMotionBatchCsv([{ shot_id:'s1', name:'镜头,一', duration:'4s', camera:'"推进"', action:'', screenplay_id:'sp1', motion_task_id:'task1', constraint_status:'confirmed' }]);
    expect(csv).toContain('"镜头,一"');
    expect(csv).toContain('""推进""');
  });
  it('protects clearing all batch drafts with confirmation', () => {
    localStorage.setItem('multimodal-motion-batch-draft:workspace', JSON.stringify([{ saved_at: '2026-08-25T00:00:00Z', shots: [{ shot_id: 's1', name: '一', duration: '2s', camera: '', action: '' }] }]));
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false);
    render(<DirectorShotList shots={[{ shot_id: 's1', name: '一', duration: '2s', camera: '', action: '' }]} profiles={[]} onChange={vi.fn()} />);
    fireEvent.click(screen.getByText('清空草稿'));
    expect(confirm).toHaveBeenCalled();
    expect(localStorage.getItem('multimodal-motion-batch-draft:workspace')).toContain('s1');
    confirm.mockRestore();
  });
  it('duplicates a shot with a unique id and clears task bindings', () => {
    const onChange = vi.fn();
    render(<DirectorShotList shots={[{ shot_id: 's1', name: '镜头', duration: '2s', camera: '', action: '', motion_task_id: 'task-1', constraint_status: 'confirmed' }]} profiles={[]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('复制镜头 镜头'));
    expect(onChange).toHaveBeenCalledWith([
      expect.objectContaining({ shot_id: 's1' }),
      expect.objectContaining({ shot_id: 's1-copy', name: '镜头 副本', motion_task_id: undefined, constraint_status: undefined }),
    ]);
  });
  it('deletes a shot but keeps the final timeline clip', () => {
    const onChange = vi.fn();
    const { rerender } = render(<DirectorShotList shots={[{ shot_id: 's1', name: '一', duration: '2s', camera: '', action: '' }, { shot_id: 's2', name: '二', duration: '2s', camera: '', action: '' }]} profiles={[]} onChange={onChange} />);
    fireEvent.click(screen.getByLabelText('删除镜头 一'));
    expect(onChange).toHaveBeenCalledWith([expect.objectContaining({ shot_id: 's2' })]);
    onChange.mockClear();
    rerender(<DirectorShotList shots={[{ shot_id: 's1', name: '一', duration: '2s', camera: '', action: '' }]} profiles={[]} onChange={onChange} />);
    expect((screen.getByLabelText('删除镜头 一') as HTMLButtonElement).disabled).toBe(true);
  });
});
