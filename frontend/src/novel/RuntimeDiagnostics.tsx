import {Activity,CheckCircle2,Info,TriangleAlert} from 'lucide-react';
import type {TextRuntimeDiagnostics} from '../api';
import {Badge,EmptyState,Panel} from '../ui/primitives';
import './runtimeDiagnostics.css';

type Props={diagnostics?:TextRuntimeDiagnostics;loading?:boolean;error?:string|null;unauthorized?:boolean};
const capabilityLabels:Record<string,string>={generate:'文本生成',stream:'流式输出',structured_output:'结构化输出'};

export function RuntimeDiagnostics({diagnostics,loading=false,error,unauthorized=false}:Props){
  if(loading)return <Panel title="模型运行诊断"><p className="runtime-diagnostics-state" role="status" aria-live="polite">正在读取所选路线状态…</p></Panel>;
  if(unauthorized)return <Panel title="模型运行诊断"><div className="runtime-diagnostics-state runtime-diagnostics-state--error" role="alert">无权查看此工作区的模型运行诊断。</div></Panel>;
  if(error)return <Panel title="模型运行诊断"><div className="runtime-diagnostics-state runtime-diagnostics-state--error" role="alert"><strong>暂时无法读取诊断</strong><p>请确认所选模型仍然存在，然后重试。</p></div></Panel>;
  if(!diagnostics)return <Panel title="模型运行诊断"><EmptyState title="尚未选择文本模型" detail="请先在右侧 AI 写作助手中选择一个模型，再查看只读诊断。"/></Panel>;
  const ready=diagnostics.state==='READY';
  return <Panel title="模型运行诊断" actions={<Badge tone={ready?'success':'warning'}>{ready?<CheckCircle2 aria-hidden="true"/>:<TriangleAlert aria-hidden="true"/>}{diagnostics.state_label}</Badge>} className="runtime-diagnostics">
    <div className="runtime-diagnostics__notice"><Info aria-hidden="true"/><span>诊断只读取现有运行时元数据，不会连接模型服务、修改配置或发起生成。</span></div>
    <section className="runtime-diagnostics__summary" aria-labelledby="runtime-diagnostics-summary">
      <Activity aria-hidden="true"/>
      <div><h3 id="runtime-diagnostics-summary">{diagnostics.state_label}</h3><p>{diagnostics.explanation}</p></div>
    </section>
    <section aria-labelledby="runtime-diagnostics-action"><h3 id="runtime-diagnostics-action">建议操作</h3><p>{diagnostics.author_action}</p></section>
    <dl className="runtime-diagnostics__identity">
      <div><dt>模型服务标识</dt><dd>{diagnostics.provider_id}</dd></div>
      <div><dt>模型标识</dt><dd>{diagnostics.model_id}</dd></div>
    </dl>
    <section aria-labelledby="runtime-diagnostics-capabilities"><h3 id="runtime-diagnostics-capabilities">安全能力摘要</h3>{diagnostics.safe_capabilities.length?<ul>{diagnostics.safe_capabilities.map(item=><li key={item}>{capabilityLabels[item]||'已支持能力'}</li>)}</ul>:<p>当前没有可展示的安全能力信息。</p>}</section>
  </Panel>;
}
