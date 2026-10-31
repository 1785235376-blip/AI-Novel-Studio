import {describe,expect,it} from 'vitest';
import {selectedScopeLabels} from './scopeLabels';
// [HERMIA-FE-20261025 DUI P0-1] Spec change: unnamed selected owners show a human placeholder, never the opaque ID;
// IDs (and their distinctness) move to `ids`, which ContextBar renders only as data-scope-id.
const selected={workspaceId:'workspace-a',projectId:'project-a',storylineId:'storyline-alternate',branchId:'branch-draft-2'};
describe('selected owner labels',()=>{
  it('does not invent mainline or default-storyline names for a selected scope without metadata',()=>{
    const l=selectedScopeLabels(selected);
    expect(l).toMatchObject({workspace:'已选创作空间（未命名）',project:'已选作品（未命名）',storyline:'已选故事线（未命名）',branch:'已选分支（未命名）'});
    expect(l.ids).toEqual({workspace:'workspace-a',project:'project-a',storyline:'storyline-alternate',branch:'branch-draft-2'});
    expect(JSON.stringify([l.workspace,l.project,l.storyline,l.branch])).not.toMatch(/workspace-a|project-a|storyline-alternate|branch-draft-2|主线|默认故事线/);
  });
  it('uses actual supplied names consistently for every module without changing IDs',()=>{
    const scope={...selected,workspaceName:'Writers',projectName:'Synthetic novel',storylineName:'Alternative',branchName:'Second draft'};
    expect(selectedScopeLabels(scope)).toMatchObject({workspace:'Writers',project:'Synthetic novel',storyline:'Alternative',branch:'Second draft'});expect(scope.branchId).toBe('branch-draft-2');
  });
  it('keeps distinct opaque IDs distinct and leaves absent owners unselected',()=>{
    expect(selectedScopeLabels({...selected,branchId:'owner:~a'}).ids?.branch).not.toBe(selectedScopeLabels({...selected,branchId:'owner:~b'}).ids?.branch);
    expect(selectedScopeLabels({...selected,projectId:'',storylineId:'',branchId:'',branchName:'Old branch'})).toMatchObject({workspace:'已选创作空间（未命名）',project:'',storyline:'',branch:''});
  });
  it('retains honest local manuscript labels only for actual local scope',()=>{
    expect(selectedScopeLabels(undefined,'Local draft')).toEqual({workspace:'本机作品',project:'Local draft',storyline:'默认故事线',branch:'主线'});
  });
});
