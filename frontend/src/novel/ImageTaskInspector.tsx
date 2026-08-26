import { Image as ImageIcon, WandSparkles } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./ImageTaskInspector.css";

export type ImageInspection = { id: string; status: "QUEUED" | "RUNNING" | "SUCCEEDED" | "FAILED"; providerId: string; modelId: string; assetUri?: string; error?: string; imported?: boolean };
const tone = (status: ImageInspection["status"]) => status === "SUCCEEDED" ? "success" : status === "FAILED" ? "error" : status === "RUNNING" ? "info" : "warning";
const label = (status: ImageInspection["status"]) => status === "SUCCEEDED" ? "已完成" : status === "FAILED" ? "失败" : status === "RUNNING" ? "生成中" : "排队中";

export function ImageTaskInspector({ inspection, novelId }: { inspection?: ImageInspection; novelId?: string }) {
  if (!inspection) return <section className="image-task-inspector" aria-label="图片任务检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="暂无图片任务" detail={novelId ? "提交生成任务或从历史记录选择真实结果。" : "请先打开小说项目。"}/></section>;
  return <section className="image-task-inspector" aria-label="图片任务检查面板">
    <div className="workspace-inspector__eyebrow">Image Task</div>
    <header><WandSparkles aria-hidden="true"/><div><strong>图片生成任务</strong><span>{inspection.id}</span></div><Badge tone={tone(inspection.status)}>{label(inspection.status)}</Badge></header>
    <div className="image-task-inspector__preview" aria-busy={inspection.status === "RUNNING"}>{inspection.assetUri ? <img src={inspection.assetUri} alt="当前图片生成结果" referrerPolicy="no-referrer"/> : <div><ImageIcon aria-hidden="true"/><span>{inspection.status === "FAILED" ? "未生成可用图片" : "等待 Provider 返回结果"}</span></div>}</div>
    <dl className="image-task-inspector__facts"><div><dt>Provider</dt><dd>{inspection.providerId}</dd></div><div><dt>模型</dt><dd>{inspection.modelId}</dd></div><div><dt>小说项目</dt><dd>{novelId || "未选择"}</dd></div><div><dt>资产库</dt><dd>{inspection.imported ? "已导入" : inspection.assetUri ? "尚未导入" : "无结果"}</dd></div></dl>
    {inspection.error ? <div className="image-task-inspector__error" role="alert"><strong>失败摘要</strong><p>{inspection.error}</p></div> : <p className="novel-help">Inspector 不保存生成 Prompt、凭据或完整 Provider 响应。</p>}
  </section>;
}
