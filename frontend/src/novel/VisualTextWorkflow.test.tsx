// @vitest-environment jsdom
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,describe,expect,it} from 'vitest';
import {VisualTextWorkflow} from './VisualTextWorkflow';

const workflow={workflow_contract_version:'visual-text-workflow/v2',title:'文本生成流程',description:'只读展示当前文本模型如何接收上下文并产生待确认草稿。',read_only:true as const,nodes:[
  {stable_id:'context:privacy-filtered',kind:'context',label:'隐私筛选上下文',summary:'经过隐私筛选的信息。',production_boundary:'context.privacy_filter',capabilities:[]},
  {stable_id:'text-model:deepseek:deepseek-chat',kind:'text_model',label:'DeepSeek Chat',summary:'通过现有文本模型运行时生成草稿。',production_boundary:'runtime.text_model_node',capabilities:['generate','stream'],provider_id:'deepseek',model_id:'deepseek-chat',available:true},
  {stable_id:'stream:generation-events',kind:'stream',label:'流式生成',summary:'沿用现有流式事件。',production_boundary:'runtime.generation_events',capabilities:[]},
  {stable_id:'draft:diff-preview',kind:'draft',label:'草稿与差异预览',summary:'采用前不会修改正文。',production_boundary:'generation.draft_diff',capabilities:[]},
  {stable_id:'accept:explicit',kind:'accept',label:'显式采用',summary:'作者主动采用。',production_boundary:'generation.explicit_accept',capabilities:[]},
  {stable_id:'revision:immutable',kind:'revision',label:'创建新修订',summary:'保留既有历史。',production_boundary:'revision.immutable_append',capabilities:[]},
],edges:[
  {source:'context:privacy-filtered',target:'text-model:deepseek:deepseek-chat',relationship:'提供经过筛选的创作信息'},
  {source:'text-model:deepseek:deepseek-chat',target:'stream:generation-events',relationship:'沿用现有流式事件'},
  {source:'stream:generation-events',target:'draft:diff-preview',relationship:'形成待确认草稿'},
  {source:'draft:diff-preview',target:'accept:explicit',relationship:'等待作者明确决定'},
  {source:'accept:explicit',target:'revision:immutable',relationship:'通过版本检查后写入'},
]};

describe('VisualTextWorkflow',()=>{
  afterEach(cleanup);
  it('renders a Chinese-first accessible read-only representation without internal JSON',()=>{
    const {container}=render(<VisualTextWorkflow workflow={workflow}/>);
    expect(screen.getByRole('heading',{name:'文本生成流程'})).toBeTruthy();
    expect(screen.getByRole('list',{name:'文本生成流程步骤'})).toBeTruthy();
    expect(screen.getByLabelText('步骤 1：隐私筛选上下文')).toBeTruthy();
    expect(screen.getByLabelText('步骤 2：DeepSeek Chat')).toBeTruthy();
    expect(screen.getByLabelText('步骤 6：创建新修订')).toBeTruthy();
    expect(screen.getByText('只读检查')).toBeTruthy();
    expect(container.textContent).not.toMatch(/ProviderRegistry|ActorContext|LOCAL_ONLY|\{"/);
    expect(screen.queryByRole('button',{name:/运行|保存|添加节点/})).toBeNull();
  });
  it('provides loading, empty, error and unauthorized states',()=>{
    const {rerender}=render(<VisualTextWorkflow loading/>);expect(screen.getByRole('status').textContent).toContain('正在读取');
    rerender(<VisualTextWorkflow/>);expect(screen.getByText('尚未选择文本模型')).toBeTruthy();
    rerender(<VisualTextWorkflow error="failure"/>);expect(screen.getByRole('alert').textContent).toContain('暂时无法显示流程');
    rerender(<VisualTextWorkflow unauthorized/>);expect(screen.getByRole('alert').textContent).toContain('无权查看');
  });
  it('defensively redacts sensitive sentinel metadata from rendered content',()=>{
    const sentinel='sk-SENTINEL_NEVER_RENDER';
    const unsafe={...workflow,nodes:workflow.nodes.map((node,index)=>index===1?{...node,label:`Authorization Bearer ${sentinel}`,summary:`credential ${sentinel}`} : node)};
    const {container}=render(<VisualTextWorkflow workflow={unsafe}/>);
    expect(container.textContent).not.toContain(sentinel);expect(screen.getAllByText('文本模型').length).toBeGreaterThan(0);
  });
});
