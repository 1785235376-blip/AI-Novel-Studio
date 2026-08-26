// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it} from 'vitest';
import {RuntimeDiagnostics} from './RuntimeDiagnostics';

const diagnostics={diagnostics_contract_version:'text-runtime-diagnostics/v1',read_only:true as const,provider_id:'deepseek',model_id:'deepseek-chat',state:'READY' as const,state_label:'可用',explanation:'所选文本路线已具备现有流式生成能力。',author_action:'可以返回写作面板开始生成。',safe_capabilities:['generate','stream']};

describe('RuntimeDiagnostics',()=>{
  afterEach(cleanup);
  it('renders Chinese-first selected-route diagnostics without mutation controls',()=>{
    render(<RuntimeDiagnostics diagnostics={diagnostics}/>);
    expect(screen.getByRole('heading',{name:'模型运行诊断'})).toBeTruthy();
    expect(screen.getAllByText('可用').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('deepseek')).toBeTruthy();
    expect(screen.getByText('deepseek-chat')).toBeTruthy();
    expect(screen.getByText('流式输出')).toBeTruthy();
    expect(screen.queryByRole('button',{name:/配置|修复|运行|切换|保存/})).toBeNull();
  });
  it('renders the existing missing-credential state for an explicit DeepSeek route',()=>{
    render(<RuntimeDiagnostics diagnostics={{...diagnostics,state:'NOT_CONFIGURED',state_label:'未配置',explanation:'所选模型服务尚未由运行环境配置。',author_action:'请联系运行环境管理员完成模型服务配置。'}}/>);
    expect(screen.getAllByText('未配置').length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText('deepseek-chat')).toBeTruthy();
  });
  it('provides loading, empty, error and unauthorized states',()=>{
    const {rerender}=render(<RuntimeDiagnostics loading/>);expect(screen.getByRole('status').textContent).toContain('正在读取');
    rerender(<RuntimeDiagnostics/>);expect(screen.getByText('尚未选择文本模型')).toBeTruthy();
    rerender(<RuntimeDiagnostics error="failure"/>);expect(screen.getByRole('alert').textContent).toContain('暂时无法读取诊断');
    rerender(<RuntimeDiagnostics unauthorized/>);expect(screen.getByRole('alert').textContent).toContain('无权查看');
  });
});
