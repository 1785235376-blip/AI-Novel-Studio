import { Bot, GitBranch, ShieldAlert } from "lucide-react";
import { Badge, EmptyState } from "../ui/primitives";
import "./WorkflowInspector.css";

export type WorkflowInspection = {
  kind: "run" | "agent";
  id: string;
  status?: string;
  workflowTitle?: string;
  currentNodeId?: string;
  nodeId?: string;
  agentRole?: string;
  error?: string;
  pendingRefresh?: boolean;
};

const tone = (status?: string) => {
  const value = String(status || "").toUpperCase();
  if (["FAILED", "ERROR", "CANCELLED"].includes(value)) return "error" as const;
  if (["SUCCEEDED", "COMPLETED", "DONE"].includes(value)) return "success" as const;
  if (["RUNNING", "PROCESSING"].includes(value)) return "info" as const;
  return "warning" as const;
};

export function WorkflowInspector({ inspection, novelId }: { inspection?: WorkflowInspection; novelId?: string }) {
  if (!inspection) return <section className="workflow-inspector" aria-label="工作流检查面板"><div className="workspace-inspector__eyebrow">Inspector</div><EmptyState title="未选择运行任务" detail={novelId ? "检查一个工作流运行或 Agent 节点以查看真实状态。" : "请先打开小说项目。"}/></section>;
  return <section className="workflow-inspector" aria-label="工作流检查面板">
    <div className="workspace-inspector__eyebrow">{inspection.kind === "run" ? "Run Inspector" : "Agent Inspector"}</div>
    <header>{inspection.kind === "run" ? <GitBranch aria-hidden="true"/> : <Bot aria-hidden="true"/>}<div><strong>{inspection.workflowTitle || (inspection.kind === "run" ? "工作流运行" : "Agent 节点")}</strong><span title={inspection.id}>{inspection.id}</span></div><Badge tone={tone(inspection.status)}>{inspection.status || "待刷新"}</Badge></header>
    {inspection.pendingRefresh && <div className="workflow-inspector__notice"><ShieldAlert aria-hidden="true" size={15}/><span>已从任务 Dock 定位。详细记录尚未加载，请在主工作区刷新对应列表。</span></div>}
    <dl className="workflow-inspector__facts"><div><dt>类型</dt><dd>{inspection.kind === "run" ? "工作流运行" : "Agent 队列节点"}</dd></div><div><dt>小说项目</dt><dd>{novelId || "未选择"}</dd></div>{inspection.currentNodeId && <div><dt>当前节点</dt><dd>{inspection.currentNodeId}</dd></div>}{inspection.nodeId && <div><dt>节点 ID</dt><dd>{inspection.nodeId}</dd></div>}{inspection.agentRole && <div><dt>Agent 角色</dt><dd>{inspection.agentRole}</dd></div>}</dl>
    {inspection.error ? <div className="workflow-inspector__error" role="alert"><strong>失败摘要</strong><p>{inspection.error}</p></div> : <p className="novel-help">没有已发布的失败摘要。审批、暂停、恢复和完成操作仍在主工作区执行。</p>}
  </section>;
}
