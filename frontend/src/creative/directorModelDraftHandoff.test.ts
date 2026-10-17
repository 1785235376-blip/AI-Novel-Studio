import { expect, it, vi } from 'vitest';
import { readVerifiedModelDraft } from './directorModelDraftHandoff';
import { checkedDirectorAdoptionReceipt } from './directorObservationClient';
import type { CreativeDocument } from './types';
import captured from './directorModelActionWire.testFixture.json';
const receipt = () => checkedDirectorAdoptionReceipt(captured.adopted.receipt,captured.adopted.receipt.proposal_id);
// Keep genuine captured wire bytes: the legacy CreativeDocument type names actor_id,
// while this backend export carries created_by. Handoff never fabricates or uses that field.
function setup() {
 const expected=receipt(), exported={document:structuredClone(captured.draft) as unknown as CreativeDocument,document_digest:expected.document.digest,format:'json',boundary:'original owner'};
 const model={readAdoptedDraft:vi.fn(async()=>receipt())};
 const creative={export:vi.fn(async()=>exported)}; const current=vi.fn();
 return {expected,exported,model,creative,current};
}
it('explicitly reopens exact adopted draft through original reads without a graph write',async()=>{
 const e=setup(),signal=new AbortController().signal;
 const result=await readVerifiedModelDraft(e.model,e.creative,e.expected,e.current,signal);
 expect(result.document).toEqual(e.exported.document);expect(result.document).not.toBe(e.exported.document);
 expect(result.pin).toEqual({id:e.expected.document.document_id,version:e.expected.document.version,digest:e.expected.document.digest});
 expect(e.model.readAdoptedDraft).toHaveBeenCalledTimes(2);expect(e.model.readAdoptedDraft).toHaveBeenCalledWith(e.expected.proposal_id,signal);
 expect(e.creative.export).toHaveBeenCalledTimes(1);expect(e.current).toHaveBeenCalledTimes(4);
});
it.each(['document_id','version','digest'] as const)('rejects a changed exported %s',async field=>{
 const e=setup();if(field==='digest')e.exported.document_digest='f'.repeat(64);
 else if(field==='document_id')e.exported.document.id='different';else e.exported.document.version++;
 await expect(readVerifiedModelDraft(e.model,e.creative,e.expected,e.current)).rejects.toThrow();expect(e.model.readAdoptedDraft).toHaveBeenCalledTimes(1);
});
it.each(['mode','status','source'] as const)('rejects changed %s before final publication',async field=>{
 const e=setup();if(field==='mode')e.exported.document.mode='STORYBOARD';else if(field==='status')e.exported.document.status='APPROVED';
 else e.exported.document.source_documents={};
 await expect(readVerifiedModelDraft(e.model,e.creative,e.expected,e.current)).rejects.toThrow();
});
it.each([1,2])('rejects changed adoption metadata at receipt read %i',async number=>{
 const e=setup(),wrong={...receipt(),review_action_digest:'f'.repeat(64)};
 e.model.readAdoptedDraft.mockResolvedValueOnce(number===1?wrong:receipt()).mockResolvedValueOnce(wrong);
 await expect(readVerifiedModelDraft(e.model,e.creative,e.expected,e.current)).rejects.toThrow();
 expect(e.creative.export).toHaveBeenCalledTimes(number===1?0:1);
});
it.each([1,2,3,4])('checks current authority at boundary %i',async point=>{
 const e=setup();let count=0;e.current.mockImplementation(()=>{if(++count===point)throw new Error('retired');});
 await expect(readVerifiedModelDraft(e.model,e.creative,e.expected,e.current)).rejects.toThrow('retired');
});
it('honors pre-cancelled reads without reaching either owner',async()=>{
 const e=setup(),abort=new AbortController();abort.abort();
 await expect(readVerifiedModelDraft(e.model,e.creative,e.expected,e.current,abort.signal)).rejects.toMatchObject({name:'AbortError'});
 expect(e.model.readAdoptedDraft).not.toHaveBeenCalled();expect(e.creative.export).not.toHaveBeenCalled();
});
it('snapshots caller receipt and exported document across awaits',async()=>{
 const e=setup();e.model.readAdoptedDraft.mockImplementationOnce(async()=>{e.expected.review_action_digest='e'.repeat(64);return receipt();})
 .mockImplementationOnce(async()=>{e.exported.document.title='mutated later';return receipt();});
 const original=e.exported.document.title;
 const result=await readVerifiedModelDraft(e.model,e.creative,e.expected,e.current);
 expect(result.document.title).toBe(original);expect(result.receipt.review_action_digest).toBe(receipt().review_action_digest);
});
