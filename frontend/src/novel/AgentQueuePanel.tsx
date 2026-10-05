import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { useStudio } from "../store";
import { Button, Panel } from "../ui/primitives";
import {
  FOCUS_FAILED_TASKS_EVENT,
  publishTaskSummary,
} from "../ui/taskSummary";
import "./WorkflowConsole.css";
import type { WorkflowInspection } from "./WorkflowInspector";

export function AgentQueuePanel({ novelId, onInspect }: { novelId?: string; onInspect?: (inspection: WorkflowInspection) => void }) {
  const selectedModel = useStudio(state => state.textModel);
  const [chapter, setChapter] = useState(1);
  const [busy, setBusy] = useState(false);
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
  async function action(work: () => Promise<unknown>) {
    setBusy(true);setError("");
    try { await work();await refresh(); } catch { setError("Agent 操作失败，请检查模型配置、权限和任务状态。"); }
    finally { setBusy(false); }
  }
  return (
    <Panel title="Agent 队列" className="agent-queue-console">
      <p className="novel-help">使用写作区已选择的模型执行。结果保留在 Agent Job，需审核后再决定是否采用；可能产生服务商费用。</p>
      <label>章节编号<input type="number" min={1} value={chapter} onChange={event => setChapter(Number(event.target.value))} /></label>
      <p>{selectedModel ? `${selectedModel.providerId} / ${selectedModel.modelId}` : "请先在写作区选择已配置模型。"}</p>
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
          {item.status === "QUEUED" && <Button variant="ghost" disabled={busy || !selectedModel || chapter < 1} onClick={() => selectedModel && action(() => api.executeWorkflowAgent(item.run_id,item.node_id,{chapter,provider_id:selectedModel.providerId,model_id:selectedModel.modelId}))}>执行所选模型</Button>}
          {item.status === "WORKING" && <Button variant="ghost" disabled={busy} onClick={() => action(() => api.syncWorkflowAgent(item.run_id,item.node_id))}>同步真实结果</Button>}
        </p>
      ))}
      </div>
    </Panel>
  );
}
