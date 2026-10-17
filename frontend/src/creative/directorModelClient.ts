/** Explicit action client; construction and reads never dispatch a model. */
import { ApiError, type CollaborationContext } from '../api';
import type { StudioGraphTransport } from './studioGraphClient';
import { createDirectorObservationClient, checkedDirectorAdoptionReceipt, checkedDirectorStatusReceipt,
  type DirectorAdoptionReceipt, type DirectorStatusReceipt } from './directorObservationClient';
import { checkedDirectorSceneNote, checkedPlanningSnapshot, checkedVisualTarget, type PlanningSnapshot } from './studioProductionGraphContract';
import type { DirectorSceneNote, VisualTarget } from './types';

export type DirectorPreviewRequest = { expected_version: number; route_id: string; allow_synthetic?: false; max_output_tokens?: number; temperature?: number };
export type DirectorPreviewReceipt = {
  contract: 'DIRECTOR_MODEL_PREVIEW_V1'; proposal_id: string; version: number; reviewed_preview_digest: string;
  prompt: string; parameters: { max_output_tokens: number; temperature: number }; route_id: string;
  route_fingerprint: string; provider_id: string; model_id: string;
  source_document_id: string; source_version: number; source_digest: string; source_mode: 'STORYBOARD';
  local_only: true; reserve_microusd: 0; model_called: false; automatic_retry: false; quality_verification: 'NOT_RUN';
};
export type DirectorPendingProvenance = {
  method: 'MODEL_ASSISTED'; model_called: true; provider_id: string; model_id: string; model_version: string | null;
  route_fingerprint: string; synthetic: false; parameters: DirectorPreviewReceipt['parameters']; source_mode: 'STORYBOARD';
  source_document_id: string; source_version: number; source_digest: string;
  source_mapping: { source_shot_id: string; note_id: string; scene_id: string; source_number: number }[];
  job_id: string; request_digest: string; preview_digest: string; candidate_output_digest: string;
  terminal_evidence_digest: string; quality_verification: 'HUMAN_REVIEW_REQUIRED';
};
export type DirectorPendingReceipt = { contract: 'DIRECTOR_MODEL_PENDING_REVIEW_V1'; proposal_id: string;
  expected_version: number; director_notes: DirectorSceneNote[]; output_digest: string;
  visual_target: VisualTarget | null; provenance: DirectorPendingProvenance };
export type DirectorReviewSubmission = { expected_version: number; reviewed_output_digest: string;
  title: string; director_notes: DirectorSceneNote[]; visual_target?: VisualTarget | null };

function invalid(): never { throw new ApiError({ status: 200, code: 'DIRECTOR_MODEL_CONTRACT_INVALID',
  message: '模型操作的版本或来源回执不匹配。请核对原任务状态，不要重复提交。' }); }
function object(value: unknown): Record<string, unknown> { if (!value || typeof value !== 'object' || Array.isArray(value)) invalid(); return value as Record<string, unknown>; }
function closed(value: Record<string, unknown>, required: string[], optional: string[] = []) {
  if (required.some(k => !Object.hasOwn(value,k)) || Object.keys(value).some(k => !required.includes(k) && !optional.includes(k))) invalid();
}
function text(value: unknown, max=240, empty=false): string { if (typeof value !== 'string' || value.length>max || !empty&&!value.trim() || /[\u0000\u007f]/.test(value)) invalid(); return value; }
function hash(value: unknown): string { if (typeof value!=='string'||!/^[a-f0-9]{64}$/.test(value)) invalid(); return value; }
function integer(value: unknown,min=1,max=Number.MAX_SAFE_INTEGER): number { if (typeof value!=='number'||!Number.isSafeInteger(value)||value<min||value>max) invalid(); return value; }
function parameters(value: unknown): DirectorPreviewReceipt['parameters'] {
  const r=object(value);closed(r,['max_output_tokens','temperature']);
  if(typeof r.temperature!=='number'||!Number.isFinite(r.temperature)||r.temperature<0||r.temperature>2) invalid();
  return {max_output_tokens:integer(r.max_output_tokens,1,2048),temperature:r.temperature};
}
function source(row: Record<string,unknown>, expected: PlanningSnapshot) {
  if(row.source_mode!=='STORYBOARD'||row.source_document_id!==expected.id||row.source_version!==expected.version||row.source_digest!==expected.digest) invalid();
}
function previewReceipt(value: unknown,proposal: string,expected: PlanningSnapshot): DirectorPreviewReceipt {
  const r=object(value);closed(r,['contract','proposal_id','version','reviewed_preview_digest','prompt','parameters','route_id','route_fingerprint',
    'provider_id','model_id','source_document_id','source_version','source_digest','source_mode','local_only','reserve_microusd',
    'model_called','automatic_retry','quality_verification']);
  if(r.contract!=='DIRECTOR_MODEL_PREVIEW_V1'||r.proposal_id!==proposal||r.local_only!==true||r.reserve_microusd!==0
    ||r.model_called!==false||r.automatic_retry!==false||r.quality_verification!=='NOT_RUN') invalid();
  source(r,expected);
  return {contract:r.contract,proposal_id:proposal,version:integer(r.version),reviewed_preview_digest:hash(r.reviewed_preview_digest),
    prompt:text(r.prompt,8_000_000),parameters:parameters(r.parameters),route_id:text(r.route_id),route_fingerprint:hash(r.route_fingerprint),
    provider_id:text(r.provider_id),model_id:text(r.model_id),source_document_id:expected.id,source_version:expected.version,source_digest:expected.digest,
    source_mode:'STORYBOARD',local_only:true,reserve_microusd:0,model_called:false,automatic_retry:false,quality_verification:'NOT_RUN'};
}
function pendingReceipt(value: unknown,proposal: string,expected: PlanningSnapshot): DirectorPendingReceipt {
  const r=object(value);closed(r,['contract','proposal_id','expected_version','director_notes','output_digest','visual_target','provenance']);
  if(r.contract!=='DIRECTOR_MODEL_PENDING_REVIEW_V1'||r.proposal_id!==proposal||!Array.isArray(r.director_notes)||!r.director_notes.length||r.director_notes.length>200) invalid();
  const notes=r.director_notes.map(checkedDirectorSceneNote), p=object(r.provenance);
  closed(p,['method','model_called','provider_id','model_id','model_version','route_fingerprint','synthetic','parameters','source_mode',
    'source_document_id','source_version','source_digest','source_mapping','job_id','request_digest','preview_digest','candidate_output_digest','terminal_evidence_digest','quality_verification']);
  if(p.method!=='MODEL_ASSISTED'||p.model_called!==true||p.synthetic!==false||p.quality_verification!=='HUMAN_REVIEW_REQUIRED') invalid();
  source(p,expected);
  if(!Array.isArray(p.source_mapping)||p.source_mapping.length!==notes.length) invalid();
  const mapping=p.source_mapping.map((value,index)=>{
    const m=object(value);closed(m,['source_shot_id','note_id','scene_id','source_number']);
    const result={source_shot_id:text(m.source_shot_id),note_id:text(m.note_id),scene_id:text(m.scene_id),source_number:integer(m.source_number,1,10000)};
    const note=notes[index];
    if(note.id!==result.note_id||note.scene_id!==result.scene_id||note.number!==result.source_number||!note.planning) invalid();
    if(note.planning.evidence.some(e=>e.scene_id!==note.scene_id||(e.field==='dialogue' ? e.dialogue_index===null : e.dialogue_index!==null))) invalid();
    return result;
  });
  if(new Set(mapping.map(m=>m.note_id)).size!==notes.length||new Set(mapping.map(m=>m.source_shot_id)).size!==notes.length) invalid();
  const output=hash(r.output_digest);if(hash(p.candidate_output_digest)!==output) invalid();
  return {contract:r.contract,proposal_id:proposal,expected_version:integer(r.expected_version),director_notes:notes,output_digest:output,
    visual_target:r.visual_target===null?null:structuredClone(checkedVisualTarget(r.visual_target)),
    provenance:{method:'MODEL_ASSISTED',model_called:true,provider_id:text(p.provider_id),model_id:text(p.model_id),
      model_version:p.model_version===null?null:text(p.model_version,1000,true),route_fingerprint:hash(p.route_fingerprint),synthetic:false,
      parameters:parameters(p.parameters),source_mode:'STORYBOARD',source_document_id:expected.id,source_version:expected.version,source_digest:expected.digest,
      source_mapping:mapping,job_id:text(p.job_id),request_digest:hash(p.request_digest),preview_digest:hash(p.preview_digest),candidate_output_digest:output,
      terminal_evidence_digest:hash(p.terminal_evidence_digest),quality_verification:'HUMAN_REVIEW_REQUIRED'}};
}
export function checkedDirectorReviewSubmission(value: unknown): DirectorReviewSubmission {
  const r=object(value);closed(r,['expected_version','reviewed_output_digest','title','director_notes'],['visual_target']);
  if(!Array.isArray(r.director_notes)||!r.director_notes.length||r.director_notes.length>200) invalid();
  return {expected_version:integer(r.expected_version),reviewed_output_digest:hash(r.reviewed_output_digest),title:text(r.title),
    director_notes:r.director_notes.map(checkedDirectorSceneNote),
    ...(Object.hasOwn(r,'visual_target')&&r.visual_target!==undefined?{visual_target:r.visual_target===null?null:structuredClone(checkedVisualTarget(r.visual_target))}:{})};
}

function reviewExpectation(proposal: string, candidate: DirectorPendingReceipt, body: DirectorReviewSubmission): DirectorPendingReceipt {
  const candidateRow=object(candidate), p=object(candidateRow.provenance);
  const expected=pendingReceipt(candidateRow,proposal,checkedPlanningSnapshot({id:p.source_document_id,version:p.source_version,digest:p.source_digest},true));
  if(body.expected_version!==expected.expected_version||body.reviewed_output_digest!==expected.output_digest) invalid();
  return expected;
}
function assertAdoptionSource(receipt: DirectorAdoptionReceipt, expected: DirectorPendingReceipt) {
  const p=expected.provenance;
  if(receipt.source_document_id!==p.source_document_id||receipt.source_version!==p.source_version||receipt.source_digest!==p.source_digest
    ||receipt.job_id!==p.job_id||receipt.request_digest!==p.request_digest||receipt.terminal_evidence_digest!==p.terminal_evidence_digest) invalid();
}
export { pendingReceipt as checkedDirectorPendingReceipt };

export function createDirectorModelClient(projectId: string, transport: StudioGraphTransport, scope?: CollaborationContext['scope']) {
  const project=text(projectId), captured=scope?{...scope}:undefined;
  if(captured&&captured.projectId!==project) invalid();
  const expected: Record<string,string>=captured?{mode:'collaboration',novel_id:project,workspace_id:text(captured.workspaceId),storyline_id:text(captured.storylineId),branch_id:text(captured.branchId)}:{mode:'local',novel_id:project};
  const base=`/api/novels/${encodeURIComponent(project)}/experimental/creative/director-proposals`;
  const reads=createDirectorObservationClient(project,transport,captured);
  async function call(proposal: string, suffix: string, method: 'GET'|'POST', body: unknown, kind: string, signal?: AbortSignal): Promise<unknown> {
    text(proposal);const value=await transport.json<unknown>(`${base}/${encodeURIComponent(proposal)}/model-v1/${suffix}`,method,body,signal);
    if(signal?.aborted) throw new DOMException('The read was cancelled.','AbortError');
    const r=object(value);closed(r,['contract','project_id','scope','kind','receipt']);const owner=object(r.scope);
    if(r.contract!=='DIRECTOR_OBSERVATION_V1'||r.kind!==kind||r.project_id!==project||Object.keys(owner).length!==Object.keys(expected).length
      ||Object.entries(expected).some(([key,value])=>owner[key]!==value)) invalid();
    return r.receipt;
  }
  return {
    ...reads,
    async preview(proposal: string, sourcePin: PlanningSnapshot, input: DirectorPreviewRequest): Promise<DirectorPreviewReceipt> {
      const pin=checkedPlanningSnapshot(sourcePin,true), r=object(input);
      closed(r,['expected_version','route_id'],['allow_synthetic','max_output_tokens','temperature']);
      if(r.allow_synthetic!==undefined&&r.allow_synthetic!==false) invalid();
      const body={expected_version:integer(r.expected_version),route_id:text(r.route_id,160),allow_synthetic:false,
        ...parameters({max_output_tokens:r.max_output_tokens??512,temperature:r.temperature??0})};
      const result=previewReceipt(await call(proposal,'preview','POST',body,'preview'),proposal,pin);
      if(result.version!==body.expected_version+1||result.route_id!==body.route_id
        ||result.parameters.max_output_tokens!==body.max_output_tokens||result.parameters.temperature!==body.temperature) invalid();
      return result;
    },
    async readPreview(proposal: string, sourcePin: PlanningSnapshot, signal?: AbortSignal): Promise<DirectorPreviewReceipt> {
      const pin=checkedPlanningSnapshot(sourcePin,true);
      return previewReceipt(await call(proposal,'preview','GET',undefined,'preview',signal),proposal,pin);
    },
    async dispatch(proposal: string, sourcePin: PlanningSnapshot, preview: DirectorPreviewReceipt): Promise<DirectorStatusReceipt> {
      const pin=checkedPlanningSnapshot(sourcePin,true), frozen=previewReceipt(preview,proposal,pin);
      const raw=await call(proposal,'dispatch','POST',{expected_version:frozen.version,reviewed_preview_digest:frozen.reviewed_preview_digest},'status');
      const result=checkedDirectorStatusReceipt(raw,proposal);
      // Original owner commits admission, then its reservation binding.
      if(result.version!==frozen.version+2||result.reviewed_preview_digest!==frozen.reviewed_preview_digest||result.phase==='PREVIEW') invalid();
      return result;
    },
    async prepareReview(proposal: string, sourcePin: PlanningSnapshot, status: DirectorStatusReceipt): Promise<DirectorPendingReceipt> {
      const pin=checkedPlanningSnapshot(sourcePin,true), frozen=checkedDirectorStatusReceipt(status,proposal);
      if(frozen.phase!=='COMPLETED'||frozen.terminal_evidence_digest===null) invalid();
      const raw=await call(proposal,'prepare-review','POST',{expected_version:frozen.version,terminal_evidence_digest:frozen.terminal_evidence_digest},'pending-review');
      const result=pendingReceipt(raw,proposal,pin), p=result.provenance;
      if(result.expected_version!==frozen.version+1||p.job_id!==frozen.job_id||p.request_digest!==frozen.request_digest
        ||p.preview_digest!==frozen.reviewed_preview_digest||p.terminal_evidence_digest!==frozen.terminal_evidence_digest) invalid();
      return result;
    },
    async readPending(proposal: string, sourcePin: PlanningSnapshot, signal?: AbortSignal): Promise<DirectorPendingReceipt> {
      const pin=checkedPlanningSnapshot(sourcePin,true);
      return pendingReceipt(await call(proposal,'pending-review','GET',undefined,'pending-review',signal),proposal,pin);
    },
    async review(proposal: string, submission: DirectorReviewSubmission, pending: DirectorPendingReceipt): Promise<DirectorAdoptionReceipt> {
      const body=checkedDirectorReviewSubmission(submission), expected=reviewExpectation(proposal,pending,body);
      const result=checkedDirectorAdoptionReceipt(await call(proposal,'review','POST',body,'adopted-draft'),proposal);
      if(result.reviewed_version!==body.expected_version||result.candidate_output_digest!==body.reviewed_output_digest) invalid();
      assertAdoptionSource(result,expected);
      return result;
    },
    async reconcileReview(proposal: string, submission: DirectorReviewSubmission, pending: DirectorPendingReceipt, signal?: AbortSignal): Promise<DirectorAdoptionReceipt> {
      const body=checkedDirectorReviewSubmission(submission), expected=reviewExpectation(proposal,pending,body);
      // This POST is the server's exact read-only reconciliation endpoint.
      const result=checkedDirectorAdoptionReceipt(await call(proposal,'reconcile-review','POST',body,'adopted-draft',signal),proposal);
      if(result.reviewed_version!==body.expected_version||result.candidate_output_digest!==body.reviewed_output_digest) invalid();
      assertAdoptionSource(result,expected);
      return result;
    },
    async cancel(proposal: string, status: DirectorStatusReceipt): Promise<DirectorStatusReceipt> {
      const frozen=checkedDirectorStatusReceipt(status,proposal);
      if(!['ADMITTED','RUNNING'].includes(frozen.phase)||!frozen.job_id||!frozen.request_digest) invalid();
      const body={expected_version:frozen.version,job_id:frozen.job_id,request_digest:frozen.request_digest,reviewed_preview_digest:frozen.reviewed_preview_digest};
      const result=checkedDirectorStatusReceipt(await call(proposal,'cancel','POST',body,'status'),proposal);
      if(result.version!==frozen.version||result.job_id!==frozen.job_id||result.request_digest!==frozen.request_digest
        ||result.reviewed_preview_digest!==frozen.reviewed_preview_digest||!result.cancellation_requested) invalid();
      return result;
    },
  };
}
export type DirectorModelClient=ReturnType<typeof createDirectorModelClient>;
