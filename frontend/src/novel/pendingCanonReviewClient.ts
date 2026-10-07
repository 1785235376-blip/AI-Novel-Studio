import {ApiError,type CollaborationContext} from '../api';
export type CanonReview = {id:string;version:number;status:string;preview_digest:string;proposals:Record<string,unknown>[];source:{chapter_id:string;version:number;digest:string}|null;source_state:string;source_evidence?:{chapter_id:string;version:number;content:string}|null;lineage:string;history:{version:number;action:string;reason:string;actor_id:string}[];recovery_required:boolean;allowed_actions:string[];stale_source:boolean};
export type CanonDecision = {expected_version:number;preview_digest:string;chapter_id:string|null;action:'approve'|'reject';reason:string;operation_id:string;confirmed:true};
export function pendingCanonReviewClient(projectId:string,context:CollaborationContext){
  const captured={...context};
  async function request<T>(path:string,method='GET',body?:unknown,signal?:AbortSignal):Promise<T>{
    const headers:Record<string,string>={'Content-Type':'application/json'};
    if(captured.sessionToken)headers['X-Session-Token']=captured.sessionToken;
    // Deliberately PROJECT-scoped: a branch header cannot grant Canon authority.
    const response=await fetch(`/api/projects/${encodeURIComponent(projectId)}/pending-canon${path}`,{method,headers,signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
    if(!response.ok){let raw:any={};try{raw=await response.json()}catch{/* Do not display arbitrary transport content. */}
      throw new ApiError({status:response.status,code:raw.detail?.code||'CANON_REVIEW_FAILED',message:response.status===409?'Canon 候选或来源已改变。请重新预览并核对，理由已保留。':response.status===401||response.status===403?'需要项目级 Canon 审阅权限；分支角色不能操作主线 Canon。':response.status===503?'保存中断，请刷新检查恢复状态，勿重复批准。':'Canon 记录或功能不可用，请刷新检查。'});
    }
    return response.json();
  }
  return {
    list:(signal?:AbortSignal)=>request<{items:CanonReview[]}>('/review','GET',undefined,signal),
    preview:(id:string,chapterId?:string)=>request<CanonReview>(`/${encodeURIComponent(id)}/preview`,'POST',{chapter_id:chapterId||null}),
    review:(id:string,body:CanonDecision)=>request<CanonReview>(`/${encodeURIComponent(id)}/review`,'POST',body),
    recover:(id:string,version:number)=>request<CanonReview>(`/${encodeURIComponent(id)}/recover`,'POST',{expected_version:version}),
    cancelRecovery:(id:string,version:number)=>request<CanonReview>(`/${encodeURIComponent(id)}/cancel-recovery`,'POST',{expected_version:version}),
  };
}
