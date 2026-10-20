// @vitest-environment jsdom
import {afterEach,expect,it,vi} from 'vitest';
import {act,cleanup,render,screen,waitFor} from '@testing-library/react';
import {WorkflowPanel} from './WorkflowPanel';
import {api} from '../api';
vi.mock('../api',()=>({api:{workflows:vi.fn(),workflowRuns:vi.fn()}}));
vi.mock('../store',()=>({useStudio:(select:any)=>select({scope:{branchId:'branch'}})}));
afterEach(cleanup);
it('discard old-project workflow response after changing projects',async()=>{
 let finish:(value:any)=>void=()=>{};
 vi.mocked(api.workflows).mockImplementation((nid)=>nid==='project-a'?new Promise(resolve=>{finish=resolve}):Promise.resolve({items:[]}));
 const view=render(<WorkflowPanel novelId="project-a"/>);
 await waitFor(()=>expect(api.workflows).toHaveBeenCalledWith('project-a'));
 view.rerender(<WorkflowPanel novelId="project-b"/>);
 await waitFor(()=>expect(api.workflows).toHaveBeenCalledWith('project-b'));
 await act(async()=>finish({items:[{id:'private-a',title:'PRIVATE_PROJECT_A_WORKFLOW',nodes:[]}]}));
 expect(screen.queryByText(/PRIVATE_PROJECT_A_WORKFLOW/)).toBeNull();
});
