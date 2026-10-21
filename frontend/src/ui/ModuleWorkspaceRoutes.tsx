import {useEffect, useState, type ReactNode} from 'react';
import type {Asset} from '../api';
import {AppShell, type ScopeLabels, type StudioModule, type ProjectNoun} from './AppShell';
import {ScreenplayPanel} from '../novel/ScreenplayPanel';
import {PluginManagerPanel} from '../novel/PluginManagerPanel';
import {WorkflowPanel} from '../novel/WorkflowPanel';
import {AgentQueuePanel} from '../novel/AgentQueuePanel';
import {AssetInspector} from '../novel/AssetInspector';
import {WorkflowInspector, type WorkflowInspection} from '../novel/WorkflowInspector';
import {ImageTaskInspector, type ImageInspection} from '../novel/ImageTaskInspector';
import {VideoTaskInspector, type VideoInspection} from '../novel/VideoTaskInspector';
import {AudioTaskInspector, type AudioInspection} from '../novel/AudioTaskInspector';
import {PluginInspector, type PluginInspection} from '../novel/PluginInspector';
import {CapabilityStatusCenter} from './CapabilityStatusCenter';
import {AiControlCenter} from './AiControlCenter';
import {MediaProviderSettings} from './MediaProviderSettings';
import {ModelCenter} from './ModelCenter';
import type {LocalAiOnboardingOwner} from './LocalAiDiscovery';
import {MultimodalDirectorWorkspace} from '../novel/MultimodalDirectorWorkspace';
import {EmptyState} from './primitives';
import {EditNleShell, EditNleMediaRail, EditNleInspector, demoEditTimeline} from './EditNleShell';
import {
  ImageWorkspaceShell, ImageWorkspaceRail, ImageEmptyCta,
  AudioWorkspaceShell, AudioWorkspaceRail, AudioEmptyCta,
  AssetsWorkspaceShell, AssetsWorkspaceRail, AssetsEmptyCta,
} from './MediaWorkspaceShells';

type WorkspaceModule=Exclude<StudioModule,'NOVEL'>;
interface Props {localAiOnboarding?:LocalAiOnboardingOwner; module: WorkspaceModule; onModuleChange:(value:StudioModule)=>void; scope:ScopeLabels; actor:string; novelId?:string; projectNoun?:ProjectNoun; interopEntry?:ReactNode; interopSettings?:ReactNode; controlTab?:'models'; onControlSurfaceChange?:(surface:string)=>void;}
const moduleLabels: Record<WorkspaceModule, string> = { IMAGE: '图片', VIDEO: '视频', AUDIO: '声音', EDIT: '剪辑', CONTROL: '主控', PLUGIN: '插件', WORKFLOW: '工作流', ASSETS: '资产' };
function WorkspaceRail({ module }: { module: WorkspaceModule }) {
  return <nav className="workspace-rail" aria-label={`${moduleLabels[module]}工作区导航`}><div className="workspace-rail__eyebrow">当前工作区</div><strong>{moduleLabels[module]}</strong><button className="is-active" aria-current="page">工作区概览</button><button disabled title="最近编辑尚未开放">最近编辑</button><button disabled title="待处理任务尚未开放">待处理任务</button><div className="workspace-rail__future"><span>预留入口</span><small>AI Copilot</small><small>Provider 状态</small><small>审批队列</small></div></nav>;
}
function WorkspaceInspector({ module, novelId }: { module: WorkspaceModule; novelId?: string }) {
  const context: Record<WorkspaceModule, { focus: string; slot: string }> = {
    IMAGE: { focus: '参考图、构图与一致性约束', slot: '预留：图片任务 / 资产预览' },
    VIDEO: { focus: '当前镜头、转场与时间线轨道', slot: '预留：Motion Task / 视频预览' },
    AUDIO: { focus: '声音档案、对白与配音批次', slot: '预留：音频波形 / Provider 任务' },
    EDIT: { focus: '多轨时间线、片段剪辑与交付', slot: 'NLE TimelineWorkspace / StudioTimelineEditor' },
    CONTROL: { focus: '模型、Provider、凭据与路由策略', slot: '预留：主控对话 / 模型诊断' },
    PLUGIN: { focus: '插件能力与运行权限', slot: '预留：插件详情 / 权限审批' },
    WORKFLOW: { focus: 'Job 队列与执行状态', slot: '预留：运行时间线 / 重试操作' },
    ASSETS: { focus: '资产元数据与引用关系', slot: '预留：媒体预览 / 使用位置' },
  };
  return <section className="workspace-inspector__empty" aria-label="工作区检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><strong>{moduleLabels[module]}上下文</strong><p>当前关注：{context[module].focus}</p><dl className="workspace-inspector__facts"><div><dt>小说项目</dt><dd>{novelId || '未选择'}</dd></div><div><dt>工作区</dt><dd>{moduleLabels[module]}</dd></div><div><dt>运行状态</dt><dd><span className="ui-badge ui-badge--info">等待真实任务</span></dd></div></dl><div className="workspace-inspector__slot">{context[module].slot}</div></section>;
}
function ControlWorkspace({interopSettings,requestedTab,onSurfaceChange,localAiOnboarding}:{localAiOnboarding?:LocalAiOnboardingOwner;interopSettings?:ReactNode;requestedTab?:'models';onSurfaceChange?:(surface:string)=>void}){
  const [tab,setTab]=useState<'assistant'|'models'|'providers'>('assistant');
  useEffect(()=>{if(requestedTab)setTab(requestedTab)},[requestedTab]);
  useEffect(()=>{onSurfaceChange?.(tab==='models'?'model-center':'settings')},[tab,onSurfaceChange]);
  return <div className="control-workspace"><div className="control-workspace__tabs" role="tablist" aria-label="主控设置"><button type="button" role="tab" aria-selected={tab==='assistant'} onClick={()=>setTab('assistant')}>AI 主控</button><button type="button" role="tab" aria-selected={tab==='models'} onClick={()=>setTab('models')}>模型中心</button><button type="button" role="tab" aria-selected={tab==='providers'} onClick={()=>setTab('providers')}>媒体 Provider</button></div>{tab==='assistant'?<>{interopSettings}<AiControlCenter/></>:tab==='models'?<ModelCenter onboarding={localAiOnboarding}/>:<MediaProviderSettings/>}</div>;
}

export function ModuleWorkspaceRoutes({localAiOnboarding,module,onModuleChange,scope,actor,novelId,projectNoun,interopEntry,interopSettings,controlTab,onControlSurfaceChange}:Props){
  const [selectedAsset,setSelectedAsset]=useState<Asset>();
  // [HERMIA-FE-20261022 W-P0-06] EDIT session: playhead/selection shared with inspector (CapCut-density shell).
  const editTimeline = novelId && module==='EDIT' ? demoEditTimeline(novelId) : null;
  const [editPlayheadMs,setEditPlayheadMs]=useState(0);
  const [editSelectedClipIds,setEditSelectedClipIds]=useState<string[]>(['c-v1']);

  const [workflowInspection,setWorkflowInspection]=useState<WorkflowInspection>();
  const [imageInspection,setImageInspection]=useState<ImageInspection>();
  const [videoInspection,setVideoInspection]=useState<VideoInspection>();
  const [audioInspection,setAudioInspection]=useState<AudioInspection>();
  const [pluginInspection,setPluginInspection]=useState<PluginInspection>();
  let main:ReactNode; let status='工作区';
  switch(module){
    case 'IMAGE': main=novelId?<ImageWorkspaceShell novelId={novelId} inspection={imageInspection} onInspect={i=>{if(i)setImageInspection(i);}}/>:<EmptyState title="请先打开小说项目" detail="图片预览、参考与生成任务需要绑定到一个小说项目。"/>; status='图片工作区'; break;
    case 'VIDEO': main=novelId?<><MultimodalDirectorWorkspace mode="video" novelId={novelId}/><ScreenplayPanel novelId={novelId} onInspect={setVideoInspection}/></>:<EmptyState title="请先打开小说项目" detail="视频导演台、剧本与镜头任务需要绑定到一个小说项目。"/>; status='视频工作区'; break;
    case 'AUDIO': main=novelId?<AudioWorkspaceShell novelId={novelId} onInspect={setAudioInspection} onSendToEdit={()=>onModuleChange('EDIT')}/>:<EmptyState title="请先打开小说项目" detail="配音、音效与有声书需要绑定到一个小说项目。"/>; status='声音工作区'; break;
    case 'EDIT': main=novelId&&editTimeline?<EditNleShell novelId={novelId} timeline={editTimeline} playheadMs={editPlayheadMs} onPlayhead={setEditPlayheadMs} selectedClipIds={editSelectedClipIds} onSelectClips={setEditSelectedClipIds}/>:<EmptyState title="请先打开小说项目" detail="剪辑时间线需要绑定到一个小说/项目。NLE 不嵌入小说中区（多工作区并列）。"/>; status='剪辑工作区'; break;
    case 'CONTROL': main=<ControlWorkspace localAiOnboarding={localAiOnboarding} interopSettings={interopSettings} requestedTab={controlTab} onSurfaceChange={onControlSurfaceChange}/>; status='AI 主控'; break;
    case 'PLUGIN': main=<PluginManagerPanel onInspect={setPluginInspection}/>; status='插件管理'; break;
    case 'WORKFLOW': main=novelId?<><WorkflowPanel novelId={novelId} onInspect={setWorkflowInspection}/><AgentQueuePanel novelId={novelId} onInspect={setWorkflowInspection}/></>:<EmptyState title="请先打开小说项目" detail="工作流定义、运行记录与 Agent 队列需要绑定到一个小说项目。"/>; status='工作流'; break;
    case 'ASSETS': main=novelId?<AssetsWorkspaceShell novelId={novelId} selectedAssetId={selectedAsset?.id} onSelectAsset={setSelectedAsset}/>:<EmptyState title="请先打开小说项目" detail="资产库中的文件和引用关系按小说项目隔离。"/>; status='资产库'; break;
  }
  const inspector=module==='EDIT'&&novelId&&editTimeline?<EditNleInspector novelId={novelId} timeline={editTimeline} selectedClipIds={editSelectedClipIds} playheadMs={editPlayheadMs} editable={false}/>:module==='ASSETS'?<>{selectedAsset?<AssetInspector asset={selectedAsset} novelId={novelId}/>:<AssetsEmptyCta/>}</>:module==='WORKFLOW'?<WorkflowInspector inspection={workflowInspection} novelId={novelId}/>:module==='IMAGE'?<>{imageInspection?<ImageTaskInspector inspection={imageInspection} novelId={novelId}/>:<ImageEmptyCta/>}</>:module==='VIDEO'?<VideoTaskInspector inspection={videoInspection} novelId={novelId}/>:module==='AUDIO'?<>{audioInspection?<AudioTaskInspector inspection={audioInspection} novelId={novelId}/>:<AudioEmptyCta onSendToEdit={()=>onModuleChange('EDIT')}/>}</>:module==='PLUGIN'?<PluginInspector inspection={pluginInspection}/>:<WorkspaceInspector module={module} novelId={novelId}/>;
  const sidebar=module==='EDIT'&&novelId?<EditNleMediaRail novelId={novelId}/>:module==='IMAGE'&&novelId?<ImageWorkspaceRail/>:module==='AUDIO'&&novelId?<AudioWorkspaceRail onSendToEdit={()=>onModuleChange('EDIT')}/>:module==='ASSETS'&&novelId?<AssetsWorkspaceRail/>:<WorkspaceRail module={module}/>;
  // EDIT: skip bulky CapabilityStatusCenter above hero timeline (status stays in bar); other modules unchanged.
  const mainBody=(module==='EDIT'||module==='IMAGE'||module==='AUDIO'||module==='ASSETS')?<div className="media-ws-main" data-module-shell={module}>{main}</div>:<><CapabilityStatusCenter module={module} novelId={novelId}/>{main}</>;
  return <AppShell module={module} onModuleChange={onModuleChange} scope={scope} projectNoun={projectNoun} actor={actor} sidebar={sidebar} main={mainBody} inspector={inspector} status={<>{status}{interopEntry}</>}/>;
}
