// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import {AiWritingPanel,type AiVariantDraft} from './AiWritingPanel';

const models=[{provider_id:'deepseek',model_id:'deepseek-chat',display_name:'DeepSeek Chat',available:true}];
const readiness={diagnostics_contract_version:'1',read_only:true as const,provider_id:'deepseek',model_id:'deepseek-chat',state:'READY' as const,state_label:'Ready',explanation:'',author_action:'',safe_capabilities:[]};
const base={models,selection:{providerId:'deepseek',modelId:'deepseek-chat'},readiness,readinessLoading:false,readinessError:false,onGenerate:vi.fn(),onAccept:vi.fn(),onReject:vi.fn()};
afterEach(()=>cleanup());

describe('AI writing variants',()=>{
  it('requests three variants when the author selects three',()=>{
    const onGenerateVariants=vi.fn();render(<AiWritingPanel {...base} onGenerateVariants={onGenerateVariants}/>);
    fireEvent.click(screen.getByRole('button',{name:'3'}));
    fireEvent.click(screen.getByRole('button',{name:'生成创作下一章草稿'}));
    expect(onGenerateVariants).toHaveBeenCalledWith('continue','',3,'');
    expect(base.onGenerate).not.toHaveBeenCalled();
  });

  it('switches candidates and applies the selected draft',()=>{
    const variants:AiVariantDraft[]=[
      {id:'a',variantIndex:1,status:'ready',output:'方案一'},
      {id:'b',variantIndex:2,status:'ready',output:'方案二'},
    ];
    const onSelectVariant=vi.fn(),onAccept=vi.fn();
    const {rerender}=render(<AiWritingPanel {...base} variants={variants} activeVariant={0} onSelectVariant={onSelectVariant} onAccept={onAccept}/>);
    expect(screen.getByText('方案一')).toBeTruthy();
    fireEvent.click(screen.getByRole('tab',{name:'方案 2 · 可用'}));expect(onSelectVariant).toHaveBeenCalledWith(1);
    rerender(<AiWritingPanel {...base} variants={variants} activeVariant={1} onSelectVariant={onSelectVariant} onAccept={onAccept}/>);
    expect(screen.getByText('方案二')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'采用草稿'}));expect(onAccept).toHaveBeenCalledWith(variants[1]);
  });

  it('keeps completed candidates usable when another candidate fails',()=>{
    const variants:AiVariantDraft[]=[
      {id:'failed',variantIndex:1,status:'failed',output:'',error:'provider unavailable'},
      {id:'ready',variantIndex:2,status:'ready',output:'可采用的方案'},
    ];
    const onSelectVariant=vi.fn(),onReject=vi.fn(),onAccept=vi.fn(),onRetry=vi.fn();
    const {rerender}=render(<AiWritingPanel {...base} variants={variants} activeVariant={0} onSelectVariant={onSelectVariant} onReject={onReject} onAccept={onAccept} onRetry={onRetry}/>);
    expect(screen.getByRole('tab',{name:'方案 1 · 失败'})).toBeTruthy();
    expect(screen.getByText('其他已完成的候选仍可预览和采用。')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'重新生成此候选'}));
    expect(onRetry).toHaveBeenCalledWith(variants[0]);
    fireEvent.click(screen.getByRole('button',{name:'移除失败候选'}));
    expect(onReject).toHaveBeenCalledWith(variants[0]);
    fireEvent.click(screen.getByRole('tab',{name:'方案 2 · 可用'}));
    expect(onSelectVariant).toHaveBeenCalledWith(1);
    rerender(<AiWritingPanel {...base} variants={variants} activeVariant={1} onSelectVariant={onSelectVariant} onReject={onReject} onAccept={onAccept} onRetry={onRetry}/>);
    expect(screen.getByText('可采用的方案')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'采用草稿'}));
    expect(onAccept).toHaveBeenCalledWith(variants[1]);
  });

  it('shows a timed out candidate as retryable',()=>{
    const timedOut:AiVariantDraft={id:'timeout',variantIndex:1,status:'failed',output:'',error:'候选生成超时，请重新生成此候选。'};
    const onRetry=vi.fn();render(<AiWritingPanel {...base} variants={[timedOut]} onRetry={onRetry}/>);
    expect(screen.getByText('候选生成超时，请重新生成此候选。')).toBeTruthy();
    fireEvent.click(screen.getByRole('button',{name:'重新生成此候选'}));
    expect(onRetry).toHaveBeenCalledWith(timedOut);
  });
  it('does not treat an unconfigured text provider as a ready draft',()=>{
    const failed:AiVariantDraft={id:'unconfigured',variantIndex:1,status:'failed',output:'',error:'TEXT_PROVIDER_NOT_CONFIGURED'};
    render(<AiWritingPanel {...base} variants={[failed]}/>);
    expect(screen.getByText('未配置可用文本模型，未调用 DeepSeek，不能当作创作完成。')).toBeTruthy();
    expect(screen.queryByRole('button',{name:'采用草稿'})).toBeNull();
  });
  it('disables acceptance for a recovered stale candidate',()=>{
    const stale:AiVariantDraft={id:'stale',variantIndex:1,status:'ready',output:'保留的草稿',acceptBlocked:true,acceptBlockedReason:'正文已在生成期间发生变化，请先处理版本冲突。'};
    const onResolveConflict=vi.fn();render(<AiWritingPanel {...base} variants={[stale]} onResolveConflict={onResolveConflict}/>);
    expect(screen.getByText(stale.acceptBlockedReason!)).toBeTruthy();
    expect((screen.getByRole('button',{name:'采用草稿'}) as HTMLButtonElement).disabled).toBe(true);
    fireEvent.click(screen.getByRole('button',{name:'比较与手动合并'}));
    expect(onResolveConflict).toHaveBeenCalledWith(stale);
  });
});
