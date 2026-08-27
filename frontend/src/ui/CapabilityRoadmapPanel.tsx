import {AudioLines,BookOpenCheck,GitBranch,Image,PlugZap,Search,ShieldCheck,Sparkles} from 'lucide-react';
import {Badge,Panel} from './primitives';
import './capability-roadmap.css';

type RoadmapItem={title:string;service:string;api:string;description:string;state:'部分接入'|'后端预留';icon:typeof Sparkles};

const items:RoadmapItem[]=[
  {title:'知识库候选审核',service:'Knowledge Base Review',api:'/api/v1/novels/{id}/import/knowledge-base/review',description:'导入预览、持久化待审队列、逐项选择与编辑、接受/拒绝/跳过已接入；更丰富的批量历史筛选仍待增强。',state:'部分接入',icon:BookOpenCheck},
  {title:'研究资料',service:'Research Assistant',api:'/api/v1/novels/{id}/research',description:'本地 sidecar 资料卡：新建、筛选、编辑、版本冲突和删除确认已接入。不读取外部网络。',state:'部分接入',icon:Search},
  {title:'角色成长轨迹',service:'Character Evolution Service',api:'/api/v1/novels/{id}/character-evolution',description:'角色阶段、关系变化和证据回溯的专用窗口。',state:'后端预留',icon:GitBranch},
  {title:'音视频与多模态',service:'Voice / Video / Vision Runtime',api:'/api/v1/media/*',description:'配音、视频、视觉理解和向量能力的统一任务入口。',state:'后端预留',icon:AudioLines},
  {title:'资产派生与记忆',service:'Visual Memory & Asset Derivation',api:'/api/v1/assets/{id}/derivatives',description:'缩略图、实体关联、派生资源和视觉记忆将在这里管理。',state:'后端预留',icon:Image},
  {title:'Provider 与插件',service:'Provider / Plugin / Permission Manager',api:'/api/v1/providers · /api/v1/plugins',description:'项目级 Provider、插件能力和权限策略；密钥仍只允许桌面运行时输入。',state:'后端预留',icon:PlugZap},
  {title:'工作流编排',service:'Workflow Orchestrator',api:'/api/v1/workflows',description:'可恢复 DAG、任务依赖和人工审批节点的统一入口。',state:'后端预留',icon:Sparkles},
  {title:'安全与发布检查',service:'Release Gate & Audit',api:'/api/v1/release-gates · /api/v1/audit',description:'备份、恢复、完整性和发布前检查结果将集中呈现。',state:'后端预留',icon:ShieldCheck},
];

export function CapabilityRoadmapPanel(){
  return <Panel title="能力路线图" actions={<Badge tone="warning">后端待接入</Badge>} className="capability-roadmap">
    <p className="novel-help">这里列出当前版本尚未完成或仅完成基础接口的能力。每张卡片标注服务归属和 API 前缀，后端补齐后可在原位接入，不会伪造结果。</p>
    <div className="capability-roadmap__grid">{items.map(({title,service,api,description,state,icon:Icon})=><article className="capability-roadmap__card" key={title}>
      <div className="capability-roadmap__card-head"><span className="capability-roadmap__icon"><Icon aria-hidden="true"/></span><div><h3>{title}</h3><Badge tone={state==='部分接入'?'info':'neutral'}>{state}</Badge></div></div>
      <p>{description}</p><dl><div><dt>服务</dt><dd>{service}</dd></div><div><dt>API</dt><dd><code>{api}</code></dd></div></dl>
    </article>)}</div>
  </Panel>;
}
