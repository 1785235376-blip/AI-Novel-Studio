import {ArrowDown,CheckCircle2,Eye,Info} from 'lucide-react';
import type {VisualTextWorkflow as Workflow} from '../api';
import {Badge,EmptyState,Panel} from '../ui/primitives';
import './visualTextWorkflow.css';

type Props={workflow?:Workflow;loading?:boolean;error?:string|null;unauthorized?:boolean};
function safeText(value:string,fallback:string){return /api_key|authorization|bearer\s|credential|sk-/i.test(value)?fallback:value}

export function VisualTextWorkflow({workflow,loading=false,error,unauthorized=false}:Props){
  if(loading)return <Panel title="文本生成流程"><p className="visual-workflow-state" role="status" aria-live="polite">正在读取当前流程…</p></Panel>;
  if(unauthorized)return <Panel title="文本生成流程"><div className="visual-workflow-state visual-workflow-state--error" role="alert">无权查看此工作区的文本生成流程。</div></Panel>;
  if(error)return <Panel title="文本生成流程"><div className="visual-workflow-state visual-workflow-state--error" role="alert"><strong>暂时无法显示流程</strong><p>请确认已选择可用的文本模型，然后重试。</p></div></Panel>;
  if(!workflow)return <Panel title="文本生成流程"><EmptyState title="尚未选择文本模型" detail="请先在右侧 AI 写作助手中选择一个可用模型，再查看生成流程。"/></Panel>;
  return <Panel title={workflow.title} actions={<Badge tone="info"><Eye aria-hidden="true"/>只读检查</Badge>} className="visual-workflow">
    <p className="visual-workflow__description">{workflow.description}</p>
    <div className="visual-workflow__notice"><Info aria-hidden="true"/><span>此处只展示现有流程，不会运行模型、创建任务或修改正文。</span></div>
    <ol className="visual-workflow__steps" aria-label="文本生成流程步骤">
      {workflow.nodes.map((node,index)=><li key={node.stable_id}>
        <article className="visual-workflow__node" aria-label={`步骤 ${index+1}：${safeText(node.label,'文本模型')}`}>
          <span className="visual-workflow__number" aria-hidden="true">{index+1}</span>
          <div><h3>{safeText(node.label,'文本模型')}</h3><p>{safeText(node.summary,'流程信息已隐藏。')}</p>{node.kind==='text_model'&&<Badge tone={node.available?'success':'warning'}>{node.available?<><CheckCircle2 aria-hidden="true"/>当前可用</>:'当前不可用'}</Badge>}</div>
        </article>
        {index<workflow.nodes.length-1&&<div className="visual-workflow__edge" aria-label={safeText(workflow.edges[index]?.relationship||'进入下一步','进入下一步')}><ArrowDown aria-hidden="true"/><span>{safeText(workflow.edges[index]?.relationship||'进入下一步','进入下一步')}</span></div>}
      </li>)}
    </ol>
    <details className="visual-workflow__accessible"><summary>查看文字版流程说明</summary><ol>{workflow.nodes.map(node=><li key={node.stable_id}><strong>{safeText(node.label,'文本模型')}</strong>：{safeText(node.summary,'流程信息已隐藏。')}</li>)}</ol></details>
  </Panel>;
}
