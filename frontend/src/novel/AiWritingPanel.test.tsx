// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,describe,expect,it,vi} from 'vitest';
import type {TextRuntimeDiagnostics} from '../api';
import {AiDraftReview,AiWritingPanel,generationFailureMessage,lineDiff} from './AiWritingPanel';

afterEach(()=>{cleanup();delete (window as {chrome?:unknown}).chrome;});
const selection={providerId:'deepseek',modelId:'deepseek-chat'};
const model={provider_id:'deepseek',model_id:'deepseek-chat',display_name:'DeepSeek Chat',available:false};
const diagnostics=(state:TextRuntimeDiagnostics['state']):TextRuntimeDiagnostics=>({diagnostics_contract_version:'text-runtime-diagnostics/v1',read_only:true,provider_id:'deepseek',model_id:'deepseek-chat',state,state_label:state,explanation:'technical detail',author_action:'technical action',safe_capabilities:['generate','stream']});
const base={packagedMode:true,models:[model],selection,onSelectionChange:vi.fn(),onGenerate:vi.fn(),onCancel:vi.fn(),onAccept:vi.fn(),onReject:vi.fn()};

describe('AI writing product flow',()=>{
  it('shows selected DeepSeek as unconfigured without enabling generation or exposing credentials',()=>{
    render(<AiWritingPanel {...base} readiness={diagnostics('NOT_CONFIGURED')}/>);
    expect(screen.getByText('DeepSeek Chat',{selector:'p'})).toBeTruthy();expect(screen.getByText('尚未配置')).toBeTruthy();
    expect((screen.getByRole('button',{name:'生成创作下一章草稿'}) as HTMLButtonElement).disabled).toBe(true);
    expect(screen.queryByText('AI 已就绪')).toBeNull();expect(screen.queryByText('本机默认')).toBeNull();expect(screen.queryByText('默认模型')).toBeNull();
    expect((screen.getByLabelText('DeepSeek API Key') as HTMLInputElement).getAttribute('type')).toBe('password');
  });
  it('shows authoritative readiness and submits the selected operation with trimmed instructions',()=>{
    const generate=vi.fn();render(<AiWritingPanel {...base} readiness={diagnostics('READY')} onGenerate={generate}/>);
    expect(screen.getByText('可以开始生成')).toBeTruthy();expect((screen.getByRole('button',{name:'生成创作下一章草稿'}) as HTMLButtonElement).disabled).toBe(false);
    fireEvent.click(screen.getByRole('tab',{name:'润色'}));fireEvent.change(screen.getByLabelText('附加要求（可选）'),{target:{value:'  更克制  '}});fireEvent.click(screen.getByRole('button',{name:'生成润色草稿'}));expect(generate).toHaveBeenCalledWith('polish','更克制','');
  });
  it('keeps loading neutral and distinguishes unavailable from unconfigured',()=>{
    const view=render(<AiWritingPanel {...base} readinessLoading/>);expect(screen.getByText('正在检查模型状态…')).toBeTruthy();expect(screen.queryByText('尚未配置')).toBeNull();
    view.rerender(<AiWritingPanel {...base} readiness={diagnostics('UNAVAILABLE')}/>);expect(screen.getByText('暂不可用')).toBeTruthy();expect(screen.queryByText('尚未配置')).toBeNull();
  });
  it('shows generation progress, locks route mutation, and exposes one accessible cancel action',()=>{
    const cancel=vi.fn();render(<AiWritingPanel {...base} readiness={diagnostics('READY')} generating onCancel={cancel}/>);
    expect(screen.getByText('生成中…')).toBeTruthy();expect(screen.queryByRole('button',{name:'生成创作下一章草稿'})).toBeNull();const stop=screen.getByRole('button',{name:'停止生成'});fireEvent.click(stop);expect(cancel).toHaveBeenCalledTimes(1);expect((screen.getByLabelText('文本模型') as HTMLSelectElement).disabled).toBe(true);
  });
  it('prevents duplicate cancel requests and reports intentional cancellation without an error',()=>{
    const cancel=vi.fn();const view=render(<AiWritingPanel {...base} readiness={diagnostics('READY')} generating cancelling onCancel={cancel}/>);const stopping=screen.getByRole('button',{name:'正在停止…'}) as HTMLButtonElement;expect(stopping.disabled).toBe(true);fireEvent.click(stopping);expect(cancel).not.toHaveBeenCalled();
    view.rerender(<AiWritingPanel {...base} readiness={diagnostics('READY')} cancelled/>);expect(screen.getByText('已停止生成')).toBeTruthy();expect(screen.queryByText('生成失败，请重试')).toBeNull();
  });
  it('sanitizes generation failure, preserves retry, and keeps raw errors out of primary UI',()=>{
    const raw='HTTP 500 provider_id=deepseek request_id=secret';render(<AiWritingPanel {...base} readiness={diagnostics('READY')} error={raw} draft={{id:'d',output:'',status:'failed',error:raw}}/>);
    expect(screen.getByText('生成失败')).toBeTruthy();expect(screen.getByRole('alert').textContent).toBe('生成失败，请重试');expect(screen.queryByText(raw)).toBeNull();expect((screen.getByRole('button',{name:'生成创作下一章草稿'}) as HTMLButtonElement).disabled).toBe(false);expect(generationFailureMessage(raw)).toBe('生成失败，请重试');
  });
  it('preserves explicit model selection without local, mock, or null fallback',()=>{
    const select=vi.fn();render(<AiWritingPanel {...base} selection={null} onSelectionChange={select}/>);const selector=screen.getByLabelText('文本模型');fireEvent.change(selector,{target:{value:'deepseek:deepseek-chat'}});expect(select).toHaveBeenCalledWith(selection);expect(screen.getAllByRole('option').map(option=>option.textContent)).toEqual(['尚未选择文本模型','DeepSeek Chat']);
  });
  it('previews, diffs, accepts and rejects generated results explicitly',()=>{
    const draft={id:'d1',original:'旧句',output:'新句',status:'ready' as const},accept=vi.fn(),reject=vi.fn();render(<AiDraftReview draft={draft} onAccept={accept} onReject={reject}/>);expect(screen.getByText('生成结果')).toBeTruthy();expect(screen.getByText('待确认修改')).toBeTruthy();fireEvent.click(screen.getByRole('tab',{name:'差异'}));expect(screen.getByLabelText('原文与草稿差异').textContent).toContain('-旧句');expect(screen.getByLabelText('原文与草稿差异').textContent).toContain('+新句');fireEvent.click(screen.getByRole('button',{name:'采用草稿'}));fireEvent.click(screen.getByRole('button',{name:'放弃草稿'}));expect(accept).toHaveBeenCalledWith(draft);expect(reject).toHaveBeenCalledWith(draft);
  });
  it('produces deterministic line-level changes',()=>expect(lineDiff('a\nb','a\nc')).toEqual([{kind:'same',text:'a'},{kind:'removed',text:'b'},{kind:'added',text:'c'}]));
  it('sends the exact session credential message and clears the password DOM immediately',async()=>{
    const postMessage=vi.fn();Object.defineProperty(window,'chrome',{value:{webview:{postMessage}},configurable:true});
    render(<AiWritingPanel {...base} onCredentialRefresh={async()=>true}/>);
    const input=screen.getByLabelText('DeepSeek API Key');fireEvent.change(input,{target:{value:'runtime-fake-sentinel'}});fireEvent.click(screen.getByRole('button',{name:'配置此会话'}));
    expect(postMessage).toHaveBeenCalledWith({protocol:'ai-novel-webview-credential/v1',type:'SET_PROVIDER_CREDENTIAL',provider:'deepseek',credential:'runtime-fake-sentinel'});
    await waitFor(()=>expect((input as HTMLInputElement).value).toBe(''));
  });
  it('shows configured state without a secret hint and clears through the fixed bridge',async()=>{
    const postMessage=vi.fn();Object.defineProperty(window,'chrome',{value:{webview:{postMessage}},configurable:true});
    render(<AiWritingPanel {...base} credentialConfigured onCredentialRefresh={async()=>false}/>);
    expect(screen.getByText('本次会话已配置')).toBeTruthy();expect(screen.queryByLabelText('DeepSeek API Key')).toBeNull();fireEvent.click(screen.getByRole('button',{name:'清除'}));
    expect(postMessage).toHaveBeenCalledWith({protocol:'ai-novel-webview-credential/v1',type:'CLEAR_PROVIDER_CREDENTIAL',provider:'deepseek'});
  });
  it('refreshes the authoritative session configuration state on demand',async()=>{
    const refresh=vi.fn(async()=>false);render(<AiWritingPanel {...base} onCredentialRefresh={refresh}/>);
    fireEvent.click(screen.getByRole('button',{name:'刷新状态'}));
    expect(screen.getByRole('button',{name:'正在刷新…'})).toBeTruthy();
    await waitFor(()=>expect(refresh).toHaveBeenCalledTimes(1));
    await waitFor(()=>expect(screen.getByRole('button',{name:'刷新状态'})).toBeTruthy());
  });
});
