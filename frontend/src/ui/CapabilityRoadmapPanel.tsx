import {AudioLines,BookOpenCheck,GitBranch,Image,PlugZap,Search,ShieldCheck,Sparkles} from 'lucide-react';
import {Badge,Panel} from './primitives';
import './capability-roadmap.css';

type RoadmapItem={title:string;service:string;api:string;description:string;state:'部分接入'|'后端预留';icon:typeof Sparkles};

const items:RoadmapItem[]=[
  {title:'知识库候选审核',service:'Knowledge Base Review',api:'/api/v1/novels/{id}/import/knowledge-base/review',description:'导入预览、持久化待审队列、逐项选择与编辑、接受/拒绝/跳过已接入；更丰富的批量历史筛选仍待增强。',state:'部分接入',icon:BookOpenCheck},
  {title:'研究资料',service:'Research Assistant',api:'/api/v1/novels/{id}/research',description:'本地 sidecar 资料卡：新建、筛选、编辑、版本冲突和删除确认已接入。不读取外部网络。',state:'部分接入',icon:Search},
  {title:'角色成长轨迹',service:'Character Evolution Service',api:'/api/v1/novels/{id}/character-evolution',description:'可手动记录角色阶段、事件和心理变化到 durable sidecar。不会从正文自动抽取成长，也没有独立证据图谱。',state:'部分接入',icon:GitBranch},
  {title:'音视频与多模态',service:'Voice / Video / Vision Runtime',api:'/api/v1/media/*',description:'窗口已挂接配音/视频任务入口。未配置 Provider 时 fail-closed：任务保持 PENDING 并返回 VIDEO_PROVIDER_NOT_CONFIGURED，不会出现 placeholder:// 成功。镜头生成与真实视频 Provider 未实现。',state:'部分接入',icon:AudioLines},
  {title:'资产派生与记忆',service:'Visual Memory & Asset Derivation',api:'/api/v1/assets/{id}/derivatives',description:'资产库基础上传/列表/缩略图已接入；派生资源、实体关联和视觉记忆仍未实现。',state:'后端预留',icon:Image},
  {title:'Provider 与插件',service:'Provider / Plugin / Permission Manager',api:'/api/v1/providers · /api/v1/plugins',description:'插件可发现、注册、审核权限并激活清单；execution_supported=false，激活清单不等于执行插件代码。密钥只允许桌面运行时输入。',state:'部分接入',icon:PlugZap},
  {title:'工作流编排',service:'Workflow Orchestrator',api:'/api/v1/workflows',description:'工作流定义与 run 记录已接入。agent_task 节点只进入等待人工触发，运行时不执行模型任务。',state:'部分接入',icon:Sparkles},
  {title:'安全与发布检查',service:'Release Gate & Audit',api:'/api/v1/release-gates · /api/v1/audit',description:'发布门禁和审计 API 已存在，没有独立发布窗口。DesktopHost DH-01–DH-08 窗口门禁仍待 Windows 操作员，不能用 API 替代。',state:'部分接入',icon:ShieldCheck},
];

export function CapabilityRoadmapPanel(){
  return <Panel title="能力路线图" actions={<Badge tone="warning">诚实状态</Badge>} className="capability-roadmap">
    <p className="novel-help">卡片写的是当前真实接入程度，不是路线图愿望。部分接入不等于 V1.0 完成，也不会把未实现的引擎写成已上线。</p>
    <div className="capability-roadmap__grid">{items.map(({title,service,api,description,state,icon:Icon})=><article className="capability-roadmap__card" key={title}>
      <div className="capability-roadmap__card-head"><span className="capability-roadmap__icon"><Icon aria-hidden="true"/></span><div><h3>{title}</h3><Badge tone={state==='部分接入'?'info':'neutral'}>{state}</Badge></div></div>
      <p>{description}</p><dl><div><dt>服务</dt><dd>{service}</dd></div><div><dt>API</dt><dd><code>{api}</code></dd></div></dl>
    </article>)}</div>
  </Panel>;
}
