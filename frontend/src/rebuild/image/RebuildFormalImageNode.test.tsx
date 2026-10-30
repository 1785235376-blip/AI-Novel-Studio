// @vitest-environment jsdom
// Entry/authority regression. Child production UI is a stub; no execution or approval.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../../store';
import { bindLocalHostSession, clearLocalHostSession } from '../../localHostSession';
import { setCollaborationContext } from '../../api';
import { RebuildFormalImageNode } from './RebuildFormalImageNode';

const probe = vi.hoisted(() => ({ overview: vi.fn(), activate: vi.fn(), child: undefined as any }));
vi.mock('../../creative/studioClient', () => ({ studioClient: () => ({ overview: probe.overview, activate: probe.activate }) }));
vi.mock('../../creative/studioProductionClient', () => ({ studioProductionClient: () => ({}) }));
vi.mock('../../creative/CanvasImageNodeTask', () => ({ CanvasImageNodeTask: (props: any) => { probe.child = props; return <p>Original owner child</p>; } }));
const overview = { project: { id: 'project-a', incarnation: 'file:00000000-0000-4000-8000-000000000001' }, capabilities: { can_mutate: true, can_review: true } };
const props = { projectId: 'project-a', node: { id: 'node-a', t: 'image_generate' as const, title: 'Light', prompt: 'A lighthouse', x: 24, y: 48 }, isSourceCurrent: () => true };
beforeEach(() => {
  probe.child = undefined; probe.overview.mockReset().mockResolvedValue(overview); probe.activate.mockReset();
  setCollaborationContext({ sessionToken: '' });
  useStudio.setState({ novelId: 'project-a', sessionToken: '', actor: undefined, scope: undefined });
  bindLocalHostSession('synthetic-entry-host', { session_mode: 'LOCAL_HOST', actor_id: 'entry-author' });
});
afterEach(() => { cleanup(); clearLocalHostSession(); vi.restoreAllMocks(); });
async function open() { fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' })); await screen.findByText('Original owner child'); return probe.child; }
it('reads verified owner only on explicit entry and never creates a canvas by opening', async () => {
  render(<RebuildFormalImageNode {...props} />); expect(probe.overview).not.toHaveBeenCalled();
  const child = await open(); expect(probe.overview).toHaveBeenCalledTimes(1);
  expect(child.owner).toMatchObject({ projectId: 'project-a', actorId: 'entry-author', incarnation: overview.project.incarnation });
  expect(child.node).toEqual(props.node);
});
it('retires captured dispatch synchronously across project A/B/A before React commits', async () => {
  render(<RebuildFormalImageNode {...props} />); const child = await open(), write = vi.fn();
  await act(async () => {
    useStudio.setState({ novelId: 'project-b' }); useStudio.setState({ novelId: 'project-a' });
    await expect(child.mutate(write)).rejects.toThrow('原节点或工作区身份已改变');
  });
  expect(write).not.toHaveBeenCalled();
});
it('discards late owner read after project changes and leaves new context unopened', async () => {
  let finish!: (value: unknown) => void; probe.overview.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  const view = render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  act(() => useStudio.setState({ novelId: 'project-b' }));
  view.rerender(<RebuildFormalImageNode {...props} projectId="project-b" />);
  await act(async () => finish(overview)); expect(probe.child).toBeUndefined();
});
it('refuses a missing verified author and retires child on unmount', async () => {
  const view = render(<RebuildFormalImageNode {...props} />); const child = await open(), write = vi.fn();
  view.unmount(); await expect(child.mutate(write)).rejects.toThrow(); expect(write).not.toHaveBeenCalled();
  clearLocalHostSession(); render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  await screen.findByText('缺少可核实的项目代次或作者身份，不能建立服务端节点目标。');
});

// [HERMIA-FE-20261031 ACT] Reproduce-first: an un-activated (LEGACY) local File project must not mount the owner panel
// (providers would 422 STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED); activation is one explicit, confirmed POST.
const legacy = { ...overview, project: { ...overview.project, entry_kind: 'LEGACY' } };
const neutral = { ...overview, project: { ...overview.project, entry_kind: 'NEUTRAL_STUDIO' } };
it('LEGACY project shows an explicit activation step instead of the owner panel; cancel sends nothing', async () => {
  probe.overview.mockResolvedValue(legacy);
  render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  const entry = await screen.findByRole('button', { name: '启用独立工作室…' });
  expect(probe.child).toBeUndefined();
  fireEvent.click(entry);
  expect(screen.getByRole('dialog').textContent).toContain('不会改动正文、章节、权限或项目类型');
  fireEvent.click(screen.getByRole('button', { name: '取消' }));
  expect(probe.activate).not.toHaveBeenCalled(); expect(probe.child).toBeUndefined();
});
it('confirmed activation POSTs exactly once (double click), re-reads overview, then mounts owner panel', async () => {
  probe.overview.mockResolvedValueOnce(legacy).mockResolvedValueOnce(neutral);
  let finish!: (value: unknown) => void; probe.activate.mockReturnValue(new Promise(resolve => { finish = resolve; }));
  render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  fireEvent.click(await screen.findByRole('button', { name: '启用独立工作室…' }));
  const confirm = screen.getByRole('button', { name: '确认启用' });
  fireEvent.click(confirm); fireEvent.click(confirm);
  expect(probe.activate).toHaveBeenCalledTimes(1);
  await act(async () => finish({ project: neutral.project }));
  await screen.findByText('Original owner child');
  expect(probe.overview).toHaveBeenCalledTimes(2);
});
it('activation failure is shown and the owner panel stays unmounted', async () => {
  probe.overview.mockResolvedValue(legacy); probe.activate.mockRejectedValue(new Error('denied'));
  render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  fireEvent.click(await screen.findByRole('button', { name: '启用独立工作室…' }));
  fireEvent.click(screen.getByRole('button', { name: '确认启用' }));
  await screen.findByText(/启用失败/); expect(probe.child).toBeUndefined();
});
