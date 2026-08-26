import { BookOpenText, Mic2, Volume2 } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./AudioTaskInspector.css";

export type AudioInspection = { kind: "speech" | "audiobook"; id: string; status?: string; chapterId?: string; providerId?: string; modelId?: string; voice?: string; emotion?: string; audioUri?: string; imported?: boolean; error?: string; pendingRefresh?: boolean };
const tone=(status?:string)=>{const value=String(status||"").toUpperCase();return ["SUCCEEDED","COMPLETED"].includes(value)?"success":value==="FAILED"?"error":["RUNNING","PROCESSING"].includes(value)?"info":"warning";};
export function AudioTaskInspector({inspection,novelId}:{inspection?:AudioInspection;novelId?:string}){
  if(!inspection)return <section className="audio-task-inspector" aria-label="声音任务检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="暂无声音任务" detail={novelId?"生成配音或检查有声书队列任务。":"请先打开小说项目。"}/></section>;
  return <section className="audio-task-inspector" aria-label="声音任务检查面板"><div className="workspace-inspector__eyebrow">{inspection.kind==="speech"?"Speech Task":"Audiobook Job"}</div><header>{inspection.kind==="speech"?<Mic2 aria-hidden="true"/>:<BookOpenText aria-hidden="true"/>}<div><strong>{inspection.kind==="speech"?"单次配音":"有声书章节"}</strong><span>{inspection.id}</span></div><Badge tone={tone(inspection.status)}>{inspection.status||"待刷新"}</Badge></header>
    <div className="audio-task-inspector__player">{inspection.audioUri?<audio src={inspection.audioUri} controls preload="metadata" aria-label="当前语音生成结果"/>:<div><Volume2 aria-hidden="true"/><span>{inspection.status==="FAILED"?"未生成可用音频":"等待真实音频结果"}</span></div>}</div>
    {inspection.pendingRefresh&&<p className="audio-task-inspector__notice">已从任务 Dock 定位，详细记录尚未加载，请刷新声音任务。</p>}
    <dl className="audio-task-inspector__facts"><div><dt>Provider</dt><dd>{inspection.providerId||"未读取"}</dd></div><div><dt>模型</dt><dd>{inspection.modelId||"未读取"}</dd></div><div><dt>音色</dt><dd>{inspection.voice||"未读取"}</dd></div><div><dt>情绪</dt><dd>{inspection.emotion||"未读取"}</dd></div>{inspection.chapterId&&<div><dt>章节 ID</dt><dd>{inspection.chapterId}</dd></div>}<div><dt>资产库</dt><dd>{inspection.imported?"已导入":inspection.audioUri?"尚未导入":"无结果"}</dd></div></dl>
    {inspection.error?<div className="audio-task-inspector__error" role="alert"><strong>失败摘要</strong><p>{inspection.error}</p></div>:<p className="novel-help">Inspector 不保存朗读全文、凭据或完整 Provider 响应。</p>}
  </section>;
}
