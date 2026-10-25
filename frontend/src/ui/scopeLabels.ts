import type {Scope} from '../api';
import type {ScopeLabels} from './AppShell';

/** Display the selected owner honestly when navigation supplied IDs without names.
 * A missing name never establishes that a selected branch is the main branch.
 */
export function selectedScopeLabels(scope:Scope|undefined,localNovelTitle='当前小说'):ScopeLabels{
  if(!scope)return {workspace:'本机作品',project:localNovelTitle,storyline:'默认故事线',branch:'主线'};
  // [HERMIA-FE-20261025 DUI P0-1] Never print an opaque ID as a label; IDs travel in `ids` (rendered as data-* only).
  const named=(id:string,name:string|undefined,unnamed:string)=>id?(name?.trim()||unnamed):'';
  return {workspace:named(scope.workspaceId,scope.workspaceName,'已选创作空间（未命名）'),project:named(scope.projectId,scope.projectName,'已选作品（未命名）'),storyline:named(scope.storylineId,scope.storylineName,'已选故事线（未命名）'),branch:named(scope.branchId,scope.branchName,'已选分支（未命名）'),
    ids:{workspace:scope.workspaceId||'',project:scope.projectId||'',storyline:scope.storylineId||'',branch:scope.branchId||''}};
}
