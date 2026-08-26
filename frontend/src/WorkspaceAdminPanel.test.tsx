// @vitest-environment jsdom
import {act} from 'react';
import {createRoot, type Root} from 'react-dom/client';
import {QueryClient, QueryClientProvider} from '@tanstack/react-query';
import {afterEach, describe, expect, it, vi} from 'vitest';
import {WorkspaceAdminPanel} from './CollaborationPanels';
import {api, type Scope} from './api';
import {useStudio} from './store';

(globalThis as {IS_REACT_ACT_ENVIRONMENT?: boolean}).IS_REACT_ACT_ENVIRONMENT = true;

const scopeA: Scope = {workspaceId:'workspace-a',projectId:'project-a',storylineId:'story-a',branchId:'branch-a'};
const actor = {id:'actor-1',displayName:'Owner',workspaceId:'workspace-a'};
let host: HTMLDivElement;
let root: Root;
let client: QueryClient;

function Harness({dirty=false, conflict=false}:{dirty?:boolean;conflict?:boolean}) {
  const scope=useStudio(state=>state.scope);
  return <WorkspaceAdminPanel scope={scope} hasUnsavedChanges={dirty} hasConflict={conflict}/>;
}

async function render(props:{dirty?:boolean;conflict?:boolean}={}) {
  localStorage.clear();
  useStudio.setState({sessionToken:'trusted-session',actor,scope:scopeA,novelId:'project-a',chapterId:'chapter-a'});
  client=new QueryClient({defaultOptions:{queries:{retry:false,gcTime:Infinity}}});
  host=document.createElement('div');document.body.append(host);root=createRoot(host);
  await act(async()=>{root.render(<QueryClientProvider client={client}><Harness {...props}/></QueryClientProvider>);await Promise.resolve()});
  for(let i=0;i<30&&!host.textContent?.includes('Workspace B');i++)await act(async()=>{await new Promise(resolve=>setTimeout(resolve,0))});
}

function switchButton(){return [...host.querySelectorAll<HTMLButtonElement>('button')].find(button=>button.textContent?.includes('Workspace B'))!}
function button(label:string){return [...host.querySelectorAll<HTMLButtonElement>('button')].find(candidate=>candidate.textContent?.includes(label))!}

afterEach(()=>{vi.restoreAllMocks();if(root)act(()=>root.unmount());host?.remove()});

describe('WorkspaceAdminPanel production workspace switch',()=>{
  it('creates a workspace through the trusted admin API and refreshes the workspace cache',async()=>{
    vi.spyOn(api,'adminWorkspaces').mockResolvedValue([{id:'workspace-a',name:'Workspace A'}]);
    vi.spyOn(api,'adminMembers').mockResolvedValue([]);
    const create=vi.spyOn(api,'adminCreateWorkspace').mockResolvedValue({id:'workspace-new',name:'Workspace New'});
    await render();
    const invalidated=vi.spyOn(client,'invalidateQueries');
    await act(async()=>button('新建').click());
    const input=host.querySelector<HTMLInputElement>('input[name="value"]')!;
    await act(async()=>{input.value='Workspace New';input.dispatchEvent(new Event('input',{bubbles:true}));});
    await act(async()=>{host.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await Promise.resolve();});
    expect(create).toHaveBeenCalledWith(expect.stringMatching(/^workspace-/),'Workspace New');
    expect(create.mock.calls[0]).toHaveLength(2);
    expect(invalidated).toHaveBeenCalledWith({queryKey:['admin-workspaces']});
  });

  it('renames the current workspace through the trusted admin API and refreshes the workspace cache',async()=>{
    vi.spyOn(api,'adminWorkspaces').mockResolvedValue([{id:'workspace-a',name:'Workspace A'}]);
    vi.spyOn(api,'adminMembers').mockResolvedValue([]);
    const rename=vi.spyOn(api,'adminRenameWorkspace').mockResolvedValue({id:'workspace-a',name:'Renamed'});
    await render();
    const invalidated=vi.spyOn(client,'invalidateQueries');
    await act(async()=>button('重命名').click());
    const input=host.querySelector<HTMLInputElement>('input[name="value"]')!;
    await act(async()=>{input.value='Renamed';input.dispatchEvent(new Event('input',{bubbles:true}));});
    await act(async()=>{host.querySelector<HTMLFormElement>('form')!.dispatchEvent(new Event('submit',{bubbles:true,cancelable:true}));await Promise.resolve();});
    expect(rename).toHaveBeenCalledWith('workspace-a','Renamed');
    expect(rename.mock.calls[0]).toHaveLength(2);
    expect(invalidated).toHaveBeenCalledWith({queryKey:['admin-workspaces']});
  });

  it('clears stale children, uses only the backend default path, refreshes scoped authority, and preserves the trusted actor',async()=>{
    vi.spyOn(api,'adminWorkspaces').mockResolvedValue([{id:'workspace-a',name:'Workspace A'},{id:'workspace-b',name:'Workspace B'}]);
    const members=vi.spyOn(api,'adminMembers').mockResolvedValue([]);
    vi.spyOn(api,'adminWorkspaceNavigation').mockResolvedValue({workspace_id:'workspace-b',eligible_paths:[{workspace_id:'workspace-b',project_id:'first-project',storyline_id:'first-story',branch_id:'first-branch'}],default_path:{workspace_id:'workspace-b',project_id:'project-b',storyline_id:'story-b',branch_id:'branch-b'}});
    await render();
    const invalidated=vi.spyOn(client,'invalidateQueries');
    await act(async()=>switchButton().click());
    expect(useStudio.getState().scope).toEqual({workspaceId:'workspace-b',projectId:'project-b',storylineId:'story-b',branchId:'branch-b'});
    expect(useStudio.getState().scope?.projectId).not.toBe('first-project');
    expect(useStudio.getState().chapterId).toBe('');
    expect(useStudio.getState().actor).toEqual(actor);
    expect(members).toHaveBeenCalledWith('workspace-b');
    expect(invalidated.mock.calls.some(([arg])=>JSON.stringify(arg).includes('admin-members'))).toBe(true);
    expect(invalidated.mock.calls.some(([arg])=>JSON.stringify(arg).includes('bootstrap'))).toBe(true);
    expect(invalidated.mock.calls.some(([arg])=>JSON.stringify(arg).includes('collaboration'))).toBe(true);
  });

  it('represents an empty workspace with NONE child scope and never selects the first eligible child',async()=>{
    vi.spyOn(api,'adminWorkspaces').mockResolvedValue([{id:'workspace-a',name:'Workspace A'},{id:'workspace-b',name:'Workspace B'}]);
    vi.spyOn(api,'adminMembers').mockResolvedValue([]);
    vi.spyOn(api,'adminWorkspaceNavigation').mockResolvedValue({workspace_id:'workspace-b',eligible_paths:[{workspace_id:'workspace-b',project_id:'first-project',storyline_id:'first-story',branch_id:'first-branch'}],default_path:null});
    await render();
    await act(async()=>switchButton().click());
    expect(useStudio.getState().scope).toEqual({workspaceId:'workspace-b',projectId:'',storylineId:'',branchId:''});
    expect(useStudio.getState().novelId).toBe('');
    expect(useStudio.getState().chapterId).toBe('');
  });

  it.each([{dirty:true,conflict:false},{dirty:false,conflict:true}])('fails closed before navigation for dirty/conflict state %#',async flags=>{
    vi.spyOn(api,'adminWorkspaces').mockResolvedValue([{id:'workspace-a',name:'Workspace A'},{id:'workspace-b',name:'Workspace B'}]);
    vi.spyOn(api,'adminMembers').mockResolvedValue([]);
    const navigation=vi.spyOn(api,'adminWorkspaceNavigation');
    await render(flags);
    await act(async()=>switchButton().click());
    expect(navigation).not.toHaveBeenCalled();
    expect(useStudio.getState().scope).toEqual(scopeA);
    expect(useStudio.getState().chapterId).toBe('chapter-a');
  });
});
