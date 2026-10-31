import {expect,it,vi} from 'vitest';
import captured from './directorScreenplayWire.testFixture.json';
import {createDirectorModelClient} from './directorModelClient';
const p=captured.preview.receipt,pin={id:p.source_document_id,version:p.source_version,digest:p.source_digest};
const input={expected_version:p.version-1,route_id:p.route_id,allow_synthetic:false as const,max_output_tokens:p.parameters.max_output_tokens,temperature:p.parameters.temperature};
it('decodes actual captured screenplay HTTP receipts and keeps every action on V2',async()=>{
 const json=vi.fn().mockResolvedValueOnce(captured.preview).mockResolvedValueOnce(captured.completed_status).mockResolvedValueOnce(captured.pending).mockResolvedValueOnce(captured.adopted);
 const client=createDirectorModelClient(captured.preview.project_id,{json},undefined,'SCREENPLAY');
 expect(json).not.toHaveBeenCalled();const preview=await client.preview(p.proposal_id,pin,input);
 const status=await client.dispatch(p.proposal_id,pin,preview);const pending=await client.prepareReview(p.proposal_id,pin,status);
 expect(pending).toEqual(captured.pending.receipt);
 expect(await client.review(p.proposal_id,captured.submitted_review as never,pending)).toEqual(captured.adopted.receipt);
 expect(json.mock.calls).toHaveLength(4);expect(json.mock.calls.every(([url])=>url.includes('/model-v2/'))).toBe(true);
});
it.each(['mode','contract','mapping','sequence','shot','source'])('rejects mixed or changed %s without fallback',async change=>{
 const bad=structuredClone(captured.pending) as any;
 if(change==='mode')bad.receipt.provenance.source_mode='STORYBOARD';
 if(change==='contract')bad.receipt.contract='DIRECTOR_MODEL_PENDING_REVIEW_V1';
 if(change==='mapping')bad.receipt.provenance.source_mapping[0].note_id='foreign';
 if(change==='sequence')bad.receipt.provenance.source_mapping[0].source_sequence=true;
 if(change==='shot')bad.receipt.provenance.source_mapping[0].source_shot_id='fabricated';
 if(change==='source')bad.receipt.provenance.source_digest='0'.repeat(64);
 const json=vi.fn().mockResolvedValue(bad);const client=createDirectorModelClient(captured.preview.project_id,{json},undefined,'SCREENPLAY');
 await expect(client.readPending(p.proposal_id,pin)).rejects.toThrow();expect(json).toHaveBeenCalledTimes(1);
});
it('requires explicit source selection and preserves the captured read path',async()=>{
 const json=vi.fn().mockResolvedValue(captured.preview);const legacy=createDirectorModelClient(captured.preview.project_id,{json});
 await expect(legacy.readPreview(p.proposal_id,pin)).rejects.toThrow();
 const client=createDirectorModelClient(captured.preview.project_id,{json},undefined,'SCREENPLAY');
 json.mockResolvedValue(captured.completed_status);await client.readStatus(p.proposal_id);
 expect(json.mock.calls.at(-1)?.[0]).toContain('/model-v2/status');
});
