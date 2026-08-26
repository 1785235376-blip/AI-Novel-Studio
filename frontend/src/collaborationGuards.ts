import type {ApiProblem, Scope} from './api';
import type {LocalDraft, PersistentConflict} from './drafts';

export type CollaborationFailure='FORBIDDEN'|'VERSION_CONFLICT'|'OTHER';

export function classifyCollaborationFailure(problem:Pick<ApiProblem,'status'|'code'>):CollaborationFailure {
  if(problem.status===403||problem.code==='FORBIDDEN')return 'FORBIDDEN';
  if(problem.status===409||problem.code==='VERSION_CONFLICT')return 'VERSION_CONFLICT';
  return 'OTHER';
}

export const scopeKey=(scope?:Scope)=>scope
  ? [scope.workspaceId,scope.projectId,scope.storylineId,scope.branchId].join('\u001f')
  : '';

function sessionFingerprint(sessionToken:string):string {
  let hash=2166136261;
  for(let index=0;index<sessionToken.length;index++)hash=Math.imul(hash^sessionToken.charCodeAt(index),16777619);
  return (hash>>>0).toString(36);
}

/** Separates origin-local recovery data by collaboration scope and opaque session. */
export const recoveryKey=(scope:Scope|undefined,sessionToken:string)=>{
  const scoped=scopeKey(scope);
  return scoped&&sessionToken?`${scoped}\u001fclient:${sessionFingerprint(sessionToken)}`:scoped;
};

/** Captures scope at dispatch time so a late response cannot populate a new scope. */
export function isCurrentScope(requestScopeKey:string,current?:Scope):boolean {
  return requestScopeKey===scopeKey(current);
}

export function preserveConflict(
  local:LocalDraft,server:{version:number;content:string;document?:unknown},detectedAt:string,
):PersistentConflict {
  return {chapterId:local.chapterId,local:{...local},server:{...server},detectedAt};
}

export const requiresHydrationConflict=(draft:LocalDraft|undefined,serverVersion:number)=>
  !!draft&&draft.baseVersion!==serverVersion;

export function rebaseNewerDraft(current:LocalDraft|undefined,dispatched:Pick<LocalDraft,'content'|'document'>,savedVersion:number):LocalDraft|undefined {
  if(!current)return undefined;
  const same=current.content===dispatched.content&&JSON.stringify(current.document??null)===JSON.stringify(dispatched.document??null);
  return same?undefined:{...current,baseVersion:savedVersion};
}

export class SingleFlight<T> {
  private pending?:Promise<T>;
  run(start:()=>Promise<T>):Promise<T>{if(this.pending)return this.pending;this.pending=start().finally(()=>{this.pending=undefined});return this.pending}
  get active(){return this.pending!==undefined}
}
