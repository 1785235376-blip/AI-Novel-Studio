import {expect,it} from 'vitest';
import native from './fixtures/canvasVideoTrim.native.json';
import {checkedCanvasVideoTaskCommand,checkedCanvasVideoTaskPreview} from './canvasVideoTrimTask';
const clone=<T,>(v:T):T=>structuredClone(v);
const command=()=>({...clone(native.command),request_id:'explicit-child',derived_from:{owner:'timeline',job_id:native.queued.id,job_version:3,request_id:native.queued.request_id,request_digest:native.queued.request_digest,receipt_digest:null}});
it('preserves the old omitted field byte structure and accepts the additive six-field origin',()=>{
 expect(checkedCanvasVideoTaskCommand(native.command)).toEqual(native.command);
 expect(Object.hasOwn(checkedCanvasVideoTaskCommand(native.command),'derived_from')).toBe(false);
 expect(checkedCanvasVideoTaskCommand(command())).toEqual(command());
});
it.each(['null','extra','owner','version','unsafe-version','same-request','request-id','digest','receipt','missing-receipt'])('rejects malformed derived origin %s before transport',change=>{
 const c:any=command();
 if(change==='null')c.derived_from=null;
 else if(change==='extra')c.derived_from.unreviewed=true;
 else if(change==='owner')c.derived_from.owner='video';
 else if(change==='version')c.derived_from.job_version=0;
 else if(change==='unsafe-version')c.derived_from.job_version=2**53;
 else if(change==='same-request')c.request_id=c.derived_from.request_id;
 else if(change==='request-id')c.derived_from.request_id='unsafe/request';
 else if(change==='digest')c.derived_from.request_digest='unknown';
 else if(change==='receipt')c.derived_from.receipt_digest='unknown';
 else delete c.derived_from.receipt_digest;
 expect(()=>checkedCanvasVideoTaskCommand(c)).toThrow();
});
it.each(['job_id','job_version','request_id','request_digest','receipt_digest'])('rejects preview detachment of the reviewed parent %s',key=>{
 const c=checkedCanvasVideoTaskCommand(command());
 const p:any={...clone(native.preview),command:clone(c)};
 p.command.derived_from[key]=key==='job_version'?4:key.includes('digest')?'a'.repeat(64):'other-parent';
 expect(()=>checkedCanvasVideoTaskPreview(p,c)).toThrow();
});
