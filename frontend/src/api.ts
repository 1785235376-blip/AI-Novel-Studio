export type Scope={workspaceId:string;projectId:string;storylineId:string;branchId:string;workspaceName?:string;projectName?:string;storylineName?:string;branchName?:string};
export type Actor={id:string;displayName:string;workspaceId:string};
export type CollaborationContext={sessionToken:string;actor?:Actor;scope?:Scope};
export type Novel={id:string;title:string;genre:string;chapter_count:number;word_count:number;status:string};
export type Asset={id:string;novel_id:string;filename:string;kind:string;media_type:string;size:number;sha256:string;created_at:string;updated_at:string};
export type Chapter={id:string;novel_id:string;number:number;title:string;content:string;document:any;version:number;word_count:number;status:string;is_archived?:boolean};
export type VersionEntry={version:number;timestamp?:string;created_at?:string;source?:string;reason?:string;operator?:string;actor_id?:string;document?:any};
export type Member={id:string;user_id?:string;display_name?:string;status:string};
export type Permission={id:string;principal_id:string;permission?:string;role?:string;domain:string;scope:any};
export type PermissionSummary={actor_id:string;domain:string;capabilities:Record<string,boolean>};
export type AuditEntry={id:string;actor_id:string;action:string;target_type:string;target_id:string;timestamp:string;metadata?:Record<string,unknown>};
export type Snapshot={id:string;chapter_version_id?:string;context_pack_hash?:string;created_at?:string;model?:string;context_mode?:string;budget?:unknown;ordering?:unknown;actor_id?:string;generation_id?:string};
export type Bootstrap={actor:{actor_id:string;session_id:string;client_id:string};scope:{workspace_id:string;project_id:string;storyline_id:string;branch_id:string};capabilities:Record<string,boolean>};
export type AdminWorkspace={id:string;name:string};
export type WorkspaceNavigationPath={workspace_id:string;project_id:string;storyline_id:string;branch_id:string;project_name?:string;storyline_name?:string;branch_name?:string};
export type WorkspaceNavigationContext={workspace_id:string;eligible_paths:WorkspaceNavigationPath[];default_path:WorkspaceNavigationPath|null};
export type AdminProject={id:string;title:string;genre?:string;status?:string;updated_at?:string};
export type AdminStoryline={id:string;name:string;description?:string};
export type AdminBranch={id:string;name:string;storyline_id?:string};
export type AdminMember={user_id:string;display_name:string;membership_id:string;status:string;roles:any[];permissions:any[]};
export type PermissionExplanation={principal_id:string;permission:string;domain:string;allowed:boolean;sources:any[]};
export type ApiProblem={status:number;code:string;message:string;details?:any;request_id?:string};
export type TextModel={provider_id:string;model_id:string;display_name:string;available:boolean};
export type VisualWorkflowNode={stable_id:string;kind:string;label:string;summary:string;production_boundary:string;capabilities:string[];provider_id?:string;model_id?:string;available?:boolean};
export type VisualTextWorkflow={workflow_contract_version:string;title:string;description:string;read_only:true;nodes:VisualWorkflowNode[];edges:{source:string;target:string;relationship:string}[]};
export type TextRuntimeDiagnostics={diagnostics_contract_version:string;read_only:true;provider_id:string;model_id:string;state:'READY'|'NOT_CONFIGURED'|'UNAVAILABLE'|'MODEL_DISABLED'|'STREAMING_UNSUPPORTED';state_label:string;explanation:string;author_action:string;safe_capabilities:string[]};
export type CredentialStatus={provider:string;configured:boolean;backend:'windows'|'keyring'|'memory';persistent:boolean;degraded:boolean;degraded_reason?:string|null;secret:null};
export type AssetProviderStatus={provider_id:string;display_name?:string;endpoint?:string;default_model:string;api_style?:'openai'|'comfyui'|'automatic1111';local?:boolean;enabled?:boolean;requires_credential?:boolean;credential_configured?:boolean;configured:boolean;registered:boolean;reachable?:boolean;secret?:null};
export type VideoProviderStatus={id:string;display_name:string;endpoint:string;model:string;local:boolean;requires_credential:boolean;credential_configured:boolean;available:boolean;registered:boolean;health:string};
export type ReleaseReadiness={status:'READY'|'DEGRADED'|'BLOCKED';profile:'local'|'collaboration'|'packaged';checks:{vault:{status:'PASS'|'DEGRADED'|'FAIL';backend:'windows'|'keyring'|'memory';persistent:boolean;degraded:boolean;degraded_reason:string|null};session_boundary:{status:'PASS'|'FAIL';mode:'loopback_only'|'session_required'|'packaged_bootstrap';detail:string};providers:{status:'PASS'|'DEGRADED'|'FAIL';text:{configured:boolean;reachable:boolean};image:{registered:number;configured:number};speech:{configured:boolean};vision:{configured:boolean}};packaged:{status:'PASS'|'SKIP'|'FAIL';bootstrap:boolean;memory_fallback_allowed:boolean};plugin_runtime:{status:'DEFERRED';execution_supported:false;isolation:'DENY_ALL'}};blockers:string[];warnings:string[];docs:{env:string[]}};
export type ImportReview={id:string;novel_id:string;status:'PENDING'|'ACCEPTED'|'REJECTED'|'SKIPPED'|string;source_format?:string;import_id?:string|null;candidates:Record<string,Record<string,unknown>[]>;selected?:Record<string,boolean[]>;analysis?:{source:string;provider_id?:string;model_id?:string;chapter_count?:number;content_characters?:number};history?:Record<string,unknown>[];decision?:string;created_at?:string;updated_at?:string};
export type ExportJob={id:string;novel_id:string;format:string;status:'queued'|'running'|'succeeded'|'failed'|'cancelled';created_at:string;updated_at:string;progress?:number;progress_message?:string;retry_of?:string|null;attempt?:number;result?:{format:string;filename:string;content?:string;content_base64?:string;content_encoding?:string;media_type?:string}|null;error?:{code:string;message:string}|null};
export type CreativeAgent={id:string;name:string;description:string;prompt_role:string;tools:string[];output_schema:string;requires_approval:boolean};
export type ContextPreviewSource={section:string;item_count:number};
export type AgentContextPreview={context_contract_version?:string;agent_id?:string;agent_name?:string;novel_id?:string;chapter_id?:string;chapter_version?:number;target?:'local'|'cloud'|string;instruction?:string;sections:Record<string,unknown>;source_manifest?:ContextPreviewSource[];context_hash?:string;created_at?:string};

let collaboration:CollaborationContext={sessionToken:''};
export function setCollaborationContext(value:CollaborationContext){collaboration=value}
export function getCollaborationContext(){return collaboration}

export class ApiError extends Error{constructor(public problem:ApiProblem){super(problem.message)}get status(){return this.problem.status}}

/**
 * Turn a failed API call into a user-facing diagnostic without echoing an
 * arbitrary response body.  Backends may include provider or parser details
 * in ``details``; only a small set of operational fields is safe to render
 * in the desktop UI.  The complete structured payload remains available on
 * ``ApiError.problem`` for diagnostics and tests.
 */
const SAFE_ERROR_DETAIL_KEYS=new Set(['status','actual_version','expected_version','field','format','operation','retry_of','limit','resource']);
export function apiErrorView(error:unknown,fallback='操作失败'):{message:string;code?:string;requestId?:string;details?:string}{
  if(!(error instanceof ApiError)) return {message:error instanceof Error&&error.message?error.message:fallback};
  const problem=error.problem;
  let details:string|undefined;
  if(problem.details&&typeof problem.details==='object'&&!Array.isArray(problem.details)){
    const safe=Object.fromEntries(Object.entries(problem.details).filter(([key,value])=>SAFE_ERROR_DETAIL_KEYS.has(key)&&(typeof value==='string'||typeof value==='number'||typeof value==='boolean')));
    if(Object.keys(safe).length) details=JSON.stringify(safe);
  }
  return {message:problem.message||fallback,code:problem.code,requestId:problem.request_id,details};
}
async function call<T>(url:string,init?:RequestInit):Promise<T>{
 const scope=collaboration.scope;
 const headers:Record<string,string>={'Content-Type':'application/json',...(init?.headers as Record<string,string>||{})};
 if(init?.method&&init.method!=='GET'&&!headers['Idempotency-Key']) headers['Idempotency-Key']=globalThis.crypto?.randomUUID?.()||`desktop-${Date.now()}-${Math.random().toString(16).slice(2)}`;
 if(!headers['X-Request-ID']) headers['X-Request-ID']=globalThis.crypto?.randomUUID?.()||`desktop-${Date.now()}-${Math.random().toString(16).slice(2)}`;
 if(collaboration.sessionToken)headers['X-Session-Token']=collaboration.sessionToken;
 if(scope?.branchId)headers['X-Branch-Id']=scope.branchId;
 const r=await fetch(url,{...init,headers});
 if(!r.ok){const body=await r.text();let raw:any=body;try{raw=body?JSON.parse(body):body}catch{}const detail=raw?.detail??raw;const code=raw?.code??detail?.code??raw?.error?.code??(r.status===403?'FORBIDDEN':'HTTP_ERROR');throw new ApiError({status:r.status,code,message:raw?.message??detail?.message??detail?.detail??raw?.error?.message??(body||`HTTP ${r.status}`),details:raw?.details??raw,request_id:raw?.request_id??(r.headers.get('X-Request-ID')||undefined)})}
 return r.status===204?undefined as T:r.json();
}
async function downloadCall(url:string,extraHeaders:Record<string,string>={}):Promise<Blob>{
  const scope=collaboration.scope;
 const headers:Record<string,string>={'X-Request-ID':globalThis.crypto?.randomUUID?.()||`desktop-${Date.now()}-${Math.random().toString(16).slice(2)}`};
 if(collaboration.sessionToken)headers['X-Session-Token']=collaboration.sessionToken;
 if(scope?.branchId)headers['X-Branch-Id']=scope.branchId;
 Object.assign(headers,extraHeaders);
 const r=await fetch(url,{headers});
 if(!r.ok){const body=await r.text();let raw:any=body;try{raw=body?JSON.parse(body):body}catch{}const detail=raw?.detail??raw;const code=raw?.code??detail?.code??(r.status===403?'FORBIDDEN':'HTTP_ERROR');throw new ApiError({status:r.status,code,message:raw?.message??detail?.message??detail?.detail??(body||`HTTP ${r.status}`),details:raw?.details??raw,request_id:raw?.request_id??(r.headers.get('X-Request-ID')||undefined)})}
 return r.blob();
}
const query=(path:string,params:Record<string,string|undefined>)=>{const s=new URLSearchParams();Object.entries(params).forEach(([k,v])=>v!==undefined&&s.set(k,v));return `${path}?${s}`};
const scoped=(scope:Scope,suffix:string)=>`/api/collaboration/workspaces/${encodeURIComponent(scope.workspaceId)}/projects/${encodeURIComponent(scope.projectId)}/storylines/${encodeURIComponent(scope.storylineId)}/branches/${encodeURIComponent(scope.branchId)}/${suffix}`;
const items=async<T>(promise:Promise<{items:T[]}>):Promise<T[]>=>(await promise).items;
export const aiAnalyzeImportReview=(novelId:string,reviewId:string,providerId?:string,modelId?:string)=>call<{review:ImportReview;analysis:NonNullable<ImportReview['analysis']>}>(`/api/novels/${encodeURIComponent(novelId)}/import/knowledge-base/review/${encodeURIComponent(reviewId)}/ai-analyze`,{method:'POST',body:JSON.stringify({provider_id:providerId,model_id:modelId})});
export const createNovelKnowledgeReview=(novelId:string)=>call<ImportReview>(`/api/novels/${encodeURIComponent(novelId)}/knowledge-base/review`,{method:'POST'});
export const createChapterKnowledgeReview=(novelId:string,chapterId:string)=>call<ImportReview>(`/api/novels/${encodeURIComponent(novelId)}/chapters/${encodeURIComponent(chapterId)}/knowledge-base/review`,{method:'POST'});
export const api={
 releaseReadiness:()=>call<ReleaseReadiness>('/api/release/readiness'),
 packagedProvisionInitialWorkspace:()=>call<AdminWorkspace>('/api/packaged/initial-workspace',{method:'POST',body:JSON.stringify({})}),
 adminWorkspaces:()=>items(call<{items:AdminWorkspace[]}>('/api/collaboration/admin/workspaces')),
 adminCreateWorkspace:(workspaceId:string,name:string)=>call<AdminWorkspace>('/api/collaboration/admin/workspaces',{method:'POST',body:JSON.stringify({id:workspaceId,name})}),
 adminRenameWorkspace:(workspaceId:string,name:string)=>call<AdminWorkspace>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}`,{method:'PATCH',body:JSON.stringify({name})}),
 adminWorkspaceNavigation:(workspaceId:string)=>call<WorkspaceNavigationContext>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/navigation`),
 adminProjects:(workspaceId:string)=>call<AdminProject[]>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects`),
 adminCreateProject:(workspaceId:string,title:string,genre='')=>call<AdminProject>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects`,{method:'POST',body:JSON.stringify({title,genre})}),
 adminStorylines:(workspaceId:string,projectId:string)=>call<AdminStoryline[]>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}/storylines`),
 adminCreateStoryline:(workspaceId:string,projectId:string,name:string)=>call<AdminStoryline>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}/storylines`,{method:'POST',body:JSON.stringify({name})}),
 adminBranches:(workspaceId:string,projectId:string,storylineId:string)=>call<AdminBranch[]>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}/storylines/${encodeURIComponent(storylineId)}/branches`),
 adminCreateBranch:(workspaceId:string,projectId:string,storylineId:string,name:string)=>call<AdminBranch>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/projects/${encodeURIComponent(projectId)}/storylines/${encodeURIComponent(storylineId)}/branches`,{method:'POST',body:JSON.stringify({name})}),
 adminMembers:(workspaceId:string)=>call<AdminMember[]>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/members`),
 adminAddMember:(workspaceId:string,userId:string)=>call<AdminMember>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}`,{method:'POST'}),
 adminSetMemberStatus:(workspaceId:string,userId:string,status:'ACTIVE'|'INACTIVE')=>call<any>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/members/${encodeURIComponent(userId)}/status`,{method:'PATCH',body:JSON.stringify({status})}),
 adminGrantRole:(workspaceId:string,body:any)=>call<any>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/roles`,{method:'POST',body:JSON.stringify(body)}),
 adminRevokeRole:(workspaceId:string,id:string)=>call<any>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/roles/${encodeURIComponent(id)}`,{method:'DELETE'}),
 adminGrantPermission:(workspaceId:string,body:any)=>call<any>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/permissions`,{method:'POST',body:JSON.stringify(body)}),
 adminRevokePermission:(workspaceId:string,id:string)=>call<any>(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/permissions/${encodeURIComponent(id)}`,{method:'DELETE'}),
 adminExplain:(workspaceId:string,principalId:string,permission:string,domain:string,scope:Scope)=>call<PermissionExplanation>(query(`/api/collaboration/admin/workspaces/${encodeURIComponent(workspaceId)}/explain`,{principal_id:principalId,permission,domain,kind:'BRANCH',project_id:scope.projectId,storyline_id:scope.storylineId,branch_id:scope.branchId})),
 bootstrap:(scope:Scope)=>call<Bootstrap>(scoped(scope,'bootstrap')),members:(scope:Scope)=>items(call<{items:Member[]}>(scoped(scope,'members'))),permissions:(scope:Scope)=>call<PermissionSummary>(scoped(scope,'permissions')),audit:(scope:Scope)=>items(call<{items:AuditEntry[]}>(scoped(scope,'audit'))),snapshots:(scope:Scope,chapterId:string)=>items(call<{items:Snapshot[]}>(scoped(scope,`chapters/${encodeURIComponent(chapterId)}/snapshots`))),snapshotDetail:(scope:Scope,chapterId:string,snapshotId:string)=>call<Snapshot>(scoped(scope,`chapters/${encodeURIComponent(chapterId)}/snapshots/${encodeURIComponent(snapshotId)}`)),scopedChapters:(scope:Scope)=>items(call<{items:Chapter[]}>(scoped(scope,'chapters'))),scopedCreateChapter:(scope:Scope,title:string)=>call<Chapter>(scoped(scope,'chapters'),{method:'POST',body:JSON.stringify({title})}),storyDatabase:(scope:Scope,resource:string)=>call<{resource:string;items:any[]}>(scoped(scope,`story-database/${encodeURIComponent(resource)}`)),
 novels:()=>call<Novel[]>('/api/novels'),novel:(id:string)=>call<Novel&{long_term_summary?:string}>(`/api/novels/${id}`),writingGoal:(id:string)=>call<{target_words:number;target_chapters:number;current_words:number;current_chapters:number;words_progress:number;chapters_progress:number;deadline:string}>(`/api/novels/${encodeURIComponent(id)}/writing-goal`),updateWritingGoal:(id:string,body:{target_words:number;target_chapters:number;deadline?:string})=>call<any>(`/api/novels/${encodeURIComponent(id)}/writing-goal`,{method:'PUT',body:JSON.stringify(body)}),updateNovel:(id:string,body:{title?:string;genre?:string;status?:string;long_term_summary?:string})=>call<Novel&{long_term_summary?:string}>(`/api/novels/${id}`,{method:'PUT',body:JSON.stringify(body)}),createNovel:(title:string,genre:string)=>call<Novel>('/api/novels',{method:'POST',body:JSON.stringify({title,genre})}),deleteNovel:(id:string)=>call<void>(`/api/novels/${id}`,{method:'DELETE'}),
   assets:(novelId:string,kind?:string,characterId?:string,sceneId?:string)=>{const params=new URLSearchParams();if(kind)params.set('kind',kind);if(characterId)params.set('character_id',characterId);if(sceneId)params.set('scene_id',sceneId);const query=params.toString();return call<Asset[]>(`/api/novels/${encodeURIComponent(novelId)}/assets${query?`?${query}`:''}`)},
 uploadAsset:(novelId:string,body:{filename:string;content_base64:string;media_type?:string;kind?:string})=>call<Asset>(`/api/novels/${encodeURIComponent(novelId)}/assets`,{method:'POST',body:JSON.stringify({novel_id:novelId,...body})}),
 asset:(assetId:string)=>call<Asset>(`/api/assets/${encodeURIComponent(assetId)}`),
 assetDownloadUrl:(assetId:string,novelId:string)=>`/api/assets/${encodeURIComponent(assetId)}/download?novel_id=${encodeURIComponent(novelId)}`,
 assetDownload:(assetId:string,novelId:string)=>downloadCall(`/api/assets/${encodeURIComponent(assetId)}/download?novel_id=${encodeURIComponent(novelId)}`),
 deleteAsset:(assetId:string)=>call<{id:string;deleted:boolean}>(`/api/assets/${encodeURIComponent(assetId)}`,{method:'DELETE'}),
 chapters:(id:string)=>call<Chapter[]>(`/api/novels/${id}/chapters`),archivedChapters:(id:string)=>call<Chapter[]>(`/api/novels/${id}/chapters/archived`),archiveChapter:(id:string,version:number)=>call<Chapter>(`/api/chapters/${id}/archive?expected_version=${version}`,{method:'POST'}),restoreArchivedChapter:(id:string,version:number)=>call<Chapter>(`/api/chapters/${id}/restore-archive?expected_version=${version}`,{method:'POST'}),chapter:(id:string)=>call<Chapter>(`/api/chapters/${id}`),createChapter:(id:string,title='')=>call<Chapter>(`/api/novels/${id}/chapters`,{method:'POST',body:JSON.stringify({title})}),
 saveChapter:(id:string,content:string,version:number,document?:any,source='USER')=>call<Chapter>(`/api/chapters/${id}`,{method:'PUT',body:JSON.stringify({content,document,version,source})}),history:async(scope:Scope,id:string)=>(await call<{items:VersionEntry[];current_version:number}>(scoped(scope,`chapters/${encodeURIComponent(id)}/revisions`))).items,revisionDetail:(scope:Scope,id:string,version:number)=>call<VersionEntry>(scoped(scope,`chapters/${encodeURIComponent(id)}/revisions/${version}`)),legacyHistory:(id:string)=>call<VersionEntry[]>(`/api/chapters/${encodeURIComponent(id)}/history`),restore:(id:string,v:number,expected:number)=>call<Chapter>(`/api/chapters/${id}/history/${v}/restore?expected_version=${expected}`,{method:'POST'}),deleteChapter:(id:string)=>call<void>(`/api/chapters/${id}`,{method:'DELETE'}),duplicateChapter:(id:string)=>call<Chapter>(`/api/chapters/${id}/duplicate`,{method:'POST'}),renameChapter:(id:string,title:string,version:number)=>call<Chapter>(`/api/chapters/${id}/rename`,{method:'POST',body:JSON.stringify({title,version})}),moveChapter:(id:string,direction:'up'|'down')=>call<any>(`/api/chapters/${id}/move`,{method:'POST',body:JSON.stringify({direction})}),
 generate:(operation:string,body:object)=>call<{job_id:string;events_url:string;base_chapter_version?:number}>(`/api/generate/${operation}`,{method:'POST',body:JSON.stringify(body)}),job:(id:string)=>call<any>(`/api/generation/${id}`),retryGeneration:(id:string)=>call<{job_id:string;events_url:string;base_chapter_version?:number;retry_of:string}>(`/api/generation/${id}/retry`,{method:'POST'}),accept:(id:string,content?:string,expected_version?:number)=>call<any>(`/api/generation/${id}/accept`,{method:'POST',body:JSON.stringify({content,expected_version})}),reject:(id:string)=>call<any>(`/api/generation/${id}/reject`,{method:'POST'}),cancel:(id:string)=>call<any>(`/api/generation/${id}/cancel`,{method:'POST'}),
 generateVariants:(operation:string,body:object)=>call<{operation:string;group_id:string;count:number;variants:{job_id:string;events_url:string;base_chapter_version?:number;variant_index:number}[]}>(`/api/generate/${operation}/variants`,{method:'POST',body:JSON.stringify(body)}),
 generationGroup:(groupId:string)=>call<{group_id:string;count:number;variants:any[]}>(`/api/generation-groups/${encodeURIComponent(groupId)}`),
 textModels:()=>items(call<{items:TextModel[]}>('/api/text-models')),
 agentChat:(body:{message:string;provider_id?:string;model_id?:string;context?:Record<string,unknown>})=>call<{message:string;provider_id:string;model_id:string;read_only:true}>('/api/agent/chat',{method:'POST',body:JSON.stringify(body)}),
 userPreferences:()=>call<{enabled:boolean;share_enabled:boolean;harness_enabled:boolean;items:{key:string;content:string;source:string;confidence:number}[]}>('/api/user-preferences'),
 saveUserPreference:(key:string,content:string)=>call<any>(`/api/user-preferences/${encodeURIComponent(key)}`,{method:'PUT',body:JSON.stringify({key,content})}),
 deleteUserPreference:(key:string)=>call<any>(`/api/user-preferences/${encodeURIComponent(key)}`,{method:'DELETE'}),
 setUserPreferencesEnabled:(enabled:boolean)=>call<any>(`/api/user-preferences-enabled?enabled=${enabled}`,{method:'PUT'}),
 setUserPreferencesShareEnabled:(enabled:boolean)=>call<any>(`/api/user-preferences-share-enabled?enabled=${enabled}`,{method:'PUT'}),
 setHarnessEnabled:(enabled:boolean)=>call<any>(`/api/harness-enabled?enabled=${enabled}`,{method:'PUT'}),
 harnessStatus:()=>call<{configured:boolean;reachable:boolean;compatible?:boolean;endpoint?:string;version?:string;reason?:string}>('/api/harness/status'),
 harnessLaunchReadiness:()=>call<{ready:boolean;authorized:boolean;local_endpoint:boolean;port_available?:boolean;reason:string}>('/api/harness/launch-readiness'),
 harnessProcess:()=>call<{running:boolean;pid:number|null}>('/api/harness/process'),
 startHarness:()=>call<{running:boolean;pid:number|null}>('/api/harness/process/start',{method:'POST'}),
  stopHarness:()=>call<{running:boolean;pid:number|null}>('/api/harness/process/stop',{method:'POST'}),
  harnessAccessAudit:(filters?:{novel_id?:string;agent_id?:string;outcome?:string})=>call<{items:{at:string;novel_id:string;chapter:number;agent_id:string;scopes:string[];outcome:string}[]}>(`/api/harness/access-audit?${new URLSearchParams(Object.entries(filters || {}).filter(([, value]) => Boolean(value)) as [string,string][]).toString()}`),
  harnessAccessAuditCsv:(filters?:{novel_id?:string;agent_id?:string;outcome?:string})=>`/api/harness/access-audit.csv?${new URLSearchParams(Object.entries(filters || {}).filter(([, value]) => Boolean(value)) as [string,string][]).toString()}`,
  clearHarnessAccessAudit:()=>call<{cleared:boolean}>('/api/harness/access-audit?confirm=true',{method:'DELETE'}),
 agents:()=>call<{catalog_version:string;agents:CreativeAgent[]}>('/api/agents'),
 agentContext:(agentId:string,novelId:string,chapter:number,instruction:string='',target:'local'|'cloud'='local')=>call<AgentContextPreview>(query(`/api/agents/${encodeURIComponent(agentId)}/context-preview`,{novel_id:novelId,chapter:String(chapter),instruction,target})),
 createAgentJob:(body:object)=>call<any>('/api/agent-jobs',{method:'POST',body:JSON.stringify(body)}),
 agentJob:(id:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}`),
 agentJobs:(params:{novelId?:string;agentId?:string;status?:string;createdAfter?:string;createdBefore?:string;branchId?:string;page?:number;pageSize?:number}={})=>call<{items:any[];page:number;page_size:number;total:number;has_more:boolean}>(query('/api/agent-jobs',{novel_id:params.novelId,agent_id:params.agentId,status:params.status,created_after:params.createdAfter,created_before:params.createdBefore,branch_id:params.branchId,page:params.page?.toString(),page_size:params.pageSize?.toString()})),
 agentJobsExportUrl:(params:{novelId?:string;agentId?:string;status?:string;createdAfter?:string;createdBefore?:string}={})=>query('/api/agent-jobs/export.csv',{novel_id:params.novelId,agent_id:params.agentId,status:params.status,created_after:params.createdAfter,created_before:params.createdBefore}),
 agentJobsExport:(params:{novelId?:string;agentId?:string;status?:string;createdAfter?:string;createdBefore?:string;branchId?:string}={})=>downloadCall(query('/api/agent-jobs/export.csv',{novel_id:params.novelId,agent_id:params.agentId,status:params.status,created_after:params.createdAfter,created_before:params.createdBefore,branch_id:params.branchId}),params.branchId?{'X-Branch-Id':params.branchId}:{}),
 agentJobAudit:(novelId:string,branchId:string,params:{createdAfter?:string;createdBefore?:string;page?:number;pageSize?:number}={})=>call<{items:AuditEntry[];page:number;page_size:number;total:number;has_more:boolean}>(query('/api/agent-jobs/audit',{novel_id:novelId,branch_id:branchId,created_after:params.createdAfter,created_before:params.createdBefore,page:params.page?.toString(),page_size:params.pageSize?.toString()})),
 agentJobAuditExport:(novelId:string,branchId:string,params:{createdAfter?:string;createdBefore?:string}={})=>downloadCall(query('/api/agent-jobs/audit.csv',{novel_id:novelId,branch_id:branchId,created_after:params.createdAfter,created_before:params.createdBefore}),{'X-Branch-Id':branchId}),
 adaptationProposals:(novelId:string,branchId?:string)=>call<any[]>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations`,{branch_id:branchId})),
 createAdaptationProposal:(novelId:string,body:{target:string;title:string;instruction:string},branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations`,{branch_id:branchId}),{method:'POST',body:JSON.stringify(body)}),
 updateAdaptationBlueprint:(novelId:string,id:string,body:object,branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(id)}/blueprint`,{branch_id:branchId}),{method:'PUT',body:JSON.stringify(body)}),
 approveAdaptationProposal:(novelId:string,id:string,branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(id)}/approve`,{branch_id:branchId}),{method:'POST'}),
 materializeAdaptation:(novelId:string,id:string,branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(id)}/materialize`,{branch_id:branchId}),{method:'POST'}),
 generateAdaptationDraft:(novelId:string,proposalId:string,taskId:string,body:{mode:string;provider_id?:string;model_id?:string},branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(proposalId)}/tasks/${encodeURIComponent(taskId)}/generate`,{branch_id:branchId}),{method:'POST',body:JSON.stringify(body)}),
 reviewAdaptationDraft:(novelId:string,proposalId:string,taskId:string,decision:'ACCEPTED'|'REJECTED',branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(proposalId)}/tasks/${encodeURIComponent(taskId)}/review`,{branch_id:branchId}),{method:'POST',body:JSON.stringify({decision})}),
 applyAdaptationDraft:(novelId:string,proposalId:string,taskId:string,branchId?:string)=>call<any>(query(`/api/novels/${encodeURIComponent(novelId)}/adaptations/${encodeURIComponent(proposalId)}/tasks/${encodeURIComponent(taskId)}/apply`,{branch_id:branchId}),{method:'POST'}),
 screenplays:(novelId:string)=>call<any[]>(`/api/novels/${encodeURIComponent(novelId)}/screenplays`),
 createScreenplay:(novelId:string,title:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays`,{method:'POST',body:JSON.stringify({title})}),
 updateScreenplayScene:(novelId:string,screenplayId:string,sceneId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/scenes/${encodeURIComponent(sceneId)}`,{method:'PUT',body:JSON.stringify(body)}),
  approveScreenplay:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/approve`,{method:'POST'}),
  planScreenplayShots:(novelId:string,id:string)=>call<any[]>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/shots`,{method:'POST'}),
  updateScreenplayShot:(novelId:string,screenplayId:string,shotId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/shots/${encodeURIComponent(shotId)}`,{method:'PUT',body:JSON.stringify(body)}),
  approveScreenplayShots:(novelId:string,id:string)=>call<any[]>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/shots/approve`,{method:'POST'}),
  planStoryboard:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/storyboard`,{method:'POST'}),
  updateStoryboardCard:(novelId:string,screenplayId:string,cardId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/storyboard/${encodeURIComponent(cardId)}`,{method:'PUT',body:JSON.stringify(body)}),
  approveStoryboard:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/storyboard/approve`,{method:'POST'}),
  planTransitions:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/transitions`,{method:'POST'}),
  updateTransition:(novelId:string,screenplayId:string,transitionId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/transitions/${encodeURIComponent(transitionId)}`,{method:'PUT',body:JSON.stringify(body)}),
  approveTransitions:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/transitions/approve`,{method:'POST'}),
  planAssets:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/assets`,{method:'POST'}),
  updateAsset:(novelId:string,screenplayId:string,assetId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/assets/${encodeURIComponent(assetId)}`,{method:'PUT',body:JSON.stringify(body)}),
  approveAssets:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/assets/approve`,{method:'POST'}),
  createAssetTasks:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(id)}/asset-tasks`,{method:'POST'}),
  updateAssetTask:(novelId:string,screenplayId:string,taskId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/asset-tasks/${encodeURIComponent(taskId)}`,{method:'PUT',body:JSON.stringify(body)}),
  executeAssetTask:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/asset-tasks/${encodeURIComponent(taskId)}/execute`,{method:'POST'}),
 executeAgentJob:(id:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/execute`,{method:'POST'}),
 startAgentJob:(id:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/start`,{method:'POST'}),
 cancelAgentJob:(id:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/cancel`,{method:'POST'}),
 retryAgentJob:(id:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/retry`,{method:'POST'}),
 reviewAgentJob:(id:string,decision:'ACCEPTED'|'REJECTED',reviewedBy:string,note='',actions:object[]=[])=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/review`,{method:'POST',body:JSON.stringify({decision,reviewed_by:reviewedBy,note,actions})}),
 applyAgentJob:(id:string,appliedBy:string)=>call<any>(`/api/agent-jobs/${encodeURIComponent(id)}/apply`,{method:'POST',body:JSON.stringify({applied_by:appliedBy})}),
 upsertCharacter:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/characters/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 upsertLocation:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/locations/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 upsertTimelineEvent:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/timeline/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
   upsertForeshadowing:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/foreshadowing/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
   foreshadowingReminders:(novelId:string,chapter:number)=>call<{chapter:number;pending:any[];overdue:any[];paid_off:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/foreshadowing/reminders?chapter=${chapter}`),
 upsertRelationship:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/relationships/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 outline:(novelId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/outline`),
 updateOutline:(novelId:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/outline`,{method:'PUT',body:JSON.stringify(body)}),
 upsertVolume:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/volumes/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 upsertScene:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/scenes/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 upsertStoryRoute:(novelId:string,id:string,body:object)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/story-routes/${encodeURIComponent(id)}`,{method:'PUT',body:JSON.stringify(body)}),
 storyRoutes:(novelId:string)=>call<any[]>(`/api/novels/${encodeURIComponent(novelId)}/story-routes`),
 worldRules:(novelId:string,status?:string)=>call<{items:any[];storage:string}>(query(`/api/novels/${encodeURIComponent(novelId)}/world-rules`,status?{status}:{})),
   createWorldRule:(novelId:string,payload:Record<string,unknown>)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/world-rules`,{method:'POST',body:JSON.stringify({payload})}),
   characterEvolution:(novelId:string,characterId:string)=>call<{items:any[];total:number}>(`/api/novels/${encodeURIComponent(novelId)}/characters/${encodeURIComponent(characterId)}/evolution`),
   createCharacterEvolution:(novelId:string,characterId:string,body:Record<string,unknown>)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/characters/${encodeURIComponent(characterId)}/evolution`,{method:'POST',body:JSON.stringify({...body,character_id:characterId})}),
   continuityCheck:(projectId:string,body:{events:any[];locations:any[];knowledge:any[];used_subject_ids?:string[];world_rules?:any[]})=>call<{status:string;findings:any[]}>(`/api/projects/${encodeURIComponent(projectId)}/continuity/checks`,{method:'POST',body:JSON.stringify(body)}),
   continuityFindings:(projectId:string)=>call<any[]>(`/api/projects/${encodeURIComponent(projectId)}/continuity/findings`),
   transitionPrompt:(novelId:string,screenplayId:string,transitionId:string)=>call<{transition_id:string;type:string;prompt:string;template_version:string;generated_at:string}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/transitions/${encodeURIComponent(transitionId)}/prompt`),
   transitionSuggestion:(novelId:string,screenplayId:string,transitionId:string)=>call<{suggested_type:string;reason:string}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/transitions/${encodeURIComponent(transitionId)}/suggestion`),
   motionPrompt:(novelId:string,screenplayId:string,transitionId:string)=>call<{motion_prompt:string;status:string}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/transitions/${encodeURIComponent(transitionId)}/motion-prompt`),
   saveMotionPrompt:(novelId:string,screenplayId:string,transitionId:string,motion_prompt:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/transitions/${encodeURIComponent(transitionId)}/motion-prompt`,{method:'PUT',body:JSON.stringify({motion_prompt})}),
   createMotionTasks:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks`,{method:'POST'}),
   videoProviders:()=>call<{items:any[]}>(`/api/video-providers`),
   configureVideoProvider:(providerId:string,config:{endpoint:string;model_id:string;enabled:boolean;local?:boolean;requires_credential?:boolean;display_name?:string})=>call<any>(`/api/video-providers/${encodeURIComponent(providerId)}/config`,{method:'PUT',body:JSON.stringify(config)}),
   videoProviderConfig:(providerId:string)=>call<any>(`/api/video-providers/${encodeURIComponent(providerId)}/config`),
   videoProviderHealth:(providerId:string)=>call<any>(`/api/video-providers/${encodeURIComponent(providerId)}/health`),
   videoCallbackSecurity:()=>call<{configured:boolean;header:string;secret_exposed:false}>(`/api/video-callback/security`),
   updateMotionTask:(novelId:string,screenplayId:string,taskId:string,status:'PENDING'|'CANCELLED')=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}`,{method:'PUT',body:JSON.stringify({status})}),
   updateMotionFrames:(novelId:string,screenplayId:string,taskId:string,frames:{start_frame?:string|null;end_frame?:string|null;constraints?:Record<string,unknown>})=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/frames`,{method:'PUT',body:JSON.stringify(frames)}),
   saveDirectorShotConstraints:(novelId:string,screenplayId:string,taskId:string,shot:{shot_id?:string;name:string;duration:string;camera:string;action:string},references:unknown[]=[])=>api.updateMotionFrames(novelId,screenplayId,taskId,{constraints:{shot_id:shot.shot_id,shot, references}}),
   updateMotionProvider:(novelId:string,screenplayId:string,taskId:string,provider_id:string,model_id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/provider`,{method:'PUT',body:JSON.stringify({provider_id,model_id})}),
   syncMotionTask:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/sync`,{method:'POST'}),
   executeMotionTask:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/execute`,{method:'POST'}),
   motionCallback:(novelId:string,screenplayId:string,taskId:string,payload:{status:string;progress?:number;url?:string;error?:string})=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/callback`,{method:'POST',body:JSON.stringify(payload)}),
   attachMotionResult:(novelId:string,screenplayId:string,taskId:string,url:string,media_type='video/mp4')=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/result`,{method:'PUT',body:JSON.stringify({url,media_type})}),
   motionResultHistory:(novelId:string,screenplayId:string,taskId:string)=>call<{current:any;history:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/result-history`),
   motionAssetReference:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/asset-reference`),
   importMotionAsset:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/import-asset`,{method:'POST'}),
   downloadMotionAsset:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/import-asset/download`,{method:'POST'}),
   motionAssetImportStatus:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/import-asset`),
   motionAssetImports:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/import-assets`),
   retryFailedMotionAssetImports:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/import-assets/retry`,{method:'POST'}),
   visionAnalyze:(body:{provider_id:string;model_id:string;prompt:string;image_url:string;novel_id?:string;character_id?:string;scene_id?:string})=>call<{provider_id:string;model_id:string;text:string}>('/api/vision/analyze',{method:'POST',body:JSON.stringify(body)}),
   imageGenerate:(body:{provider_id:string;model_id:string;prompt:string;novel_id?:string;character_id?:string;scene_id?:string;constraints?:Record<string,unknown>})=>call<{provider_id:string;model_id:string;asset_uri:string;prompt:string;constraints?:Record<string,unknown>}>('/api/images/generate',{method:'POST',body:JSON.stringify(body)}),
   speechSynthesize:(body:{provider_id:string;model_id:string;voice:string;text:string;emotion?:string;novel_id?:string;character_id?:string;chapter_id?:string})=>call<{provider_id:string;model_id:string;voice:string;audio_uri:string}>('/api/speech/synthesize',{method:'POST',body:JSON.stringify(body)}),
   synthesizeDirectorShotDialogue:(shot:{shot_id?:string;dialogue?:string;subtitle?:string},config:{provider_id:string;model_id:string;voice:string;emotion?:string;novel_id?:string;character_id?:string})=>api.speechSynthesize({...config,text:(shot.dialogue||shot.subtitle||'').trim(),chapter_id:shot.shot_id}),
   synthesizeDirectorShots:async(shots:Array<{shot_id?:string;dialogue?:string;subtitle?:string;voice?:string;emotion?:string}>,config:{provider_id:string;model_id:string;novel_id?:string;character_id?:string})=>{const results:unknown[]=[];for(const shot of shots){if(!(shot.dialogue||shot.subtitle)||!shot.voice){results.push({shot_id:shot.shot_id,status:'skipped'});continue}try{results.push({shot_id:shot.shot_id,status:'succeeded',result:await api.synthesizeDirectorShotDialogue(shot,{...config,voice:shot.voice,emotion:shot.emotion||'neutral'})})}catch(error){results.push({shot_id:shot.shot_id,status:'failed',error})}}return results},
   speechGenerations:(novelId:string,characterId?:string)=>call<{items:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/speech-generations${characterId?`?character_id=${encodeURIComponent(characterId)}`:''}`),
   audiobookManifest:(novelId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/manifest`),
   audiobookMixPlan:(novelId:string,chapterId?:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/mix-plan${chapterId?`?chapter_id=${encodeURIComponent(chapterId)}`:''}`),
   queueAudiobookChapter:(novelId:string,chapterId:string,voice='alloy')=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/chapters/${encodeURIComponent(chapterId)}/queue?voice=${encodeURIComponent(voice)}`,{method:'POST'}),
   audiobookJobs:(novelId:string)=>call<{items:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/jobs`),
   executeAudiobookJob:(novelId:string,jobId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/jobs/${encodeURIComponent(jobId)}/execute`,{method:'POST'}),
   retryAudiobookJob:(novelId:string,jobId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/audiobook/jobs/${encodeURIComponent(jobId)}/retry`,{method:'POST'}),
   importGeneratedSpeech:(novelId:string,body:{audio_uri:string;filename?:string;character_id?:string})=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/speech-generations/import`,{method:'POST',body:JSON.stringify(body)}),
   imageGenerations:(novelId:string,characterId?:string,sceneId?:string)=>{const params=new URLSearchParams();if(characterId)params.set('character_id',characterId);if(sceneId)params.set('scene_id',sceneId);const query=params.toString();return call<{items:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/image-generations${query?`?${query}`:''}`)},
   importGeneratedImage:(novelId:string,body:{asset_uri:string;filename?:string;character_id?:string;scene_id?:string})=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/image-generations/import`,{method:'POST',body:JSON.stringify(body)}),
   visualMemories:(novelId:string,characterId?:string,sceneId?:string)=>{const params=new URLSearchParams();if(characterId)params.set('character_id',characterId);if(sceneId)params.set('scene_id',sceneId);const query=params.toString();return call<{items:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/visual-memories${query?`?${query}`:''}`)},
   discoverPlugins:()=>call<{items:any[];execution_supported:boolean}>('/api/plugins/discover'),
   pluginRuntimeStatus:()=>call<any>('/api/plugins/runtime-status'),
   plugins:()=>call<{items:any[]}>('/api/plugins'),
   registerPlugin:(body:object)=>call<any>('/api/plugins',{method:'POST',body:JSON.stringify(body)}),
   setPluginPermissions:(id:string,body:object)=>call<any>(`/api/plugins/${encodeURIComponent(id)}/permissions`,{method:'PUT',body:JSON.stringify(body)}),
   enablePlugin:(id:string)=>call<any>(`/api/plugins/${encodeURIComponent(id)}/enable`,{method:'POST'}),
   disablePlugin:(id:string)=>call<any>(`/api/plugins/${encodeURIComponent(id)}/disable`,{method:'POST'}),
   workflows:(novelId?:string)=>call<{items:any[]}>(`/api/workflows${novelId?`?novel_id=${encodeURIComponent(novelId)}`:''}`),
   createWorkflow:(body:object)=>call<any>('/api/workflows',{method:'POST',body:JSON.stringify(body)}),
   workflowRuns:(id:string)=>call<{items:any[]}>(`/api/workflows/${encodeURIComponent(id)}/runs`),
   createWorkflowRun:(id:string,body:object)=>call<any>(`/api/workflows/${encodeURIComponent(id)}/runs`,{method:'POST',body:JSON.stringify(body)}),
   pauseWorkflow:(id:string)=>call<any>(`/api/workflow-runs/${encodeURIComponent(id)}/pause`,{method:'POST'}),
   resumeWorkflow:(id:string)=>call<any>(`/api/workflow-runs/${encodeURIComponent(id)}/resume`,{method:'POST'}),
   approveWorkflowNode:(runId:string,nodeId:string)=>call<any>(`/api/workflow-runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}/approve?approved_by=local-author`,{method:'POST'}),
   triggerAgentNode:(runId:string,nodeId:string)=>call<any>(`/api/workflow-runs/${encodeURIComponent(runId)}/nodes/${encodeURIComponent(nodeId)}/trigger-agent`,{method:'POST'}),
   agentQueue:(novelId?:string)=>call<{items:any[]}>(`/api/agent-queue${novelId?`?novel_id=${encodeURIComponent(novelId)}`:''}`),
   claimAgentTask:(runId:string,nodeId:string)=>call<any>(`/api/agent-queue/${encodeURIComponent(runId)}/${encodeURIComponent(nodeId)}/claim`,{method:'POST'}),
   completeAgentTask:(runId:string,nodeId:string,status:'SUCCEEDED'|'FAILED',output?:object,error?:string)=>call<any>(`/api/agent-queue/${encodeURIComponent(runId)}/${encodeURIComponent(nodeId)}/complete?status=${status}${error?`&error=${encodeURIComponent(error)}`:''}`,{method:'POST',body:output?JSON.stringify(output):undefined}),
   pipelineStatus:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/pipeline-status`),
   multimodalHealth:()=>call<any>('/api/multimodal/health'),
   assetProviders:()=>call<{items:AssetProviderStatus[];routing_policy?:'LOCAL_FIRST'}>('/api/asset-providers'),
   configureAssetProvider:(providerId:string,config:{endpoint:string;default_model:string;api_style:'openai'|'comfyui'|'automatic1111';local:boolean;enabled:boolean;requires_credential:boolean;display_name:string})=>call<AssetProviderStatus>(`/api/asset-providers/${encodeURIComponent(providerId)}`,{method:'PUT',body:JSON.stringify(config)}),
   deleteAssetProvider:(providerId:string)=>call<{provider_id:string;deleted:boolean}>(`/api/asset-providers/${encodeURIComponent(providerId)}`,{method:'DELETE'}),
   advancePipeline:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/pipeline-advance`,{method:'POST'}),
   advancePipelineUntilGate:(novelId:string,screenplayId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/pipeline-advance-until-gate`,{method:'POST'}),
   retryMotionAssetImport:(novelId:string,screenplayId:string,taskId:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/import-asset/retry`,{method:'POST'}),
   motionFrameHistory:(novelId:string,screenplayId:string,taskId:string)=>call<{current:any;history:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/motion-tasks/${encodeURIComponent(taskId)}/frame-history`),
   visualContinuity:(novelId:string,screenplayId:string)=>call<{screenplay_id:string;findings:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/screenplays/${encodeURIComponent(screenplayId)}/visual-continuity`),
   resolveContinuityFinding:(projectId:string,id:string)=>call<any>(`/api/projects/${encodeURIComponent(projectId)}/continuity/findings/${encodeURIComponent(id)}/resolve`,{method:'POST'}),
   characterConsistencyCheck:(novelId:string,body:Record<string,unknown>)=>call<{status:string;findings:any[]}>(`/api/novels/${encodeURIComponent(novelId)}/characters/consistency-check`,{method:'POST',body:JSON.stringify(body)}),
 approveLoreProposal:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/lore/proposals/${encodeURIComponent(id)}/approve`,{method:'POST',body:JSON.stringify({reviewer:'author'})}),
 rejectLoreProposal:(novelId:string,id:string)=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/lore/proposals/${encodeURIComponent(id)}/reject`,{method:'POST',body:JSON.stringify({reviewer:'author'})}),
 credentialStatus:(provider:string)=>call<CredentialStatus>(`/api/credentials/${encodeURIComponent(provider)}`),
 saveCredential:(provider:string,credential:string)=>call<CredentialStatus>(`/api/credentials/${encodeURIComponent(provider)}`,{method:'PUT',body:JSON.stringify({provider,credential})}),
 deleteCredential:(provider:string)=>call<CredentialStatus>(`/api/credentials/${encodeURIComponent(provider)}`,{method:'DELETE'}),
 testCredential:(provider:string)=>call<{provider:string;configured:boolean;reachable:boolean}>(`/api/credentials/${encodeURIComponent(provider)}/test`,{method:'POST'}),
 visualTextWorkflow:(scope:Scope,providerId:string,modelId:string)=>call<VisualTextWorkflow>(query(scoped(scope,'visual-text-workflow'),{provider_id:providerId,model_id:modelId})),
 textRuntimeDiagnostics:(scope:Scope,providerId:string,modelId:string)=>call<TextRuntimeDiagnostics>(query(scoped(scope,'text-runtime-diagnostics'),{provider_id:providerId,model_id:modelId})),
  health:()=>call<any>('/api/health'),context:(novel:string,chapter:number,instruction:string='',target:'local'|'cloud'='cloud')=>call<any>(query('/api/context-preview',{novel_id:novel,chapter:String(chapter),instruction,target})),resource:(novel:string,name:string)=>call<Record<string,unknown>[]>(`/api/novels/${encodeURIComponent(novel)}/${encodeURIComponent(name)}`),pending:(novel:string)=>call<any[]>(query('/api/pending-canon',{novel_id:novel})),approve:(id:string,proposals?:any[])=>call<any>(`/api/pending-canon/${id}/approve`,{method:'POST',body:JSON.stringify(proposals?{proposals}:{})}),rejectCanon:(id:string)=>call<any>(`/api/pending-canon/${id}/reject`,{method:'POST'}),exportNovel:(id:string,format:'json'|'markdown'|'txt')=>call<any>(query(`/api/novels/${id}/export`,{format})),importNovel:(format:'json'|'markdown'|'txt'|'docx'|'word'|'pdf',content:string,confirm=false,contentBase64?:string)=>call<any>('/api/novels/import',{method:'POST',body:JSON.stringify({format,content,content_base64:contentBase64,confirm})}),importReviewList:(novelId:string,status?:string)=>call<{items:ImportReview[];pending:ImportReview|null}>(query(`/api/novels/${encodeURIComponent(novelId)}/import/knowledge-base/review`,{status})),importReview:(novelId:string,reviewId:string)=>call<ImportReview>(`/api/novels/${encodeURIComponent(novelId)}/import/knowledge-base/review/${encodeURIComponent(reviewId)}`),updateImportReview:(novelId:string,reviewId:string,candidates:Record<string,unknown[]>,selected?:Record<string,boolean[]>)=>call<ImportReview>(`/api/novels/${encodeURIComponent(novelId)}/import/knowledge-base/review/${encodeURIComponent(reviewId)}`,{method:'PUT',body:JSON.stringify({candidates,selected})}),reviewImportKnowledge:(novelId:string,decision:'ACCEPTED'|'REJECTED'|'SKIPPED',candidates:Record<string,unknown[]>={},options:{reviewId?:string;note?:string;selected?:Record<string,boolean[]>}={})=>call<any>(`/api/novels/${encodeURIComponent(novelId)}/import/knowledge-base/review`,{method:'POST',body:JSON.stringify({decision,candidates,review_id:options.reviewId,note:options.note,selected:options.selected})})
  ,createExport:(novelId:string,format:string)=>call<ExportJob>(query('/api/exports',{novel_id:novelId}),{method:'POST',body:JSON.stringify({format})}),
  exportJob:(jobId:string)=>call<ExportJob>(`/api/exports/${encodeURIComponent(jobId)}`),
  cancelExport:(jobId:string)=>call<ExportJob>(`/api/exports/${encodeURIComponent(jobId)}/cancel`,{method:'POST'}),
  retryExport:(jobId:string)=>call<ExportJob>(`/api/exports/${encodeURIComponent(jobId)}/retry`,{method:'POST'}),
  exportDownload:(jobId:string)=>downloadCall(`/api/exports/${encodeURIComponent(jobId)}/download`),
};
