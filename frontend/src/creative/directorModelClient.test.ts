import { describe, expect, it, vi } from 'vitest';
import { ApiError } from '../api';
import { createDirectorModelClient, checkedDirectorReviewSubmission, checkedDirectorPendingReceipt } from './directorModelClient';
import { checkedDirectorStatusReceipt } from './directorObservationClient';
import captured from './directorModelActionWire.testFixture.json';
const clone=<T,>(value:T):T=>JSON.parse(JSON.stringify(value));
const project=captured.preview.project_id, proposal=captured.preview.receipt.proposal_id;
const source={id:captured.preview.receipt.source_document_id,version:captured.preview.receipt.source_version,digest:captured.preview.receipt.source_digest};
const previewInput=()=>({expected_version:captured.preview.receipt.version-1,route_id:captured.preview.receipt.route_id,allow_synthetic:false as const,max_output_tokens:512,temperature:0});
function setup(...responses:unknown[]) {
  const json=vi.fn();responses.forEach(value=>json.mockResolvedValueOnce(value));
  return {json,client:createDirectorModelClient(project,{json})};
}

describe('explicit Director model transport client',()=>{
  it('issues exactly one request for each explicitly invoked action and accepts actual captured responses',async()=>{
    const {json,client}=setup(captured.preview,captured.completed_status,captured.pending,captured.adopted);
    expect(json).not.toHaveBeenCalled();
    const preview=await client.preview(proposal,source,previewInput());
    const status=await client.dispatch(proposal,source,preview);
    const pending=await client.prepareReview(proposal,source,status);
    const body=checkedDirectorReviewSubmission(captured.submitted_review);
    const adopted=await client.review(proposal,body,pending);
    expect(pending).toEqual(captured.pending.receipt);expect(adopted).toEqual(captured.adopted.receipt);
    expect(json.mock.calls.map(([url,method])=>[url.split('/').at(-1),method])).toEqual([
      ['preview','POST'],['dispatch','POST'],['prepare-review','POST'],['review','POST']]);
    expect(json.mock.calls[1][2]).toEqual({expected_version:preview.version,reviewed_preview_digest:preview.reviewed_preview_digest});
    expect(json.mock.calls[2][2]).toEqual({expected_version:status.version,terminal_evidence_digest:status.terminal_evidence_digest});
  });
  it('reopens preview and pending with GET only and detaches returned notes',async()=>{
    const raw=clone(captured.pending),{json,client}=setup(captured.preview,raw);
    expect(await client.readPreview(proposal,source)).toEqual(captured.preview.receipt);
    const pending=await client.readPending(proposal,source);
    pending.director_notes[0].note='local edit';
    pending.director_notes[0].planning!.rationale='local reasoning';
    expect(raw.receipt.director_notes[0]).toEqual(captured.pending.receipt.director_notes[0]);
    expect(json.mock.calls.every(call=>call[1]==='GET'&&call[2]===undefined)).toBe(true);
  });
  it('uses only the exact read-only reconciliation endpoint after an uncertain review',async()=>{
    const error=new ApiError({status:409,code:'DIRECTOR_MODEL_ACTION_NOT_CONFIRMED',message:'Uncertain'});
    const json=vi.fn().mockRejectedValueOnce(error).mockResolvedValueOnce(captured.adopted);
    const client=createDirectorModelClient(project,{json}),body=checkedDirectorReviewSubmission(captured.submitted_review);
    const pending=checkedDirectorPendingReceipt(captured.pending.receipt,proposal,source);
    await expect(client.review(proposal,body,pending)).rejects.toBe(error);expect(json).toHaveBeenCalledTimes(1);
    expect(await client.reconcileReview(proposal,body,pending)).toEqual(captured.adopted.receipt);
    expect(json.mock.calls[1][0]).toMatch(/\/reconcile-review$/);expect(json.mock.calls[1][2]).toEqual(body);
    expect(json).toHaveBeenCalledTimes(2);
  });
  it.each(['paid','called','fallback','source','route','parameters','version','private-field'] as const)('rejects a changed preview %s',async change=>{
    const value:any=clone(captured.preview);
    if(change==='paid')value.receipt.reserve_microusd=1;
    if(change==='called')value.receipt.model_called=true;
    if(change==='fallback')value.receipt.automatic_retry=true;
    if(change==='source')value.receipt.source_digest='0'.repeat(64);
    if(change==='route')value.receipt.route_id='different';
    if(change==='parameters')value.receipt.parameters.temperature=1;
    if(change==='version')value.receipt.version++;
    if(change==='private-field')value.receipt.host_principal='private';
    const {json,client}=setup(value);
    await expect(client.preview(proposal,source,previewInput())).rejects.toBeInstanceOf(ApiError);
    expect(json).toHaveBeenCalledTimes(1);
  });
  it.each(['scope','source','mapping','duplicate','missing-planning','evidence-scene','evidence-index','output','quality','private-field'] as const)('rejects invalid pending %s',async change=>{
    const value:any=clone(captured.pending),p=value.receipt.provenance;
    if(change==='scope')value.scope.branch_id='foreign';
    if(change==='source')p.source_version++;
    if(change==='mapping')p.source_mapping[0].note_id='foreign';
    if(change==='duplicate')p.source_mapping[1].source_shot_id=p.source_mapping[0].source_shot_id;
    if(change==='missing-planning')delete value.receipt.director_notes[0].planning;
    if(change==='evidence-scene')value.receipt.director_notes[0].planning.evidence[0].scene_id='foreign';
    if(change==='evidence-index')value.receipt.director_notes[0].planning.evidence[0].dialogue_index=0;
    if(change==='output')p.candidate_output_digest='0'.repeat(64);
    if(change==='quality')p.quality_verification='PASS';
    if(change==='private-field')p.reservation_id='private';
    const {json,client}=setup(value);await expect(client.readPending(proposal,source)).rejects.toBeInstanceOf(ApiError);
    expect(json).toHaveBeenCalledTimes(1);
  });
  it('snapshots preview intent before awaiting a response',async()=>{
    const input=previewInput(),{json,client}=setup(captured.preview);
    const request=client.preview(proposal,source,input);input.route_id='changed';
    expect((await request).route_id).toBe(captured.preview.receipt.route_id);
    expect(json.mock.calls[0][2].route_id).toBe(captured.preview.receipt.route_id);
  });
  it('keeps omitted visual target distinct from explicit null',()=>{
    const body=checkedDirectorReviewSubmission(captured.submitted_review);
    expect(Object.hasOwn(body,'visual_target')).toBe(false);
    expect(checkedDirectorReviewSubmission({...body,visual_target:null}).visual_target).toBeNull();
    expect(Object.hasOwn(checkedDirectorReviewSubmission({...body,visual_target:null}),'visual_target')).toBe(true);
  });
  it.each(['synthetic','invalid-version','extra'] as const)('rejects invalid preview input %s before any request',async change=>{
    const input:any=previewInput();if(change==='synthetic')input.allow_synthetic=true;
    if(change==='invalid-version')input.expected_version=true;if(change==='extra')input.terminal_evidence=false;
    const {json,client}=setup();await expect(client.preview(proposal,source,input)).rejects.toBeInstanceOf(ApiError);
    expect(json).not.toHaveBeenCalled();
  });
  it('refuses to prepare an unfinished job or cancel a terminal job',async()=>{
    const {json,client}=setup(),complete=checkedDirectorStatusReceipt(captured.completed_status.receipt,proposal);
    await expect(client.cancel(proposal,complete)).rejects.toBeInstanceOf(ApiError);
    await expect(client.prepareReview(proposal,source,{...complete,phase:'RUNNING',terminal_evidence_digest:null})).rejects.toBeInstanceOf(ApiError);
    expect(json).not.toHaveBeenCalled();
  });
  it('cancels only the exact active job without claiming upstream termination',async()=>{
    const running=checkedDirectorStatusReceipt({...captured.completed_status.receipt,phase:'RUNNING',terminal_evidence_digest:null},proposal);
    const response={...clone(captured.completed_status),receipt:{...running,cancellation_requested:true}};
    const {json,client}=setup(response);
    const receipt=await client.cancel(proposal,running);
    expect(receipt.cancellation_requested).toBe(true);expect(receipt.cancellation_confirmed).toBe(false);
    expect(receipt.upstream_cancellation_guaranteed).toBe(false);
    expect(json.mock.calls[0][2]).toEqual({expected_version:running.version,job_id:running.job_id,request_digest:running.request_digest,reviewed_preview_digest:running.reviewed_preview_digest});
  });
  it('does not expose a late aborted pending read',async()=>{
    const {client}=setup(captured.pending),controller=new AbortController();
    const request=client.readPending(proposal,source,controller.signal);controller.abort();
    await expect(request).rejects.toMatchObject({name:'AbortError'});
  });
});

it.each(['source_document_id','source_version','source_digest','job_id','request_digest','terminal_evidence_digest'] as const)('rejects an adopted receipt with a different %s',async field=>{
  const value:any=clone(captured.adopted);
  value.receipt[field]=field==='source_version'?2:field.endsWith('digest')?'0'.repeat(64):'foreign';
  const {json,client}=setup(value),body=checkedDirectorReviewSubmission(captured.submitted_review);
  const pending=checkedDirectorPendingReceipt(captured.pending.receipt,proposal,source);
  await expect(client.review(proposal,body,pending)).rejects.toBeInstanceOf(ApiError);
  expect(json).toHaveBeenCalledTimes(1);
});
