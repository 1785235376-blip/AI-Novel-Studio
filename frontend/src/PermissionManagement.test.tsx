// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {PermissionManagement, type PermissionAssignment} from './PermissionManagement';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;

const admin: PermissionAssignment = {id:'a1',principalLabel:'Lin',authority:'ADMIN',permissionLabel:'Full administration',scope:{kind:'WORKSPACE',id:'w1',label:'Studio'},source:{kind:'DIRECT',label:'Assigned by owner'},canRevoke:true};
const lead: PermissionAssignment = {id:'a2',principalLabel:'Zhou',authority:'DOMAIN_LEAD',module:'IMAGE',permissionLabel:'Manage image domain',scope:{kind:'PROJECT',id:'p1',label:'Novel A'},source:{kind:'ROLE',label:'Image lead'},canRevoke:false};
let host: HTMLDivElement; let root: Root;
function render(overrides: Partial<React.ComponentProps<typeof PermissionManagement>> = {}) {
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
  act(()=>root.render(<PermissionManagement assignments={[admin,lead]} effectivePermissions={[{id:'e1',permissionLabel:'Edit chapter',scopeLabel:'Chapter 1',explanation:'Granted by the backend through Project Editor.'}]} availableScopes={[{id:'w1',label:'Studio'}]} canGrant onGrant={vi.fn()} onRevoke={vi.fn()} {...overrides}/>));
}
afterEach(()=>{if(root)act(()=>root.unmount());host?.remove()});

describe('PermissionManagement',()=>{
  it('renders backend-supplied scope, source, module and effective explanation without deriving access',()=>{render();expect(host.textContent).toContain('管理员');expect(host.textContent).toContain('小说负责人');expect(host.textContent).toContain('图片');expect(host.textContent).toContain('Assigned by owner');expect(host.textContent).toContain('Granted by the backend through Project Editor.');const revoke=[...host.querySelectorAll<HTMLButtonElement>('button')].filter(button=>button.textContent==='移除授权');expect(revoke[0].disabled).toBe(false);expect(revoke[1].disabled).toBe(true)});
  it('requires a second explicit action before revoking ADMIN',async()=>{const onRevoke=vi.fn();render({onRevoke});const revoke=[...host.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent==='移除授权')!;act(()=>revoke.click());expect(onRevoke).not.toHaveBeenCalled();expect(host.querySelector('[role="alert"]')?.textContent).toContain('移除管理员角色');const confirm=[...host.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent==='确认移除管理员')!;await act(async()=>confirm.click());expect(onRevoke).toHaveBeenCalledWith(admin)});
  it('honors denied, loading, error, read-only and backend canGrant states',()=>{render({loading:true});expect(host.querySelector('[role="status"]')).not.toBeNull();act(()=>root.render(<PermissionManagement assignments={[]} effectivePermissions={[]} availableScopes={[]} canGrant={false} denied onGrant={vi.fn()} onRevoke={vi.fn()}/>));expect(host.querySelector('[role="alert"]')?.textContent).toContain('没有查看权限设置的权限');act(()=>root.render(<PermissionManagement assignments={[]} effectivePermissions={[]} availableScopes={[]} canGrant={false} error="offline" onGrant={vi.fn()} onRevoke={vi.fn()}/>));expect(host.querySelector('[role="alert"]')?.textContent).toContain('offline');act(()=>root.render(<PermissionManagement assignments={[admin]} effectivePermissions={[]} availableScopes={[{id:'w1',label:'Studio'}]} canGrant={false} readOnly onGrant={vi.fn()} onRevoke={vi.fn()}/>));expect([...host.querySelectorAll<HTMLButtonElement>('button')].every(button=>button.disabled)).toBe(true)});
});
