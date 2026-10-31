// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AIDirectorPanel } from './AIDirectorPanel';
import { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import type { DirectorProposal, DirectorProposalClient } from './client';
import { newDocument, newShot, type CreativeDocument, type DirectorSceneNote } from './types';

const board = (): CreativeDocument => ({ ...newDocument('STORYBOARD'), id: 'board', version: 7, title: 'Saved authored board', status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {}, shots: [
  { ...newShot(9, 'same-scene'), id: 'shot-later', frame_prompt: 'Later frame', duration_seconds: 8 },
  { ...newShot(3, 'same-scene'), id: 'shot-first', frame_prompt: 'First frame', duration_seconds: 4, sound: 'Retained sound' },
] });
function proposal(): DirectorProposal {
  const shots = board().shots.sort((a, b) => a.number - b.number);
  const notes = shots.map(shot => ({ id: `note-${shot.id}`, number: shot.number, scene_id: shot.scene_id, note: shot.frame_prompt, shot_size: shot.shot_size, camera_angle: shot.camera_angle, camera_motion: shot.camera_motion, duration_seconds: shot.duration_seconds, emotion: '', pacing: 'Rule hypothesis', performance: '', blocking: 'Verify spatial relation' }));
  return { id: 'proposal', version: 1, status: 'NEEDS_REVIEW', source_document_id: 'board', source_version: 7, source_digest: 'a'.repeat(64), title: 'Board direction', output_digest: 'digest', director_notes: notes, provenance: { source_mode: 'STORYBOARD', model_called: false, source_shots: shots.map((shot, i) => ({ note_id: notes[i].id, source_shot_id: shot.id, source_number: shot.number, scene_id: shot.scene_id, source_shot: shot, copied_fields: ['shot_size', 'camera_angle', 'camera_motion', 'duration_seconds'], suggested_fields: ['pacing', 'blocking'], retained_source_only_fields: ['sound', 'dialogue', 'continuity'] })) } };
}
function client() {
  const candidate = proposal();
  const draft: CreativeDocument = { ...board(), mode: 'DIRECTOR', id: 'director', version: 1, shots: [], director_notes: candidate.director_notes, source_documents: { board: { version: 7, digest: 'a'.repeat(64) } } };
  return { proposals: vi.fn().mockResolvedValue({ items: [] }), proposal: vi.fn().mockResolvedValue({ ...candidate, status: 'APPROVED', version: 2, document_id: draft.id }), propose: vi.fn().mockResolvedValue(candidate), review: vi.fn<(_proposal: DirectorProposal, _title: string, _notes: DirectorSceneNote[]) => Promise<{ proposal: DirectorProposal; document: CreativeDocument }>>().mockResolvedValue({ proposal: { ...candidate, status: 'APPROVED', version: 2, document_id: draft.id }, document: draft }), cancelProposal: vi.fn().mockResolvedValue({ ...candidate, status: 'CANCELLED', version: 2 }), get: vi.fn().mockResolvedValue(draft), modelRoutes: vi.fn().mockResolvedValue({ items: [] }), previewModel: vi.fn(), dispatchModel: vi.fn(), refreshModel: vi.fn(), list: vi.fn().mockResolvedValue({ items: [board()] }) };
}
const check = () => screen.getByLabelText('已核对来源、场面调度与导演建议；创建独立导演文档');
async function prepare() { fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' })); await screen.findByLabelText('采用后的导演文档标题'); }
afterEach(cleanup);

it('uses the original graph owner for saved storyboard → reviewed separate draft → verified reopen without mutating source', async () => {
  const api = client(), onDocument = vi.fn(), mutate = vi.fn();
  const source = board(); api.list.mockResolvedValue({ items: [source] });
  const snapshot = JSON.stringify(source);
  render(<GraphDirectorProposalReview client={api} active canMutate busy={false} isCurrent={() => true} read={work => work()} mutate={work => { mutate(); return work(); }} onPendingChange={() => {}} onDocument={onDocument} onDenied={() => {}} />);
  fireEvent.click(screen.getByRole('button', { name: '从已保存分镜打开导演建议审核' }));
  await screen.findByRole('option', { name: 'Saved authored board · 分镜 · v7' }); await prepare();
  expect(api.propose).toHaveBeenCalledWith(board(), undefined);
  expect(screen.getByText('分镜调度 #3')).toBeTruthy(); expect(screen.getByText('分镜调度 #9')).toBeTruthy();
  expect(screen.getByText(/当前仅支持 RULE_ASSISTED/)).toBeTruthy();
  expect(screen.getByText(/相机与时长直接复制/)).toBeTruthy();
  expect(screen.getAllByText(/仅保留在来源记录、未映射为导演执行字段/)).toHaveLength(2);
  expect(screen.queryByRole('region', { name: '可选本地模型导演' })).toBeNull();
  expect(api.modelRoutes).not.toHaveBeenCalled(); expect(api.review).not.toHaveBeenCalled();
  fireEvent.click(check()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
  await waitFor(() => expect(onDocument).toHaveBeenCalledTimes(1));
  expect(api.review.mock.calls[0][2].map((row: { number: number }) => row.number)).toEqual([3, 9]);
  expect(onDocument.mock.calls[0][0]).toMatchObject({ id: 'director', mode: 'DIRECTOR', status: 'DRAFT' });
  fireEvent.click(screen.getByRole('button', { name: '核对并打开已采用的导演草稿' }));
  await waitFor(() => expect(onDocument).toHaveBeenCalledTimes(2));
  expect(mutate).toHaveBeenCalledTimes(2); expect(api.dispatchModel).not.toHaveBeenCalled();
  expect(JSON.stringify(source)).toBe(snapshot);
});

it('retains dirty storyboard review and requires explicit discard before new source selection', async () => {
  const api = client(), source = board(), original = structuredClone(source);
  render(<AIDirectorPanel client={api} documents={[source, { ...source, id: 'board-two', title: 'Other board' }]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  await prepare(); fireEvent.change(screen.getByLabelText('建议 1 时长（秒）'), { target: { value: '11' } });
  expect((screen.getByLabelText('导演建议来源剧本或分镜') as HTMLSelectElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true);
  expect((screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并恢复原建议'));
  fireEvent.click(screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }));
  expect((screen.getByLabelText('建议 1 时长（秒）') as HTMLInputElement).value).toBe('4');
  expect(source).toEqual(original); expect(api.review).not.toHaveBeenCalled();
});

it.each(['unmount', 'client replacement'] as const)('ignores delayed storyboard proposal after %s', async interruption => {
  const api = client(); let resolve!: (row: DirectorProposal) => void;
  api.propose.mockReturnValue(new Promise<DirectorProposal>(yes => { resolve = yes; }));
  const onDocument = vi.fn();
  const props = { client: api as DirectorProposalClient, documents: [board()], canMutate: true, onDocument, onDenied: vi.fn() };
  const view = render(<AIDirectorPanel {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '准备待审导演建议' }));
  if (interruption === 'unmount') view.unmount(); else view.rerender(<AIDirectorPanel {...props} client={client()} />);
  await act(async () => resolve(proposal()));
  expect(screen.queryByLabelText('采用后的导演文档标题')).toBeNull(); expect(onDocument).not.toHaveBeenCalled(); expect(api.review).not.toHaveBeenCalled();
});

it('excludes empty saved boards and never offers model controls for an existing storyboard proposal', async () => {
  const api = client(); api.proposals.mockResolvedValue({ items: [proposal()] });
  render(<AIDirectorPanel client={api} documents={[{ ...board(), shots: [] }]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  expect((screen.getByRole('button', { name: '准备待审导演建议' }) as HTMLButtonElement).disabled).toBe(true);
  fireEvent.click(await screen.findByRole('button', { name: /Board direction/ }));
  expect(screen.queryByRole('button', { name: '预览模型输入' })).toBeNull(); expect(api.modelRoutes).not.toHaveBeenCalled();
});

function retained<T>(element: HTMLElement, name: string): T {
  const key = Object.keys(element).find(key => key.startsWith('__reactProps$'))!;
  return (element as unknown as Record<string, Record<string, T>>)[key][name];
}
it.each(['unmount', 'client ABA', 'source ABA', 'source version', 'permission retirement'] as const)('rejects an actual retained prepare handler after %s before dispatch', async retirement => {
  const api = client(), a = board(), b = { ...board(), id: 'other-board' }, onDocument = vi.fn();
  const props = { client: api, documents: [a, b], canMutate: true, onDocument, onDenied: vi.fn() };
  const view = render(<AIDirectorPanel {...props} />); await screen.findByText('没有待审导演建议');
  const oldPrepare = retained<(event: { detail: number }) => void>(screen.getByRole('button', { name: '准备待审导演建议' }), 'onClick');
  if (retirement === 'unmount') view.unmount();
  else if (retirement === 'client ABA') { view.rerender(<AIDirectorPanel {...props} client={client()} />); view.rerender(<AIDirectorPanel {...props} />); }
  else if (retirement === 'source ABA') {
    fireEvent.change(screen.getByLabelText('导演建议来源剧本或分镜'), { target: { value: b.id } });
    fireEvent.change(screen.getByLabelText('导演建议来源剧本或分镜'), { target: { value: a.id } });
  } else if (retirement === 'source version') view.rerender(<AIDirectorPanel {...props} documents={[{ ...a, version: 8 }, b]} />);
  else view.rerender(<AIDirectorPanel {...props} canMutate={false} />);
  act(() => oldPrepare({ detail: 1 })); expect(api.propose).not.toHaveBeenCalled(); expect(onDocument).not.toHaveBeenCalled();
});

it('rejects a retained source change handler once the storyboard review is dirty', async () => {
  const api = client(); render(<AIDirectorPanel client={api} documents={[board(), { ...board(), id: 'other-board' }]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  await screen.findByText('没有待审导演建议');
  const oldChange = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('导演建议来源剧本或分镜'), 'onChange');
  await prepare(); fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Local review title' } });
  act(() => oldChange({ target: { value: 'other-board' } }));
  expect((screen.getByLabelText('导演建议来源剧本或分镜') as HTMLSelectElement).value).toBe('board');
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Local review title');
});

it.each(['missing', 'contradictory', 'malformed'] as const)('fails closed for %s storyboard source provenance without reading model routes', async kind => {
  const api = client(), row = proposal();
  if (kind === 'missing') delete row.provenance.source_mode;
  else if (kind === 'contradictory') row.provenance.source_mode = 'SCREENPLAY';
  else Object.assign(row.provenance, { source_mode: 'UNKNOWN' });
  api.proposals.mockResolvedValue({ items: [row] });
  render(<AIDirectorPanel client={api} documents={[board()]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  fireEvent.click(await screen.findByRole('button', { name: /Board direction/ }));
  expect(screen.getByText(/来源类型记录不一致或缺失/)).toBeTruthy();
  expect(screen.queryByRole('button', { name: '预览模型输入' })).toBeNull(); expect(api.modelRoutes).not.toHaveBeenCalled();
});

it.each(['source change', 'source ABA', 'review edit'] as const)('retires old prepare synchronously before a React paint on %s', async change => {
  const api = client(); render(<AIDirectorPanel client={api} documents={[board(), { ...board(), id: 'other-board' }]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  await screen.findByText('没有待审导演建议');
  if (change === 'review edit') await prepare();
  const oldPrepare = retained<(event: { detail: number }) => void>(screen.getByRole('button', { name: '准备待审导演建议' }), 'onClick');
  const sourceChange = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('导演建议来源剧本或分镜'), 'onChange');
  const titleChange = change === 'review edit' ? retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('采用后的导演文档标题'), 'onChange') : undefined;
  api.propose.mockClear();
  act(() => {
    if (titleChange) titleChange({ target: { value: 'Keep local edit' } });
    else { sourceChange({ target: { value: 'other-board' } }); if (change === 'source ABA') sourceChange({ target: { value: 'board' } }); }
    oldPrepare({ detail: 1 });
  });
  expect(api.propose).not.toHaveBeenCalled();
  if (titleChange) expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Keep local edit');
});

it('does not let a retained confirmed-discard callback erase a newer same-batch edit', async () => {
  const api = client(); render(<AIDirectorPanel client={api} documents={[board()]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  await prepare(); fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'First edit' } });
  fireEvent.click(screen.getByLabelText('确认放弃本地审核修改并恢复原建议'));
  const discard = retained<() => void>(screen.getByRole('button', { name: '放弃本地审核修改，恢复原建议' }), 'onClick');
  const change = retained<(event: { target: { value: string } }) => void>(screen.getByLabelText('采用后的导演文档标题'), 'onChange');
  act(() => { change({ target: { value: 'Newest edit' } }); discard(); });
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Newest edit');
  expect(api.review).not.toHaveBeenCalled();
});

it('does not reuse retained recovery-discard consent after a same-batch revocation', async () => {
  const api = client(); api.review.mockRejectedValue(new Error('ambiguous receipt'));
  render(<AIDirectorPanel client={api} documents={[board()]} canMutate onDocument={() => {}} onDenied={() => {}} />);
  await prepare(); fireEvent.change(screen.getByLabelText('采用后的导演文档标题'), { target: { value: 'Keep uncertain review' } });
  fireEvent.click(check()); fireEvent.click(screen.getByRole('button', { name: '审核并采用' }));
  await screen.findByRole('button', { name: '重新读取建议状态' });
  api.proposals.mockResolvedValue({ items: [proposal()] });
  fireEvent.click(screen.getByRole('button', { name: '重新读取建议状态' }));
  const consent = await screen.findByLabelText('确认放弃本地审核修改并采用已读取建议状态'); fireEvent.click(consent);
  const discard = retained<() => void>(screen.getByRole('button', { name: '处理已核对的建议状态' }), 'onClick');
  const revoke = retained<(event: { target: { checked: boolean } }) => void>(consent, 'onChange');
  act(() => { revoke({ target: { checked: false } }); discard(); });
  expect((screen.getByLabelText('采用后的导演文档标题') as HTMLInputElement).value).toBe('Keep uncertain review');
  expect(screen.getByRole('button', { name: '重新读取建议状态' })).toBeTruthy();
});
