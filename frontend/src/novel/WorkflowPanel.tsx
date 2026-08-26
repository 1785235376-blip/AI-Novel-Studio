import { useEffect, useRef, useState } from "react";
import { api } from "../api";
import { Button, Panel } from "../ui/primitives";
import {
  FOCUS_FAILED_TASKS_EVENT,
  publishTaskSummary,
} from "../ui/taskSummary";
import "./WorkflowConsole.css";
import type { WorkflowInspection } from "./WorkflowInspector";

export function WorkflowPanel({ novelId, onInspect }: { novelId?: string; onInspect?: (inspection: WorkflowInspection) => void }) {
  const [items, setItems] = useState<any[]>([]),
    [selected, setSelected] = useState<any>(),
    [runs, setRuns] = useState<any[]>([]),
    [loading, setLoading] = useState(false),
    [title, setTitle] = useState("小说质量检查"),
    [description, setDescription] = useState(""),
    [template, setTemplate] = useState("quality_gate"),
    [error, setError] = useState("");
  const runsSection = useRef<HTMLElement>(null);
  const refreshButton = useRef<HTMLButtonElement>(null);
  const refresh = async () => {
    setLoading(true);
    try {
      const data = await api.workflows(novelId);
      setItems(data.items || []);
      setError("");
    } catch {
      setError("工作流加载失败，请检查连接后重试。");
    } finally {
      setLoading(false);
    }
  };
  const loadRuns = async (id: string) => {
    setSelected(items.find((item) => item.id === id));
    try {
      const data = await api.workflowRuns(id);
      setRuns(data.items || []);
      setError("");
    } catch {
      setError("运行记录加载失败，请刷新后重试。");
    }
  };
  useEffect(() => {
    refresh();
  }, [novelId]);
  useEffect(() => {
    publishTaskSummary(
      "workflow",
      runs.map((run) => ({
        id: run.id,
        status: run.status,
        error: run.error || run.error_message,
      })),
    );
  }, [runs]);
  useEffect(() => {
    const listener = (event: Event) => {
      const detail = (event as CustomEvent).detail;
      if (detail?.source !== "workflow") return;
      const target = detail.taskId
        ? runs.find((run) => String(run.id) === String(detail.taskId))
        : undefined;
      if (target) {
        setSelected(items.find((item) => item.id === target.workflow_id) || selected);
        onInspect?.({ kind: "run", id: String(target.id), status: target.status, workflowTitle: selected?.title || selected?.name, currentNodeId: target.current_node_id, error: target.error || target.error_message });
      } else if (detail.taskId) onInspect?.({ kind: "run", id: String(detail.taskId), status: "FAILED", pendingRefresh: true });
      requestAnimationFrame(() =>
        (runsSection.current || refreshButton.current)?.focus(),
      );
    };
    window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
    return () => window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener);
  }, [items, runs, selected, onInspect]);
  async function create() {
    if (!novelId || !title.trim()) return;
    setError("");
    const names: Record<string, string> = {
      quality_gate: "质量检查",
      manual_approval: "人工审批",
      project_snapshot: "项目快照",
      agent_task: "Agent 任务",
    };
    try {
      await api.createWorkflow({
        novel_id: novelId,
        title: title.trim(),
        description,
        nodes: [
          {
            id: template.replace("_", "-"),
            type: template,
            name: names[template],
            config:
              template === "agent_task"
                ? { agent_role: "writer", execution: "deferred" }
                : {},
          },
        ],
        edges: [],
      });
      await refresh();
    } catch {
      setError("工作流创建失败，请检查项目状态。");
    }
  }
  return (
    <Panel title="工作流编排" className="workflow-console">
      <section>
        <h4>创建工作流</h4>
        <label>
          标题
          <input value={title} onChange={(e) => setTitle(e.target.value)} />
        </label>
        <label>
          模板
          <select
            value={template}
            onChange={(e) => setTemplate(e.target.value)}
          >
            <option value="quality_gate">质量检查</option>
            <option value="manual_approval">人工审批</option>
            <option value="project_snapshot">项目快照</option>
            <option value="agent_task">Agent 任务</option>
          </select>
        </label>
        <label>
          描述
          <textarea
            rows={3}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
          />
        </label>
        <Button disabled={!novelId || !title.trim()} onClick={create}>
          创建工作流
        </Button>
        {error && <p role="alert">{error}</p>}
      </section>
      <Button ref={refreshButton} variant="ghost" onClick={refresh}>
        {loading ? "加载中…" : "刷新工作流"}
      </Button>
      {!items.length && !loading && (
        <p className="novel-help">暂无工作流定义。</p>
      )}
      {items.map((item) => (
        <p key={item.id}>
          {item.title || item.name || item.id} · {item.status || "ACTIVE"}{" "}
          {item.nodes?.some((node: any) => node.type === "agent_task") && (
            <small> · 含延迟 Agent 节点</small>
          )}{" "}
          <Button variant="ghost" onClick={() => loadRuns(item.id)}>
            查看运行
          </Button>
        </p>
      ))}
      {selected && (
        <section ref={runsSection} tabIndex={-1} aria-label="工作流运行记录">
          <h4>{selected.title || selected.name || selected.id} 运行</h4>
          <Button
            onClick={async () => {
              const run = await api.createWorkflowRun(selected.id, {
                input: { novel_id: novelId },
                initiated_by: "local-author",
              });
              setRuns((current) => [run, ...current]);
            }}
          >
            启动运行
          </Button>
          {runs.map((run) => (
            <p key={run.id}>
              运行 {run.id} · {run.status}{" "}
              <Button variant="ghost" onClick={() => onInspect?.({ kind: "run", id: String(run.id), status: run.status, workflowTitle: selected.title || selected.name || selected.id, currentNodeId: run.current_node_id, error: run.error || run.error_message })}>检查</Button>
              <Button
                variant="ghost"
                onClick={() =>
                  api.pauseWorkflow(run.id).then(() => loadRuns(selected.id))
                }
              >
                暂停
              </Button>
              <Button
                variant="ghost"
                onClick={() =>
                  api.resumeWorkflow(run.id).then(() => loadRuns(selected.id))
                }
              >
                恢复
              </Button>
              {run.current_node_id && (
                <Button
                  variant="ghost"
                  onClick={() =>
                    api
                      .approveWorkflowNode(run.id, run.current_node_id)
                      .then(() => loadRuns(selected.id))
                  }
                >
                  批准当前节点
                </Button>
              )}
              {run.node_states &&
                Object.entries(run.node_states).map(
                  ([nodeId, state]: any) =>
                    state.status === "WAITING_APPROVAL" &&
                    state.output?.execution === "DEFERRED" && (
                      <Button
                        key={nodeId}
                        variant="ghost"
                        onClick={() =>
                          api
                            .triggerAgentNode(run.id, nodeId)
                            .then(() => loadRuns(selected.id))
                        }
                      >
                        触发 Agent
                      </Button>
                    ),
                )}
            </p>
          ))}
        </section>
      )}
    </Panel>
  );
}
