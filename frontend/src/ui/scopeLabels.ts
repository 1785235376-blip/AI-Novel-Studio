import type {Scope} from '../api';
import type {ScopeLabels} from './AppShell';

/** Display the selected owner honestly when navigation supplied IDs without names.
 * A missing name never establishes that a selected branch is the main branch.
 */
export function selectedScopeLabels(scope:Scope|undefined,localNovelTitle='当前小说'):ScopeLabels{
  if(!scope)return {workspace:'本机作品',project:localNovelTitle,storyline:'默认故事线',branch:'主线'};
  const named=(id:string,name:string|undefined)=>id?(name?.trim()||id):'';
  return {workspace:named(scope.workspaceId,scope.workspaceName),project:named(scope.projectId,scope.projectName),storyline:named(scope.storylineId,scope.storylineName),branch:named(scope.branchId,scope.branchName)};
}
