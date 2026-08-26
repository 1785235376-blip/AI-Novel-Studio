import { Film, Image as ImageIcon } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./VideoTaskInspector.css";

export type VideoInspection = { id: string; status?: string; screenplayId?: string; transitionId?: string; providerId?: string; modelId?: string; progress?: number; startFrame?: string; endFrame?: string; resultUrl?: string; assetId?: string; error?: string; pendingRefresh?: boolean };
const tone = (status?: string) => { const value=String(status||"").toUpperCase(); return value==="SUCCEEDED"?"success":value==="FAILED"?"error":value==="RUNNING"?"info":"warning"; };

export function VideoTaskInspector({ inspection, novelId }: { inspection?: VideoInspection; novelId?: string }) {
  if (!inspection) return <section className="video-task-inspector" aria-label="视频任务检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="暂无视频任务" detail={novelId ? "选择一个 Motion Task 查看真实生成状态。" : "请先打开小说项目。"}/></section>;
  const progress=Math.max(0,Math.min(100,Number(inspection.progress||0)));
  return <section className="video-task-inspector" aria-label="视频任务检查面板">
    <div className="workspace-inspector__eyebrow">Motion Task</div>
    <header><Film aria-hidden="true"/><div><strong>视频生成任务</strong><span>{inspection.id}</span></div><Badge tone={tone(inspection.status)}>{inspection.status||"待刷新"}</Badge></header>
    {inspection.status==="RUNNING"&&<div className="video-task-inspector__progress" role="progressbar" aria-label="视频生成进度" aria-valuemin={0} aria-valuemax={100} aria-valuenow={progress}><span style={{width:`${progress}%`}}/><small>{progress}%</small></div>}
    <div className="video-task-inspector__preview">{inspection.resultUrl?<video src={inspection.resultUrl} controls preload="metadata" aria-label="当前视频生成结果"/>:<div><Film aria-hidden="true"/><span>{inspection.status==="SUCCEEDED"?"任务成功，但未发布可播放 URL":"尚无真实视频结果"}</span></div>}</div>
    {(inspection.startFrame||inspection.endFrame)&&<div className="video-task-inspector__frames">{inspection.startFrame?<img src={inspection.startFrame} alt="Motion Task 起始帧"/>:<span><ImageIcon aria-hidden="true"/>未配置起始帧</span>}{inspection.endFrame?<img src={inspection.endFrame} alt="Motion Task 结束帧"/>:<span><ImageIcon aria-hidden="true"/>未配置结束帧</span>}</div>}
    {inspection.pendingRefresh&&<p className="video-task-inspector__notice">已从任务 Dock 定位，详细记录尚未加载，请刷新视频任务。</p>}
    <dl className="video-task-inspector__facts"><div><dt>Provider</dt><dd>{inspection.providerId||"未配置"}</dd></div><div><dt>模型</dt><dd>{inspection.modelId||"未配置"}</dd></div><div><dt>剧本 ID</dt><dd>{inspection.screenplayId||"未读取"}</dd></div><div><dt>转场 ID</dt><dd>{inspection.transitionId||"未关联"}</dd></div><div><dt>资产 ID</dt><dd>{inspection.assetId||"未生成"}</dd></div></dl>
    {inspection.error?<div className="video-task-inspector__error" role="alert"><strong>失败摘要</strong><p>{inspection.error}</p></div>:<p className="novel-help">本地镜头和转场配置不等于视频已生成；仅真实结果 URL 可播放。</p>}
  </section>;
}
