import {ApiError, type CollaborationContext} from '../api';

export type FindingKind = 'continuity'|'narrative';
export type ReviewedFinding = {
  id:string; description:string; finding_type:string; status:string; effective_status:string; review_version:number;
  source_digest:string; finding_fingerprint:string; stale_source:boolean; suppression_active:boolean;
  source:{chapter_id:string;version:number;digest:string}; provenance:string;
  review_history:{version:number;action:string;reason:string;actor_id:string;timestamp:string}[];
  feedback_reason:string; allowed_actions:string[];
};
export type FindingDecision = {expected_version:number;source_digest:string;finding_fingerprint:string;action:string;reason:string;operation_id:string;confirmed:true};
export type FindingEvidence = {navigation:{chapter_id:string;chapter_version:number;source_digest:string};stale_source:boolean;chapter:{id:string;version:number;content:string};evidence_ids:string[];provenance:string};
export function findingReviewClient(projectId:string, context:CollaborationContext) {
  const captured={...context,scope:context.scope?{...context.scope}:undefined};
  const base=`/api/projects/${encodeURIComponent(projectId)}`;
  async function request<T>(path:string, method='GET', body?:unknown, signal?:AbortSignal):Promise<T> {
    const headers:Record<string,string>={'Content-Type':'application/json'};
    if(captured.sessionToken)headers['X-Session-Token']=captured.sessionToken;
    if(captured.scope?.branchId)headers['X-Branch-Id']=captured.scope.branchId;
    const response=await fetch(base+path,{method,headers,signal,...(body===undefined?{}:{body:JSON.stringify(body)})});
    if(!response.ok){let raw:any={};try{raw=await response.json()}catch{/* No provider body in UI. */}
      throw new ApiError({status:response.status,code:raw?.detail?.code||'FINDING_REQUEST_FAILED',message:response.status===409?'版本或证据已改变。审阅理由已保留，请刷新核对。':response.status===401||response.status===403?'当前身份无权读取或审阅此范围。':response.status===404?'功能未启用，或此范围没有这条记录。':'请求未完成，请检查资料后重试。'});
    }
    return response.json();
  }
  return {
    list:(kind:FindingKind,signal?:AbortSignal)=>request<{items:ReviewedFinding[]}>(`/${kind}/review-findings`,'GET',undefined,signal),
    check:(kind:FindingKind,body:{chapter_id:string;expected_source_version:number;facts?:object})=>request<{items:ReviewedFinding[]}>(`/${kind}/review-checks`,'POST',body),
    review:(kind:FindingKind,id:string,body:FindingDecision)=>request<ReviewedFinding>(`/${kind}/review-findings/${encodeURIComponent(id)}/review`,'POST',body),
    evidence:(kind:FindingKind,id:string,signal?:AbortSignal)=>request<FindingEvidence>(`/${kind}/review-findings/${encodeURIComponent(id)}/evidence`,'GET',undefined,signal),
  };
}
