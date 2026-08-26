import {useState, type FormEvent} from 'react';
import {Badge, Button, EmptyState, Panel} from './ui/primitives';
import './permission-management.css';

export type PermissionModule = 'NOVEL' | 'IMAGE' | 'VIDEO';
export type AuthorityKind = 'ADMIN' | 'DOMAIN_LEAD' | 'DIRECT';

export interface PermissionScope {
  kind: 'GLOBAL' | 'WORKSPACE' | 'PROJECT' | 'STORYLINE' | 'BRANCH' | 'CHAPTER';
  id: string;
  label: string;
}

export interface PermissionSource {
  kind: 'DIRECT' | 'ROLE' | 'GROUP' | 'INHERITED';
  label: string;
}

export interface PermissionAssignment {
  id: string;
  principalLabel: string;
  authority: AuthorityKind;
  permissionLabel: string;
  module?: PermissionModule;
  scope: PermissionScope;
  source: PermissionSource;
  /** Authoritative backend decision. The UI must not infer revocation rights. */
  canRevoke: boolean;
}

export interface EffectivePermissionExplanation {
  id: string;
  permissionLabel: string;
  explanation: string;
  scopeLabel: string;
}

export interface PermissionGrantRequest {
  principalId: string;
  authority: AuthorityKind;
  module?: PermissionModule;
  scopeId: string;
}

export interface PermissionManagementProps {
  assignments: PermissionAssignment[];
  effectivePermissions: EffectivePermissionExplanation[];
  availableScopes: Array<{id: string; label: string}>;
  canGrant: boolean;
  readOnly?: boolean;
  loading?: boolean;
  denied?: boolean;
  error?: string;
  onGrant: (request: PermissionGrantRequest) => void | Promise<void>;
  onRevoke: (assignment: PermissionAssignment) => void | Promise<void>;
}

const moduleOptions: PermissionModule[] = ['NOVEL', 'IMAGE', 'VIDEO'];
const authorityLabels:Record<AuthorityKind,string>={ADMIN:'管理员',DOMAIN_LEAD:'小说负责人',DIRECT:'单独授权'};
const moduleLabels:Record<PermissionModule,string>={NOVEL:'小说',IMAGE:'图片',VIDEO:'视频'};

export function PermissionManagement({
  assignments,
  effectivePermissions,
  availableScopes,
  canGrant,
  readOnly = false,
  loading = false,
  denied = false,
  error,
  onGrant,
  onRevoke,
}: PermissionManagementProps) {
  const [principalId, setPrincipalId] = useState('');
  const [authority, setAuthority] = useState<AuthorityKind>('DIRECT');
  const [module, setModule] = useState<PermissionModule>('NOVEL');
  const [scopeId, setScopeId] = useState(availableScopes[0]?.id ?? '');
  const [confirmingRevoke, setConfirmingRevoke] = useState<string>();
  const [busy, setBusy] = useState(false);

  if (loading) return <div className="permission-state" role="status" aria-live="polite">正在加载权限...</div>;
  if (denied) return <div className="permission-state permission-state--denied" role="alert">你没有查看权限设置的权限。</div>;
  if (error) return <div className="permission-state permission-state--error" role="alert">权限设置加载失败<p>{error}</p></div>;

  const mutationDisabled = readOnly || busy;

  async function submitGrant(event: FormEvent) {
    event.preventDefault();
    if (!principalId || !scopeId || mutationDisabled || !canGrant) return;
    setBusy(true);
    try {
      await onGrant({principalId, authority, scopeId, ...(authority === 'ADMIN' ? {} : {module})});
      setPrincipalId('');
    } finally {
      setBusy(false);
    }
  }

  async function revoke(assignment: PermissionAssignment) {
    if (mutationDisabled || !assignment.canRevoke) return;
    if (assignment.authority === 'ADMIN' && confirmingRevoke !== assignment.id) {
      setConfirmingRevoke(assignment.id);
      return;
    }
    setBusy(true);
    try {
      await onRevoke(assignment);
      setConfirmingRevoke(undefined);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section className="permission-management" aria-labelledby="permission-management-title">
      <header className="permission-management__heading">
        <div>
          <h1 id="permission-management-title">权限设置</h1>
          <p>角色和单独授权由权限服务统一决定。</p>
        </div>
        {readOnly && <Badge tone="warning">只读</Badge>}
      </header>

      <Panel title="角色与单独授权">
        {assignments.length === 0 ? <EmptyState title="暂无授权记录" detail="当前范围内还没有角色或单独授权。" /> : (
          <ul className="permission-list" aria-label="授权记录">
            {assignments.map(assignment => {
              const confirming = confirmingRevoke === assignment.id;
              return <li key={assignment.id} className="permission-assignment">
                <div className="permission-assignment__summary">
                  <strong>{assignment.principalLabel}</strong>
                  <Badge tone={assignment.authority === 'ADMIN' ? 'warning' : 'info'}>{authorityLabels[assignment.authority]}</Badge>
                  {assignment.module && <Badge>{moduleLabels[assignment.module]}</Badge>}
                  <span>{assignment.permissionLabel}</span>
                </div>
                <dl className="permission-metadata">
                  <div><dt>适用范围</dt><dd>{assignment.scope.label}</dd></div>
                  <div><dt>权限来源</dt><dd>{assignment.source.label}</dd></div>
                </dl>
                <div className="permission-assignment__actions">
                  {confirming && <span role="alert">移除管理员角色可能影响创作空间管理，请再次确认。</span>}
                  <Button
                    variant={confirming ? 'danger' : 'secondary'}
                    disabled={mutationDisabled || !assignment.canRevoke}
                    onClick={() => void revoke(assignment)}
                  >{confirming ? '确认移除管理员' : '移除授权'}</Button>
                  {confirming && <Button variant="ghost" disabled={busy} onClick={() => setConfirmingRevoke(undefined)}>取消</Button>}
                </div>
              </li>;
            })}
          </ul>
        )}
      </Panel>

      <Panel title="当前有效权限">
        {effectivePermissions.length === 0 ? <EmptyState title="暂无权限说明" detail="权限服务尚未返回当前范围的权限说明。" /> : (
          <ul className="permission-explanations" aria-label="当前有效权限说明">
            {effectivePermissions.map(item => <li key={item.id}>
              <strong>{item.permissionLabel}</strong>
              <span>{item.scopeLabel}</span>
              <p>{item.explanation}</p>
            </li>)}
          </ul>
        )}
      </Panel>

      <Panel title="添加授权">
        <form className="permission-grant" onSubmit={event => void submitGrant(event)}>
          <label>成员标识<input value={principalId} onChange={event => setPrincipalId(event.target.value)} disabled={mutationDisabled || !canGrant} required /></label>
          <label>授权方式<select value={authority} onChange={event => setAuthority(event.target.value as AuthorityKind)} disabled={mutationDisabled || !canGrant}>
            <option value="DIRECT">单独授权</option><option value="DOMAIN_LEAD">小说负责人</option><option value="ADMIN">管理员</option>
          </select></label>
          <label>功能模块<select value={module} onChange={event => setModule(event.target.value as PermissionModule)} disabled={mutationDisabled || !canGrant || authority === 'ADMIN'}>{moduleOptions.map(value => <option key={value} value={value}>{moduleLabels[value]}</option>)}</select></label>
          <label>适用范围<select value={scopeId} onChange={event => setScopeId(event.target.value)} disabled={mutationDisabled || !canGrant} required>{availableScopes.map(scope => <option key={scope.id} value={scope.id}>{scope.label}</option>)}</select></label>
          <Button variant="primary" type="submit" disabled={mutationDisabled || !canGrant || !principalId || !scopeId}>{busy ? '保存中…' : '添加授权'}</Button>
          {!canGrant && <p role="status">你没有添加授权的权限。</p>}
        </form>
      </Panel>
    </section>
  );
}
