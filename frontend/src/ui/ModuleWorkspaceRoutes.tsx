import {useEffect, useState, type ReactNode} from 'react';
import { CredentialsPanel } from '../rebuild/CredentialsPanel'; // [HERMIA-FE-20261022 REBUILD-2]
import { LocalInteropPanel } from '../rebuild/LocalInteropPanel'; // [HERMIA-FE-20261022 REBUILD-5]
import type {Asset} from '../api';
import {AppShell, type ScopeLabels, type StudioModule, type ProjectNoun} from './AppShell';
import {PluginManagerPanel} from '../novel/PluginManagerPanel';
import {WorkflowPanel} from '../novel/WorkflowPanel';
import {AgentQueuePanel} from '../novel/AgentQueuePanel';
import {AssetInspector} from '../novel/AssetInspector';
import {WorkflowInspector, type WorkflowInspection} from '../novel/WorkflowInspector';
import {ImageRebuild, type ImageView} from '../rebuild/image/ImageRebuild'; // [HERMIA-FE-20261022 R2]
import {VideoRebuild} from '../rebuild/video/VideoRebuild'; // [HERMIA-FE-20261022 R3]
import {AudioRebuild} from '../rebuild/audio/AudioRebuild'; // [HERMIA-FE-20261022 R4]
import {EditRebuild} from '../rebuild/edit/EditRebuild'; // [HERMIA-FE-20261022 R5]
import {AssetsRebuild} from '../rebuild/assets/AssetsRebuild'; // [HERMIA-FE-20261022 R6]
import {ControlRebuild} from '../rebuild/hub/ControlRebuild'; // [HERMIA-FE-20261022 R7]
import {PluginsRebuild} from '../rebuild/hub/PluginsRebuild'; // [HERMIA-FE-20261022 R7]
import {ImageTaskInspector, type ImageInspection} from '../novel/ImageTaskInspector';
import {VideoTaskInspector, type VideoInspection} from '../novel/VideoTaskInspector';
import {AudioTaskInspector, type AudioInspection} from '../novel/AudioTaskInspector';
import {PluginInspector, type PluginInspection} from '../novel/PluginInspector';
import {CapabilityStatusCenter} from './CapabilityStatusCenter';
import {AiControlCenter} from './AiControlCenter';
import {MediaProviderSettings} from './MediaProviderSettings';
import {ModelCenter} from './ModelCenter';
import type {LocalAiOnboardingOwner} from './LocalAiDiscovery';
import {EmptyState} from './primitives';
import {WorkspaceHonestEmpty} from './WorkspaceHonestEmpty';
import {pushEditHandoff, type EditHandoffSource} from './editHandoff';
import {
  
  AudioWorkspaceShell, AudioWorkspaceRail, AudioEmptyCta,
  AssetsWorkspaceShell, AssetsWorkspaceRail, AssetsEmptyCta,
  VideoWorkspaceShell, VideoWorkspaceRail, VideoEmptyCta,
} from './MediaWorkspaceShells';
import { mediaShellForModule } from './moduleSwitchIsolation';

type WorkspaceModule=Exclude<StudioModule,'NOVEL'>;
interface Props {localAiOnboarding?:LocalAiOnboardingOwner; module: WorkspaceModule; onModuleChange:(value:StudioModule)=>void; scope:ScopeLabels; actor:string; novelId?:string; projectNoun?:ProjectNoun; interopEntry?:ReactNode; interopSettings?:ReactNode; controlTab?:'models'; onControlSurfaceChange?:(surface:string)=>void; shellMode?:'basic'|'pro'; onShellModeChange?:(mode:'basic'|'pro')=>void;}
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


/** [HERMIA-FE-20261022 X-UX-03/09] Honest overflow surface — Header 设置 /「更多」/ 命令可达；ban fake green. */
function OverflowSurfaceBanner({module}:{module:'CONTROL'|'PLUGIN'|'WORKFLOW'}){
  const copy={
    CONTROL:{title:'主控 · 溢出工作区',detail:'经 Header「设置」/ 命令面板 /「更多」进入，不进默认 6 钮。模型与 Provider 状态读真实账本。'},
    PLUGIN:{title:'插件 · 溢出工作区',detail:'经 Header「设置」/ 命令 /「更多」进入。execution_supported=false 时不得显示已连通绿标。'},
    WORKFLOW:{title:'工作流 · 溢出工作区',detail:'经 Header「设置」/ 命令 /「更多」进入。编排面 ≠ 小说 AI 写作旁路。'},
  }[module];
  return <aside className="overflow-surface-banner" data-overflow-surface={module} data-capability-tone="neutral" data-x-ux-09="surface" aria-label={copy.title}>
    <strong>{copy.title}</strong>
    <p>{copy.detail}</p>
    <small>[HERMIA-FE-20261022 X-UX-09] 设置+更多双路径 · 铬条隐藏 ≠ 禁用 · 禁假绿</small>
  </aside>;
}

export function ModuleWorkspaceRoutes({localAiOnboarding,module,onModuleChange,scope,actor,novelId,projectNoun,interopEntry,interopSettings,controlTab,onControlSurfaceChange,shellMode='basic',onShellModeChange}:Props){
  // [HERMIA-FE-20261022 X-UX-08] This route tree mounts ONLY when App studioModule !== NOVEL.
  // Per-module main/inspector/sidebar switch below — selection buckets do not cross into novel center.
  const [selectedAsset,setSelectedAsset]=useState<Asset>();
  // [HERMIA-FE-20261022 W-P0-06] EDIT session: playhead/selection shared with inspector (CapCut-density shell).
  // [HERMIA-FE-20261022 R5] 剪辑不再挂演示时间线数据；EditRebuild 自管本地编排状态。

  const [workflowInspection,setWorkflowInspection]=useState<WorkflowInspection>();
  const [imageInspection,setImageInspection]=useState<ImageInspection>();
  const [videoInspection,setVideoInspection]=useState<VideoInspection>();
  const [audioInspection,setAudioInspection]=useState<AudioInspection>();
  const [pluginInspection,setPluginInspection]=useState<PluginInspection>();
  // [HERMIA-FE-20261022 W-UX-10] IMAGE studio|comic subview shared by rail + shell + empty CTA.
  // [HERMIA-FE-20261022 W-UX-13] IMAGE onSendToVideo → onModuleChange('VIDEO') after explicit confirm.
  const [imageSubview,setImageSubview]=useState<'studio'|'comic'>('studio');
  useEffect(()=>{ if(module!=='IMAGE') setImageSubview('studio'); },[module]);
  // [HERMIA-FE-20261022 R2] 图片页按原型重做：视图 浏览/图片画布/生成/漫画制作；旧 ImageWorkspaceShell/Rail/EmptyCta 不再挂载（代码保留）。
  const [imageView,setImageView]=useState<ImageView>('browse');
  useEffect(()=>{ if(module!=='IMAGE') setImageView('browse'); },[module]);
  // [HERMIA-FE-20261022 W-UX-14] Explicit send→EDIT records a media-pool handoff source strip.
  // [HERMIA-FE-20261022 X-UX-10] Hand-off smoke covers IMAGE→VIDEO · AUDIO→EDIT · ASSETS→* (see handoffSmoke.xUx10.test.tsx).
  const sendToEdit = (source: EditHandoffSource, label: string) => {
    pushEditHandoff({source, label, novelId});
    onModuleChange('EDIT');
  };
  const sendAssetsToModule = (m: Parameters<typeof onModuleChange>[0]) => {
    if (m === 'EDIT') {
      const assetLabel = selectedAsset?.filename || selectedAsset?.id || '资产条目';
      pushEditHandoff({source: 'ASSETS', label: String(assetLabel), novelId});
    }
    onModuleChange(m);
  };
  let main:ReactNode; let status='工作区';
  switch(module){
    case 'IMAGE': main=novelId?<ImageRebuild novelId={novelId} view={imageView} onViewChange={setImageView} shellMode={shellMode} onInspect={i=>{if(i)setImageInspection(i);}} onSendToVideo={()=>onModuleChange('VIDEO')} onOpenAssets={()=>onModuleChange('ASSETS')} onOpenControl={()=>onModuleChange('CONTROL')}/>:<WorkspaceHonestEmpty kind="no_project" workspace="IMAGE"/>; status='图片工作区'; break;
    case 'VIDEO': main=novelId?<VideoRebuild novelId={novelId} shellMode={shellMode} onSendToEdit={()=>sendToEdit('VIDEO','视频镜头 / 交片')} onOpenControl={()=>onModuleChange('CONTROL')}/>/* [HERMIA-FE-20261022 R3] 旧 VideoWorkspaceShell 退役 */:<WorkspaceHonestEmpty kind="no_project" workspace="VIDEO"/>; status='视频工作区'; break;
    case 'AUDIO': main=novelId?<AudioRebuild novelId={novelId} shellMode={shellMode} onSendToEdit={()=>sendToEdit('AUDIO','声音检听 / 交片')} onOpenAssets={()=>onModuleChange('ASSETS')} onOpenControl={()=>onModuleChange('CONTROL')}/>/* [HERMIA-FE-20261022 R4] 旧 AudioWorkspaceShell 退役 */:<WorkspaceHonestEmpty kind="no_project" workspace="AUDIO"/>; status='声音工作区'; break;
    case 'EDIT': main=novelId?<EditRebuild novelId={novelId} shellMode={shellMode} editable={false} onBackToVideo={()=>onModuleChange('VIDEO')}/>/* [HERMIA-FE-20261022 R5] 旧 EditNleShell 退役（代码保留）；默认仍是只读本地编排，不切 PRODUCTION */:<WorkspaceHonestEmpty kind="no_project" workspace="EDIT"/>; status='剪辑工作区'; break;
    case 'CONTROL': main=<ControlRebuild onOpenWorkflow={()=>onModuleChange('WORKFLOW')} advanced={<ControlWorkspace localAiOnboarding={localAiOnboarding} interopSettings={interopSettings} requestedTab={controlTab} onSurfaceChange={onControlSurfaceChange}/>}/>/* [HERMIA-FE-20261022 R7] 主控单页；旧三页签收进「高级」折叠 */; status='AI 主控'; break;
    case 'PLUGIN': main=<PluginsRebuild/>/* [HERMIA-FE-20261022 R7] 插件单页：本地软件 + 插件列表；旧治理面板进「安装插件…」抽屉 */; status='插件管理'; break;
    case 'WORKFLOW': main=novelId?<><WorkflowPanel novelId={novelId} onInspect={setWorkflowInspection}/><AgentQueuePanel novelId={novelId} onInspect={setWorkflowInspection}/></>:<EmptyState title="请先打开小说项目" detail="工作流定义、运行记录与 Agent 队列需要绑定到一个小说项目。"/>; status='工作流'; break;
    case 'ASSETS': main=novelId?<AssetsRebuild novelId={novelId} shellMode={shellMode} onSelectAsset={setSelectedAsset} onSendToModule={sendAssetsToModule}/>/* [HERMIA-FE-20261022 R6] 旧 AssetsWorkspaceShell 退役（代码保留） */:<WorkspaceHonestEmpty kind="no_project" workspace="ASSETS"/>; status='资产库'; break;
  }
  const inspector=module==='CONTROL'||module==='PLUGIN'?null/* [HERMIA-FE-20261022 R7] 单栏全页 */:module==='EDIT'&&novelId?null/* [HERMIA-FE-20261022 R5] 检视器由 EditRebuild 自画（editable={false}） */:module==='ASSETS'&&novelId?null/* [HERMIA-FE-20261022 R6] 右栏由 AssetsRebuild 自画 */:module==='ASSETS'?<>{selectedAsset?<AssetInspector asset={selectedAsset} novelId={novelId}/>:<AssetsEmptyCta onSendToModule={sendAssetsToModule}/>}</>:module==='WORKFLOW'?<WorkflowInspector inspection={workflowInspection} novelId={novelId}/>:module==='IMAGE'?null:module==='VIDEO'&&novelId?null/* [HERMIA-FE-20261022 R3] 视频无右栏 */:module==='VIDEO'?<>{videoInspection?<VideoTaskInspector inspection={videoInspection} novelId={novelId}/>:<VideoEmptyCta onSendToEdit={()=>sendToEdit('VIDEO','视频空态 · 送剪辑')}/>}</>:module==='AUDIO'&&novelId?null/* [HERMIA-FE-20261022 R4] 右栏由 AudioRebuild 自画 */:module==='AUDIO'?<>{audioInspection?<AudioTaskInspector inspection={audioInspection} novelId={novelId}/>:<AudioEmptyCta onSendToEdit={()=>sendToEdit('AUDIO','声音空态 · 送剪辑')}/>}</>:<WorkspaceInspector module={module} novelId={novelId}/>;
  const sidebar=module==='CONTROL'||module==='PLUGIN'?null/* [HERMIA-FE-20261022 R7] */:module==='EDIT'&&novelId?null/* [HERMIA-FE-20261022 R5] 媒体池由 EditRebuild 自画 */:module==='VIDEO'&&novelId?null/* [HERMIA-FE-20261022 R3] 左栏由 VideoRebuild 自画 */:module==='IMAGE'&&novelId?null:module==='AUDIO'&&novelId?null/* [HERMIA-FE-20261022 R4] */:module==='ASSETS'&&novelId?null/* [HERMIA-FE-20261022 R6] 左栏由 AssetsRebuild 自画 */:<WorkspaceRail module={module}/>;
  // EDIT: skip bulky CapabilityStatusCenter above hero timeline (status stays in bar); other modules unchanged.
  const isOverflow = module==='CONTROL'||module==='PLUGIN'||module==='WORKFLOW';
  const shell = mediaShellForModule(module);
  const mainBody=module==='CONTROL'||module==='PLUGIN'?<>{main}</>/* [HERMIA-FE-20261022 R7] 不再挂溢出横幅/能力状态大块 */:shell?<div className="media-ws-main" data-module-shell={shell} data-shell-mode={shellMode} data-x-ux-isolation="per-module">{main}</div>:<>{isOverflow?<OverflowSurfaceBanner module={module}/>:null}<CapabilityStatusCenter module={module} novelId={novelId}/>{main}</>;
  return <AppShell module={module} onModuleChange={onModuleChange} scope={scope} projectNoun={projectNoun} actor={actor} sidebar={sidebar} main={mainBody} inspector={inspector} status={<>{status}{interopEntry}</>} shellMode={shellMode} onShellModeChange={onShellModeChange}/>;
}
