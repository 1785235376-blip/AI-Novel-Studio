import {useState, type ReactNode} from 'react';
import type {Asset} from '../api';
import {AppShell, type ScopeLabels, type StudioModule} from './AppShell';
import {VisionAnalysisPanel} from '../novel/VisionAnalysisPanel';
import {ImageGenerationPanel} from '../novel/ImageGenerationPanel';
import {VisualContextPanel} from '../novel/VisualContextPanel';
import {ScreenplayPanel} from '../novel/ScreenplayPanel';
import {SpeechSynthesisPanel} from '../novel/SpeechSynthesisPanel';
import {AudiobookManifestPanel} from '../novel/AudiobookManifestPanel';
import {PluginManagerPanel} from '../novel/PluginManagerPanel';
import {WorkflowPanel} from '../novel/WorkflowPanel';
import {AgentQueuePanel} from '../novel/AgentQueuePanel';
import {AssetLibraryPanel} from '../novel/AssetLibraryPanel';
import {AssetInspector} from '../novel/AssetInspector';
import {WorkflowInspector, type WorkflowInspection} from '../novel/WorkflowInspector';
import {ImageTaskInspector, type ImageInspection} from '../novel/ImageTaskInspector';
import {VideoTaskInspector, type VideoInspection} from '../novel/VideoTaskInspector';
import {AudioTaskInspector, type AudioInspection} from '../novel/AudioTaskInspector';
import {PluginInspector, type PluginInspection} from '../novel/PluginInspector';
import {CapabilityStatusCenter} from './CapabilityStatusCenter';
import {AiControlCenter} from './AiControlCenter';
import {MultimodalDirectorWorkspace} from '../novel/MultimodalDirectorWorkspace';

interface Props {module: StudioModule; onModuleChange:(value:StudioModule)=>void; scope:ScopeLabels; actor:string; novelId?:string;}
const moduleLabels: Record<StudioModule, string> = { NOVEL: '小说', IMAGE: '图片', VIDEO: '视频', AUDIO: '声音', CONTROL: '主控', PLUGIN: '插件', WORKFLOW: '工作流', ASSETS: '资产' };
function WorkspaceRail({ module }: { module: StudioModule }) {
  return <nav className="workspace-rail" aria-label={`${moduleLabels[module]}工作区导航`}><div className="workspace-rail__eyebrow">当前工作区</div><strong>{moduleLabels[module]}</strong><button className="is-active">工作区概览</button><button>最近编辑</button><button>待处理任务</button><div className="workspace-rail__future"><span>预留入口</span><small>AI Copilot</small><small>Provider 状态</small><small>审批队列</small></div></nav>;
}
function WorkspaceInspector({ module, novelId }: { module: StudioModule; novelId?: string }) {
  const context: Record<StudioModule, { focus: string; slot: string }> = {
    NOVEL: { focus: '章节、Canon 与写作目标', slot: '预留：AI Context / 章节状态' },
    IMAGE: { focus: '参考图、构图与一致性约束', slot: '预留：图片任务 / 资产预览' },
    VIDEO: { focus: '当前镜头、转场与时间线轨道', slot: '预留：Motion Task / 视频预览' },
    AUDIO: { focus: '声音档案、对白与配音批次', slot: '预留：音频波形 / Provider 任务' },
    CONTROL: { focus: '模型、Provider、凭据与路由策略', slot: '预留：主控对话 / 模型诊断' },
    PLUGIN: { focus: '插件能力与运行权限', slot: '预留：插件详情 / 权限审批' },
    WORKFLOW: { focus: 'Job 队列与执行状态', slot: '预留：运行时间线 / 重试操作' },
    ASSETS: { focus: '资产元数据与引用关系', slot: '预留：媒体预览 / 使用位置' },
  };
  return <section className="workspace-inspector__empty" aria-label="工作区检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><strong>{moduleLabels[module]}上下文</strong><p>当前关注：{context[module].focus}</p><dl className="workspace-inspector__facts"><div><dt>小说项目</dt><dd>{novelId || '未选择'}</dd></div><div><dt>工作区</dt><dd>{moduleLabels[module]}</dd></div><div><dt>运行状态</dt><dd><span className="ui-badge ui-badge--info">等待真实任务</span></dd></div></dl><div className="workspace-inspector__slot">{context[module].slot}</div></section>;
}
export function ModuleWorkspaceRoutes({module,onModuleChange,scope,actor,novelId}:Props){
  const [selectedAsset,setSelectedAsset]=useState<Asset>();
  const [workflowInspection,setWorkflowInspection]=useState<WorkflowInspection>();
  const [imageInspection,setImageInspection]=useState<ImageInspection>();
  const [videoInspection,setVideoInspection]=useState<VideoInspection>();
  const [audioInspection,setAudioInspection]=useState<AudioInspection>();
  const [pluginInspection,setPluginInspection]=useState<PluginInspection>();
  let main:ReactNode; let status='工作区';
  switch(module){
    case 'IMAGE': main=<><MultimodalDirectorWorkspace mode="image" novelId={novelId}/><VisualContextPanel novelId={novelId ?? ''}/><VisionAnalysisPanel novelId={novelId ?? ''}/><ImageGenerationPanel novelId={novelId ?? ''} onInspect={setImageInspection}/></>; status='图片工作区'; break;
    case 'VIDEO': main=novelId?<><MultimodalDirectorWorkspace mode="video" novelId={novelId}/><ScreenplayPanel novelId={novelId} onInspect={setVideoInspection}/></>:<p className="novel-help">请先打开小说项目，再进入视频工作区。</p>; status='视频工作区'; break;
    case 'AUDIO': main=<><SpeechSynthesisPanel novelId={novelId ?? ''} onInspect={setAudioInspection}/><AudiobookManifestPanel novelId={novelId ?? ''} onInspect={setAudioInspection}/></>; status='声音工作区'; break;
    case 'CONTROL': main=<AiControlCenter/>; status='AI 主控'; break;
    case 'PLUGIN': main=<PluginManagerPanel onInspect={setPluginInspection}/>; status='插件管理'; break;
    case 'WORKFLOW': main=<><WorkflowPanel novelId={novelId ?? ''} onInspect={setWorkflowInspection}/><AgentQueuePanel novelId={novelId ?? ''} onInspect={setWorkflowInspection}/></>; status='工作流'; break;
    case 'ASSETS': main=<AssetLibraryPanel novelId={novelId ?? ''} selectedAssetId={selectedAsset?.id} onSelectAsset={setSelectedAsset}/>; status='资产库'; break;
    default: main=<p className="novel-help">请选择一个工作区。</p>;
  }
  const inspector=module==='ASSETS'?<AssetInspector asset={selectedAsset} novelId={novelId}/>:module==='WORKFLOW'?<WorkflowInspector inspection={workflowInspection} novelId={novelId}/>:module==='IMAGE'?<ImageTaskInspector inspection={imageInspection} novelId={novelId}/>:module==='VIDEO'?<VideoTaskInspector inspection={videoInspection} novelId={novelId}/>:module==='AUDIO'?<AudioTaskInspector inspection={audioInspection} novelId={novelId}/>:module==='PLUGIN'?<PluginInspector inspection={pluginInspection}/>:<WorkspaceInspector module={module} novelId={novelId}/>;
  return <AppShell module={module} onModuleChange={onModuleChange} scope={scope} actor={actor} sidebar={<WorkspaceRail module={module}/>} main={<><CapabilityStatusCenter module={module === 'NOVEL' ? 'WORKFLOW' : module} novelId={novelId}/>{main}</>} inspector={inspector} status={status}/>;
}
