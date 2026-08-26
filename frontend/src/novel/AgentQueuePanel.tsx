import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../ui/primitives";
import {
  FOCUS_FAILED_TASKS_EVENT,
  publishTaskSummary,
} from "../ui/taskSummary";
import "./WorkflowConsole.css";
import type { WorkflowInspection } from "./WorkflowInspector";

export function AgentQueuePanel({ novelId, onInspect }: { novelId?: string; onInspect?: (inspection: WorkflowInspection) => void }) {
  const [items, setItems] = useState<any[]>([]),
    [loading, setLoading] = useState(false),
    [error, setError] = useState("");
  const queue = useRef<HTMLDivElement>(null);
  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.agentQueue(novelId);
      setItems(data.items || []);
      setError("");
    } catch {
      setError("Agent 队列加载失败，请检查连接后重试。");
    } finally {
      setLoading(false);
    }
  };
  useEffect(() => {
    refresh();
  }, [novelId]);
  useEffect(() => {
    publishTaskSummary(
      "agent",
      items.map((item) => ({
        id: `${item.run_id}:${item.node_id}`,
        status: item.status,
        error: item.error || item.error_message,
      })),
    );
  }, [items]);
  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.source !== "agent") return;
      const id = detail.taskId && String(detail.taskId);
      const row = id
        ? [...(queue.current?.querySelectorAll<HTMLElement>("[data-task-id]") || [])].find(
            (item) => item.dataset.taskId === id,
          )
        : undefined;
      const target = id ? items.find((item) => `${item.run_id}:${item.node_id}` === id) : undefined;
      if (target) onInspect?.({ kind: "agent", id, status: target.status, nodeId: target.node_id, agentRole: target.agent_role, error: target.error || target.error_message });
      else if (id) onInspect?.({ kind: "agent", id, status: "FAILED", pendingRefresh: true });
      requestAnimationFrame(() => (row || queue.current)?.focus());
    };
    window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
    return () => window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
  }, [items, onInspect]);
  return (
    <Panel title="Agent 队列" className="agent-queue-console">
      <Button variant="ghost" onClick={refresh}>
        {loading ? "加载中…" : "刷新队列"}
      </Button>
      {!items.length && !loading && (
        <p className="novel-help">当前没有待执行 Agent 任务。</p>
      )}
      {error && <p role="alert">{error}</p>}
      <div ref={queue} className="agent-queue-console__list" tabIndex={-1} aria-label="Agent 任务列表">
      {items.map((item) => (
        <p
          key={`${item.run_id}-${item.node_id}`}
          data-task-id={`${item.run_id}:${item.node_id}`}
          tabIndex={-1}
        >
          运行 {item.run_id} · 节点 {item.node_id} · 角色 {item.agent_role} ·{" "}
          {item.status}{" "}
          <Button variant="ghost" onClick={() => onInspect?.({ kind: "agent", id: `${item.run_id}:${item.node_id}`, status: item.status, nodeId: item.node_id, agentRole: item.agent_role, error: item.error || item.error_message })}>检查</Button>{" "}
          <Button
            variant="ghost"
            onClick={() =>
              api.claimAgentTask(item.run_id, item.node_id).then(refresh)
            }
          >
            领取任务
          </Button>{" "}
          <Button
            variant="ghost"
            onClick={() =>
              api
                .completeAgentTask(item.run_id, item.node_id, "SUCCEEDED", {
                  note: "manual completion",
                })
                .then(refresh)
            }
          >
            标记成功
          </Button>{" "}
          <Button
            variant="ghost"
            onClick={() =>
              api
                .completeAgentTask(
                  item.run_id,
                  item.node_id,
                  "FAILED",
                  undefined,
                  "manual failure",
                )
                .then(refresh)
            }
          >
            标记失败
          </Button>
        </p>
      ))}
      </div>
    </Panel>
  );
}
