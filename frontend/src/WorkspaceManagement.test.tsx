// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {WorkspaceManagement, type WorkspaceManagementProps} from './WorkspaceManagement';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;

const base: WorkspaceManagementProps = {
  workspaces: [{id: 'w1', name: '星海工作室', memberCount: 2, accessLabel: '编辑者'}, {id: 'w2', name: '第二工作区'}],
  currentWorkspaceId: 'w1',
  members: [
    {id: 'm1', userId: 'user-a', displayName: '林岚', email: 'lin@example.test', roleLabel: 'Owner', isCurrentActor: true},
    {id: 'm2', userId: 'user-b', displayName: '周明', roleLabel: 'Editor'},
  ],
  selectedMemberId: 'm2',
  actorLabel: '林岚',
  scope: {workspaceId: 'w1', projectId: 'p1', storylineId: 's1', branchId: 'b1', chapterId: 'c1', projectLabel: '星海纪事', storylineLabel: '主故事线', branchLabel: '正式线', chapterLabel: '第三章'},
  onRequestWorkspaceSwitch: vi.fn(),
};

let host: HTMLDivElement | undefined;
let root: Root | undefined;
function render(overrides: Partial<WorkspaceManagementProps> = {}) {
  host = document.createElement('div');
  document.body.append(host);
  root = createRoot(host);
  act(() => root!.render(<WorkspaceManagement {...base} {...overrides}/>));
}
afterEach(() => { if (root) act(() => root!.unmount()); host?.remove(); root = undefined; host = undefined; });

describe('WorkspaceManagement', () => {
  it('shows the current actor, authoritative scope, members, and read-only state', () => {
    render({readOnly: true});
    expect(host!.textContent).toContain('林岚');
    expect(host!.textContent).toContain('主故事线 / 正式线');
    expect(host!.textContent).toContain('星海纪事');
    expect(host!.textContent).not.toContain('p1');
    expect(host!.textContent).not.toContain('user-b');
    expect(host!.textContent).toContain('周明');
    expect(host!.textContent).toContain('只读');
  });

  it('delegates a risky workspace switch without discarding dirty or conflict state', () => {
    const onRequestWorkspaceSwitch = vi.fn();
    render({onRequestWorkspaceSwitch, hasUnsavedChanges: true, hasConflict: true});
    const target = [...host!.querySelectorAll('button')].find(button => button.textContent?.includes('第二工作区'))!;
    act(() => target.click());
    expect(onRequestWorkspaceSwitch).toHaveBeenCalledWith({workspace: base.workspaces[1], hasUnsavedChanges: true, hasConflict: true});
    expect(host!.textContent).toContain('未解决冲突');
  });

  it('uses an honest add-existing-user flow', async () => {
    const onAddExistingUser = vi.fn().mockResolvedValue(undefined);
    render({onAddExistingUser});
    act(() => ([...host!.querySelectorAll('button')].find(button => button.textContent?.includes('添加已有用户'))!).click());
    expect(host!.textContent).toContain('不会发送邀请或创建账号');
    const input = host!.querySelector<HTMLInputElement>('input[name="value"]')!;
    act(() => { input.value = 'existing@example.test'; input.dispatchEvent(new Event('input', {bubbles: true})); });
    await act(async () => host!.querySelector('form')!.dispatchEvent(new Event('submit', {bubbles: true, cancelable: true})));
    expect(onAddExistingUser).toHaveBeenCalledWith('existing@example.test');
  });

  it('requires explicit confirmation before removing a member', async () => {
    const onRemoveMember = vi.fn().mockResolvedValue(undefined);
    render({onRemoveMember});
    act(() => ([...host!.querySelectorAll('button')].find(button => button.textContent?.includes('移除成员'))!).click());
    expect(host!.querySelector('[role="alertdialog"]')?.textContent).toContain('不会删除用户账号');
    expect(onRemoveMember).not.toHaveBeenCalled();
    await act(async () => ([...host!.querySelectorAll('button')].find(button => button.textContent === '确认移除')!).click());
    expect(onRemoveMember).toHaveBeenCalledWith('m2');
  });

  it('covers loading, denied, error, and empty states', () => {
    render({loading: true});
    expect(host!.querySelector('[role="status"]')?.textContent).toContain('正在加载');
    act(() => root!.render(<WorkspaceManagement {...base} loading={false} denied/>));
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain('无权查看');
    act(() => root!.render(<WorkspaceManagement {...base} error="连接失败"/>));
    expect(host!.querySelector('[role="alert"]')?.textContent).toContain('连接失败');
    act(() => root!.render(<WorkspaceManagement {...base} workspaces={[]} members={[]}/>));
    expect(host!.textContent).toContain('暂无创作空间');
    expect(host!.textContent).toContain('暂无成员');
  });
});
