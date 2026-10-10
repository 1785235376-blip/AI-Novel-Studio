import {describe,expect,it} from 'vitest';
import {selectedScopeLabels} from './scopeLabels';
const selected={workspaceId:'workspace-a',projectId:'project-a',storylineId:'storyline-alternate',branchId:'branch-draft-2'};
describe('selected owner labels',()=>{
  it('does not invent mainline or default-storyline names for a selected scope without metadata',()=>{
    expect(selectedScopeLabels(selected)).toEqual({workspace:'workspace-a',project:'project-a',storyline:'storyline-alternate',branch:'branch-draft-2'});
  });
  it('uses actual supplied names consistently for every module without changing IDs',()=>{
    const scope={...selected,workspaceName:'Writers',projectName:'Synthetic novel',storylineName:'Alternative',branchName:'Second draft'};
    expect(selectedScopeLabels(scope)).toEqual({workspace:'Writers',project:'Synthetic novel',storyline:'Alternative',branch:'Second draft'});expect(scope.branchId).toBe('branch-draft-2');
  });
  it('keeps distinct opaque IDs distinct and leaves absent owners unselected',()=>{
    expect(selectedScopeLabels({...selected,branchId:'owner:~a'}).branch).not.toBe(selectedScopeLabels({...selected,branchId:'owner:~b'}).branch);
    expect(selectedScopeLabels({...selected,projectId:'',storylineId:'',branchId:'',branchName:'Old branch'})).toEqual({workspace:'workspace-a',project:'',storyline:'',branch:''});
  });
  it('retains honest local manuscript labels only for actual local scope',()=>{
    expect(selectedScopeLabels(undefined,'Local draft')).toEqual({workspace:'本机作品',project:'Local draft',storyline:'默认故事线',branch:'主线'});
  });
});
