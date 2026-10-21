import {expect,it} from 'vitest';
import {audioDraftStamp,checkedAudioDraftSummary} from './audioDraftSummary';
import {audioDraftSummary} from './summary.testFixtures';
it('copies only a strictly checked immutable display projection without changing the source',()=>{
 const raw=audioDraftSummary(),before=structuredClone(raw),view=checkedAudioDraftSummary(raw);expect(view).toEqual(before);expect(view).not.toBe(raw);expect(Object.isFrozen(view)).toBe(true);expect(raw).toEqual(before);
 raw.gainDb=-3;expect(view.gainDb).toBe(-6.5);
});
it('distinguishes missing optional values from explicit zero',()=>{
 const raw=audioDraftSummary();delete raw.gainDb;delete raw.fadeInMs;delete raw.fadeOutMs;delete raw.templateGraphId;delete raw.templateVersion;delete raw.parentJobId;delete raw.parentJobVersion;
 expect(checkedAudioDraftSummary(raw)).toEqual(raw);expect(Object.hasOwn(checkedAudioDraftSummary(raw),'gainDb')).toBe(false);
 expect(checkedAudioDraftSummary({...raw,gainDb:0,fadeInMs:0,fadeOutMs:0})).toMatchObject({gainDb:0,fadeInMs:0,fadeOutMs:0});
});
it.each([{version:0},{version:2**53},{sourceVersion:1.5},{canvasVersion:true},{inMs:-1},{outMs:100},{outMs:120101},{gainDb:NaN},{gainDb:Infinity},{gainDb:-60.1},{gainDb:12.1},{gainDb:null},{gainDb:undefined},{fadeInMs:1.5},{fadeOutMs:-1},{fadeInMs:501,fadeOutMs:500},{timelineDigest:'unknown'},{draftDigest:'B'.repeat(64)},{requestId:'with space'},{sourceId:''},{canvasId:'a\u0000b'},{templateVersion:undefined},{parentJobId:undefined},{proof:{authorized:true}},{error_code:'SYNTHETIC_SECRET_DO_NOT_SHOW'}])('rejects unknown, incomplete or invalid summaries: %j',bad=>{
 expect(()=>checkedAudioDraftSummary({...audioDraftSummary(),...bad})).toThrow('AUDIO_DRAFT_SUMMARY_INVALID');
});
it('does not invent current authority for unstringifiable owners and tracks function identity',()=>{
 const cycle:any={};cycle.self=cycle;expect(audioDraftStamp(cycle)).toBeUndefined();const f=()=>true;expect(audioDraftStamp({f})).toBe(audioDraftStamp({f}));expect(audioDraftStamp({f})).not.toBe(audioDraftStamp({f:()=>true}));
});

it('captures source getters once before validation and keeps an owned data-only copy',()=>{
 const raw=audioDraftSummary();let reads=0;Object.defineProperty(raw,'gainDb',{enumerable:true,get(){reads++;return -6.5;}});
 const checked=checkedAudioDraftSummary(raw);expect(reads).toBe(1);expect(Object.getOwnPropertyDescriptor(checked,'gainDb')?.get).toBeUndefined();expect(checked.gainDb).toBe(-6.5);
});
