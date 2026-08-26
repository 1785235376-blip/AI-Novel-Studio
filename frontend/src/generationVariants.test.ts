import {describe,expect,it} from 'vitest';
import {isGenerationTerminal,isRecoveredDraftStale,recoverGenerationJob,VARIANT_TIMEOUT_ERROR,workingVariantIds} from './App';
import {generationFailureMessage} from './novel/AiWritingPanel';

describe('variant generation cancellation',()=>{
  it('cancels only candidates that are still working',()=>{
    expect(workingVariantIds([
      {id:'working-a',variantIndex:1,status:'working',output:''},
      {id:'ready',variantIndex:2,status:'ready',output:'done'},
      {id:'failed',variantIndex:3,status:'failed',output:''},
      {id:'working-b',variantIndex:4,status:'working',output:''},
    ])).toEqual(['working-a','working-b']);
  });
  it('recognizes all backend terminal states',()=>{
    expect(['COMPLETED','FAILED','CANCELLED'].every(isGenerationTerminal)).toBe(true);
    expect(isGenerationTerminal('GENERATING')).toBe(false);
  });
  it('shows the actionable timeout message without exposing arbitrary backend errors',()=>{
    expect(generationFailureMessage(VARIANT_TIMEOUT_ERROR)).toBe(VARIANT_TIMEOUT_ERROR);
    expect(generationFailureMessage('provider request id secret')).toBe('生成失败，请重试');
    expect(generationFailureMessage('服务重启导致生成中断，请重新生成。')).toBe('服务重启导致生成中断，请重新生成。');
  });
  it('recovers an interrupted stream by polling and uses the authoritative complete output',async()=>{
    const states=[
      {status:'GENERATING',output:'partial from server'},
      {status:'COMPLETED',output:'authoritative complete output'},
    ];
    const updates:any[]=[];
    const result=await recoverGenerationJob('job',async()=>states.shift(),state=>updates.push(state),{attempts:3,intervalMs:0,wait:async()=>{}});
    expect(result.output).toBe('authoritative complete output');
    expect(updates.map(item=>item.output)).toEqual(['partial from server','authoritative complete output']);
  });
  it('returns undefined when recovery polling reaches its limit',async()=>{
    const result=await recoverGenerationJob('job',async()=>({status:'GENERATING',output:''}),()=>undefined,{attempts:2,intervalMs:0,wait:async()=>{}});
    expect(result).toBeUndefined();
  });
  it('blocks recovered drafts when the chapter version changed',()=>{
    expect(isRecoveredDraftStale(3,4)).toBe(true);
    expect(isRecoveredDraftStale(4,4)).toBe(false);
    expect(isRecoveredDraftStale(undefined,4)).toBe(false);
  });
});
