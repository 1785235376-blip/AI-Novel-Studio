// @vitest-environment jsdom
// [HERMIA-FE-20261031 VERA-P3] Vera 66f2f989 P3 for the activation entry: honest condition copy, focus after confirm,
// EN strings, accurate IMAGE copy. Child production UI is a stub; no execution or approval.
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { useStudio } from '../../store';
import { bindLocalHostSession, clearLocalHostSession } from '../../localHostSession';
import { setCollaborationContext } from '../../api';
import { RebuildFormalImageNode } from './RebuildFormalImageNode';
import { setLocale, translateZh } from '../../i18n';

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
afterEach(() => { act(() => setLocale('zh-CN')); cleanup(); clearLocalHostSession(); vi.restoreAllMocks(); });
const legacy = { ...overview, project: { ...overview.project, entry_kind: 'LEGACY' } };
const neutral = { ...overview, project: { ...overview.project, entry_kind: 'NEUTRAL_STUDIO' } };
const cjk = /[\u4e00-\u9fff]/;
async function toDialog(openName = '打开正式生成与服务端保存', entryName = '启用独立工作室…') {
  render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: openName }));
  fireEvent.click(await screen.findByRole('button', { name: entryName }));
  return screen.getByRole('dialog');
}
it('(a) copy states the real condition (overview says not activated), not a provider 422', async () => {
  probe.overview.mockResolvedValue(legacy);
  render(<RebuildFormalImageNode {...props} />);
  fireEvent.click(screen.getByRole('button', { name: '打开正式生成与服务端保存' }));
  await screen.findByRole('button', { name: '启用独立工作室…' });
  const block = document.querySelector('[data-studio-activation="required"]')!.textContent!;
  expect(block).not.toContain('服务端提示');
  expect(block).toContain('项目概览');
});
it('(b) focus after a successful confirm lands on the activation result, not BODY', async () => {
  probe.overview.mockResolvedValueOnce(legacy).mockResolvedValueOnce(neutral); probe.activate.mockResolvedValue({ project: neutral.project });
  await toDialog(); fireEvent.click(screen.getByRole('button', { name: '确认启用' }));
  await screen.findByText('Original owner child');
  expect(document.activeElement).not.toBe(document.body);
  expect(document.activeElement?.getAttribute('data-studio-activation')).toBe('done');
});
it('(b) focus after a failed confirm returns to the activation entry', async () => {
  probe.overview.mockResolvedValue(legacy); probe.activate.mockRejectedValue(new Error('denied'));
  await toDialog(); fireEvent.click(screen.getByRole('button', { name: '确认启用' }));
  await screen.findByText(/启用失败/);
  expect(document.activeElement).toBe(screen.getByRole('button', { name: '启用独立工作室…' }));
});
it('(d) dialog copy no longer claims the next open goes straight to the Studio shell', async () => {
  probe.overview.mockResolvedValue(legacy);
  const text = (await toDialog()).textContent!;
  expect(text).not.toContain('下次打开这个项目会直接进入工作室界面');
  expect(text).toContain('图片仍在当前图片页');
});
it('(c) EN: entry, dialog and formal section are English', async () => {
  act(() => setLocale('en')); probe.overview.mockResolvedValue(legacy);
  const dialog = await toDialog('Open formal generation and server save', 'Enable independent Studio…');
  expect(cjk.test(dialog.textContent!), dialog.textContent!).toBe(false);
  const section = screen.getByRole('region', { name: 'Formal production and server save for the selected node' });
  expect(cjk.test(section.textContent!), section.textContent!).toBe(false);
  expect(screen.getByRole('button', { name: 'Confirm and enable' })).toBeTruthy();
  expect(screen.getByRole('button', { name: 'Cancel' })).toBeTruthy();
});
it('(c) EN: formal image node task static copy has English entries', () => {
  for (const s of ['正式图片节点任务', '关闭正式节点任务', '为此节点保存正式空白位置', '重新核对此次空白位置创建', '核对原图片任务入队结果',
    '读取此节点已保存位置与任务', '原位置请求 ID：', '查看已保存节点位置', '打开原正式节点任务', '采用到原节点作品位置',
    '核对正式结果与原节点位置', '确认采用此正式资产到原节点位置', '确认采用并保存节点位置', '节点', '坐标',
    '先显式保存空白作品位置，再分别预览、入队、执行和人工审核。审核成功后还需单独确认采用；不兼容的旧队列结果不会变成正式来源。',
    '原生产 owner 已记录人工审核。这里重新核对来源元数据，不代替候选预览或审核；保存后固定回到原节点坐标。',
    '操作结果待核对。当前实例只可读取，不会自动重发；原输入与请求 ID 保留。',
    '原身份、权限或节点已改变。请取消选择后重新选择节点并打开入口；旧确认不会恢复。']) {
    const out = translateZh('en', s); expect(cjk.test(out), `${s} -> ${out}`).toBe(false);
  }
});
