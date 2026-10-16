// @vitest-environment jsdom
// Exercise the original host/Canvas contract. Only the independent production
// child is replaced to deliver its dirty callback; this is not browser evidence.
import { act, cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { StoryboardProductionProps } from './useStoryboardProductionController';
import { CreativeWorkspace } from './CreativeWorkspace';
import { newDocument } from './types';
const held = vi.hoisted(() => ({ props: undefined as StoryboardProductionProps | undefined }));
vi.mock('./StoryboardProductionPanel', () => ({ StoryboardProductionPanel: (props: StoryboardProductionProps) => { held.props = props; return null; } }));
afterEach(() => { cleanup(); held.props = undefined; vi.unstubAllGlobals(); });
it('keeps real production dirty protection without labelling an unsubmitted production draft as saving', async () => {
  const document = { ...newDocument('STORYBOARD'), id: 'board', title: 'Saved board', version: 1, status: 'DRAFT', actor_id: 'author', created_at: '', updated_at: '', source_evidence: {} };
  vi.stubGlobal('fetch', vi.fn(async (url: string) => {
    const body = url.endsWith('/capabilities') ? { enabled: true, can_mutate: true, modes: ['STORYBOARD'] } : url.endsWith('/documents') ? { items: [document] } : url.endsWith('/creation-reference-data') ? { characters: [], locations: [], story_routes: [] } : url.endsWith('/assets') ? [] : url.endsWith('/director-proposals') || url.endsWith('/model-routes') ? { items: [] } : undefined;
    return new Response(JSON.stringify(body ?? { code: 'NOT_CONFIGURED' }), { status: body === undefined ? 404 : 200 });
  }));
  const onExit = vi.fn();
  render(<CreativeWorkspace enabled novelId="project" context={{ sessionToken: 'session', actor: { id: 'author', displayName: 'Author', workspaceId: 'workspace' } }} scope={{ workspace: 'Workspace', project: 'Project', storyline: 'Story', branch: 'Branch' }} actor="Author" chapterCount={0} manuscriptReady={false} novelMain={null} novelSidebar={null} novelInspector={null} novelStatus={null} onExit={onExit} onModuleChange={vi.fn()} />);
  await waitFor(() => expect(screen.queryByText('正在核对创作文档与权限…')).toBeNull());
  const stages = within(screen.getByRole('tablist', { name: '创作模式' }));
  fireEvent.click(stages.getByRole('tab', { name: /Storyboard/ })); await screen.findByLabelText('文档标题');
  act(() => held.props!.onDirtyChange(true));
  expect((screen.getByRole('button', { name: '保存草稿' }) as HTMLButtonElement).disabled).toBe(true);
  expect(screen.queryByRole('button', { name: '保存中…' })).toBeNull();
  expect(screen.getByRole('status', { name: '当前创作文档保存状态' }).textContent).toBe('当前分镜：已保存 · v1');
  expect(screen.getByLabelText('其他创作草稿状态').textContent).toContain('制作草稿待处理');
  const unload = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(unload); expect(unload.defaultPrevented).toBe(true);
  fireEvent.click(stages.getByRole('tab', { name: /Novel/ }));
  fireEvent.click(screen.getByRole('button', { name: '返回经典工作区' }));
  expect(stages.getByRole('tab', { name: /Storyboard/ }).getAttribute('aria-selected')).toBe('true'); expect(onExit).not.toHaveBeenCalled();
  act(() => held.props!.onDirtyChange(false));
  expect(screen.queryByLabelText('其他创作草稿状态')).toBeNull();
  const cleanUnload = new Event('beforeunload', { cancelable: true }); window.dispatchEvent(cleanUnload); expect(cleanUnload.defaultPrevented).toBe(false);
});
