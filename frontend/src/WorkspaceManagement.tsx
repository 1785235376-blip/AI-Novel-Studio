import {useId, useState, type FormEvent} from 'react';
import {AlertTriangle, Check, ChevronRight, Pencil, Plus, UserMinus, Users} from 'lucide-react';
import {Badge, Button, EmptyState, Panel} from './ui/primitives';
import './workspace-management.css';

export type WorkspaceSummary = {
  id: string;
  name: string;
  memberCount?: number;
  accessLabel?: string;
};

export type WorkspaceMember = {
  id: string;
  userId: string;
  displayName: string;
  email?: string;
  roleLabel: string;
  statusLabel?: string;
  isCurrentActor?: boolean;
};

export type WorkspaceScope = {
  workspaceId: string;
  projectId?: string;
  storylineId?: string;
  branchId?: string;
  chapterId?: string;
  projectLabel?: string;
  storylineLabel?: string;
  branchLabel?: string;
  chapterLabel?: string;
};

export type WorkspaceSwitchRequest = {
  workspace: WorkspaceSummary;
  hasUnsavedChanges: boolean;
  hasConflict: boolean;
};

export type WorkspaceManagementProps = {
  workspaces: WorkspaceSummary[];
  currentWorkspaceId?: string;
  members: WorkspaceMember[];
  selectedMemberId?: string;
  actorLabel: string;
  scope?: WorkspaceScope;
  loading?: boolean;
  error?: string;
  denied?: boolean;
  readOnly?: boolean;
  hasUnsavedChanges?: boolean;
  hasConflict?: boolean;
  onRequestWorkspaceSwitch: (request: WorkspaceSwitchRequest) => void;
  onSelectMember?: (memberId: string) => void;
  onCreateWorkspace?: (name: string) => void | Promise<void>;
  onRenameWorkspace?: (workspaceId: string, name: string) => void | Promise<void>;
  onAddExistingUser?: (userIdentifier: string) => void | Promise<void>;
  onRemoveMember?: (memberId: string) => void | Promise<void>;
};

type AsyncAction = () => void | Promise<void>;

export function WorkspaceManagement(props: WorkspaceManagementProps) {
  const {
    workspaces, currentWorkspaceId, members, selectedMemberId, actorLabel, scope,
    loading = false, error, denied = false, readOnly = false,
    hasUnsavedChanges = false, hasConflict = false,
    onRequestWorkspaceSwitch, onSelectMember, onCreateWorkspace, onRenameWorkspace,
    onAddExistingUser, onRemoveMember,
  } = props;
  const [createOpen, setCreateOpen] = useState(false);
  const [renameOpen, setRenameOpen] = useState(false);
  const [addOpen, setAddOpen] = useState(false);
  const [removeTarget, setRemoveTarget] = useState<WorkspaceMember>();
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string>();
  const createId = useId();
  const renameId = useId();
  const userId = useId();
  const currentWorkspace = workspaces.find(item => item.id === currentWorkspaceId);
  const selectedMember = members.find(item => item.id === selectedMemberId);
  const locked = readOnly || pending;

  async function run(action: AsyncAction, onSuccess: () => void) {
    setPending(true);
    setActionError(undefined);
    try {
      await action();
      onSuccess();
    } catch (reason) {
      setActionError(reason instanceof Error ? reason.message : '操作失败，请重试。');
    } finally {
      setPending(false);
    }
  }

  function submitValue(event: FormEvent<HTMLFormElement>, action: (value: string) => void | Promise<void>, onSuccess: () => void) {
    event.preventDefault();
    const form = new FormData(event.currentTarget);
    const value = String(form.get('value') ?? '').trim();
    if (!value) return;
    void run(() => action(value), onSuccess);
  }

  if (loading) return <section className="workspace-management state-surface" role="status" aria-live="polite">正在加载创作空间与成员…</section>;
  if (denied) return <section className="workspace-management state-surface state-surface--error" role="alert"><strong>无权查看创作空间管理</strong><p>权限由服务端决定。请联系创作空间管理员。</p></section>;
  if (error) return <section className="workspace-management state-surface state-surface--error" role="alert"><strong>创作空间数据加载失败</strong><p>{error}</p></section>;

  return <section className="workspace-management" aria-labelledby="workspace-management-title">
    <header className="workspace-management__header">
      <div>
        <h1 id="workspace-management-title">创作空间与团队</h1>
        <p>查看共享范围和已有成员。成员与权限变更以服务端结果为准。</p>
      </div>
      {readOnly && <Badge tone="warning">只读</Badge>}
    </header>

    <aside className="workspace-management__sidebar" aria-label="创作空间列表">
      <div className="section-heading">
        <h2>创作空间</h2>
        {onCreateWorkspace && <Button type="button" variant="ghost" disabled={locked} onClick={() => setCreateOpen(value => !value)}><Plus aria-hidden="true"/>新建</Button>}
      </div>
      {createOpen && onCreateWorkspace && <form className="compact-form" onSubmit={event => submitValue(event, onCreateWorkspace, () => setCreateOpen(false))}>
        <label htmlFor={createId}>创作空间名称</label>
        <input id={createId} name="value" autoFocus disabled={pending} required/>
        <div className="form-actions"><Button type="submit" variant="primary" disabled={pending}>创建</Button><Button type="button" variant="ghost" onClick={() => setCreateOpen(false)}>取消</Button></div>
      </form>}
      {workspaces.length === 0 ? <EmptyState title="暂无创作空间" detail={readOnly ? '当前没有可查看的创作空间。' : '使用现有创建操作开始。'}/> :
        <nav className="workspace-list" aria-label="可用创作空间">
          {workspaces.map(workspace => {
            const active = workspace.id === currentWorkspaceId;
            return <button key={workspace.id} type="button" className={active ? 'workspace-list__item is-active' : 'workspace-list__item'} aria-current={active ? 'page' : undefined} onClick={() => !active && onRequestWorkspaceSwitch({workspace, hasUnsavedChanges, hasConflict})}>
              <span><strong>{workspace.name}</strong>{workspace.accessLabel && <small>{workspace.accessLabel}</small>}</span>
              <span className="workspace-list__meta">{workspace.memberCount !== undefined && `${workspace.memberCount} 人`}{active ? <Check aria-label="当前创作空间"/> : <ChevronRight aria-hidden="true"/>}</span>
            </button>;
          })}
        </nav>}
      {(hasUnsavedChanges || hasConflict) && <div className="switch-warning" role="status"><AlertTriangle aria-hidden="true"/><span>{hasConflict ? '当前章节存在未解决冲突。' : '当前章节有未保存更改。'}切换前将由上层流程确认处理方式。</span></div>}
    </aside>

    <main className="workspace-management__main">
      <Panel title="当前协作范围" actions={currentWorkspace && onRenameWorkspace ? <Button type="button" variant="ghost" disabled={locked} onClick={() => setRenameOpen(value => !value)}><Pencil aria-hidden="true"/>重命名</Button> : undefined}>
        <dl className="scope-grid">
          <div><dt>当前用户</dt><dd>{actorLabel}</dd></div>
          <div><dt>创作空间</dt><dd>{currentWorkspace?.name ?? '未选择'}</dd></div>
          <div><dt>小说</dt><dd>{scope?.projectId ? scope.projectLabel ?? '当前小说' : '未选择'}</dd></div>
          <div><dt>故事线 / 创作分支</dt><dd>{scope?.storylineId || scope?.branchId ? [scope.storylineLabel ?? '当前故事线', scope.branchLabel ?? '当前创作分支'].join(' / ') : '未选择'}</dd></div>
          <div><dt>章节</dt><dd>{scope?.chapterId ? scope.chapterLabel ?? '当前章节' : '未选择'}</dd></div>
        </dl>
        {renameOpen && currentWorkspace && onRenameWorkspace && <form className="compact-form compact-form--inline" onSubmit={event => submitValue(event, value => onRenameWorkspace(currentWorkspace.id, value), () => setRenameOpen(false))}>
          <label htmlFor={renameId}>新的创作空间名称</label>
          <input id={renameId} name="value" defaultValue={currentWorkspace.name} autoFocus disabled={pending} required/>
          <div className="form-actions"><Button type="submit" variant="primary" disabled={pending}>保存名称</Button><Button type="button" variant="ghost" onClick={() => setRenameOpen(false)}>取消</Button></div>
        </form>}
      </Panel>

      <Panel title={<span className="title-with-icon"><Users aria-hidden="true"/>成员</span>} actions={onAddExistingUser ? <Button type="button" variant="secondary" disabled={locked || !currentWorkspaceId} onClick={() => setAddOpen(value => !value)}><Plus aria-hidden="true"/>添加已有用户</Button> : undefined}>
        {addOpen && onAddExistingUser && <form className="compact-form" onSubmit={event => submitValue(event, onAddExistingUser, () => setAddOpen(false))}>
          <label htmlFor={userId}>已有用户 ID 或邮箱</label>
          <input id={userId} name="value" autoComplete="off" aria-describedby={`${userId}-help`} autoFocus disabled={pending} required/>
          <small id={`${userId}-help`}>只添加系统中已存在的用户；此处不会发送邀请或创建账号。</small>
          <div className="form-actions"><Button type="submit" variant="primary" disabled={pending}>添加用户</Button><Button type="button" variant="ghost" onClick={() => setAddOpen(false)}>取消</Button></div>
        </form>}
        {members.length === 0 ? <EmptyState title="暂无成员" detail="当前创作空间还没有可显示的成员。"/> : <div className="member-layout">
          <ul className="member-list" aria-label="创作空间成员">
            {members.map(member => <li key={member.id}><button type="button" className={member.id === selectedMemberId ? 'member-item is-active' : 'member-item'} aria-pressed={member.id === selectedMemberId} onClick={() => onSelectMember?.(member.id)}>
              <span><strong>{member.displayName || '成员'}</strong>{member.email && <small>{member.email}</small>}</span>
              <span>{member.isCurrentActor && <Badge tone="info">当前用户</Badge>}<small>{member.roleLabel}</small></span>
            </button></li>)}
          </ul>
          <section className="member-detail" aria-live="polite" aria-label="成员详情">
            {selectedMember ? <>
              <div className="member-detail__heading"><div><h3>{selectedMember.displayName || '成员'}</h3>{selectedMember.email && <p>{selectedMember.email}</p>}</div>{selectedMember.statusLabel && <Badge tone="neutral">{selectedMember.statusLabel}</Badge>}</div>
              <dl><div><dt>成员职责</dt><dd>{selectedMember.roleLabel}</dd></div></dl>
              {onRemoveMember && <Button type="button" variant="danger" disabled={locked || selectedMember.isCurrentActor} onClick={() => setRemoveTarget(selectedMember)}><UserMinus aria-hidden="true"/>移除成员</Button>}
            </> : <EmptyState title="选择一名成员" detail="查看服务端返回的成员身份与角色。"/>}
          </section>
        </div>}
      </Panel>
      {actionError && <p className="action-error" role="alert">{actionError}</p>}
    </main>

    {removeTarget && onRemoveMember && <div className="confirm-layer" role="presentation">
      <section className="confirm-dialog" role="alertdialog" aria-modal="true" aria-labelledby="remove-member-title" aria-describedby="remove-member-detail">
        <h2 id="remove-member-title">确认移除成员？</h2>
        <p id="remove-member-detail">将从当前创作空间移除“{removeTarget.displayName}”。最终授权结果由服务端决定，此操作不会删除用户账号。</p>
        <div className="form-actions"><Button type="button" variant="danger" autoFocus disabled={pending} onClick={() => void run(() => onRemoveMember(removeTarget.id), () => setRemoveTarget(undefined))}>确认移除</Button><Button type="button" variant="secondary" disabled={pending} onClick={() => setRemoveTarget(undefined)}>取消</Button></div>
      </section>
    </div>}
  </section>;
}
