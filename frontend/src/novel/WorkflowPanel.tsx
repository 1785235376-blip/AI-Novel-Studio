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

export function WorkflowPanel({ novelId, onInspect }: { novelId?: string; onInspect?: (inspection: WorkflowInspection) => void }) {
  const branchId = useStudio((state) => state.scope?.branchId);
  const [sourceText, setSourceText] = useState("");
  const [busy, setBusy] = useState(false);
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
    setSelected(undefined); setRuns([]); setSourceText("");
    refresh();
  }, [novelId, branchId]);
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
      if (template.startsWith("recipe:")) {
        await api.createWorkflowRecipe(template.slice(7), novelId, branchId);
      } else await api.createWorkflow({
        branch_id: branchId,
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
  async function action(work: () => Promise<unknown>) {
    setBusy(true); setError("");
    try { await work(); if(selected) await loadRuns(selected.id); }
    catch { setError("操作失败；请检查权限、输入和任务当前状态后重试。"); }
    finally { setBusy(false); }
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
            <option value="recipe:import_knowledge">导入资料 → 知识候选 → 审核</option>
            <option value="recipe:planning_draft">创作规划 → 草稿 → 审阅</option>
            <option value="recipe:screenplay_assets">剧本 → 镜头分镜 → 资源任务提案</option>
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
          <p className="novel-help">配方使用本地规则整理输入，结果仅为审核材料。不会自动修改正文、Canon 或提交外部资源任务。</p>
          <label>配方输入（每行一条资料、创作要点或场景）<textarea value={sourceText} maxLength={20000} rows={5} onChange={event => setSourceText(event.target.value)} /></label>
          <Button disabled={busy}
            onClick={() => action(() => api.createWorkflowRun(selected.id, {
                input: { source_text: sourceText },
                initiated_by: "local-author",
              }))}
          >
            启动运行
          </Button>
          {runs.map((run) => (
            <div key={run.id} className="workflow-console__run">
              运行 {run.id} · {run.status}{" "}
              <Button variant="ghost" onClick={() => onInspect?.({ kind: "run", id: String(run.id), status: run.status, workflowTitle: selected.title || selected.name || selected.id, currentNodeId: run.current_node_id, error: run.error || run.error_message })}>检查</Button>
              <Button
                variant="ghost" disabled={busy || !["QUEUED","RUNNING","WAITING_APPROVAL"].includes(run.status)}
                onClick={() => action(() => api.pauseWorkflow(run.id))}
              >
                暂停
              </Button>
              <Button
                variant="ghost" disabled={busy || run.status !== "PAUSED"}
                onClick={() => action(() => api.resumeWorkflow(run.id))}
              >
                恢复
              </Button>
              <Button variant="ghost" disabled={busy || ["SUCCEEDED","FAILED","CANCELLED","REJECTED"].includes(run.status)} onClick={() => action(() => api.cancelWorkflow(run.id))}>取消</Button>
              {["FAILED","CANCELLED"].includes(run.status) && <Button variant="ghost" disabled={busy} onClick={() => action(() => api.retryWorkflow(run.id))}>重新运行（新审批）</Button>}
              {Object.entries(run.node_states || {}).map(([nodeId, state]: any) => state.status === "WAITING_APPROVAL" && run.status === "WAITING_APPROVAL" && state.output?.execution !== "DEFERRED" && <span key={nodeId}>
                <Button variant="ghost" disabled={busy} onClick={() => action(() => api.approveWorkflowNode(run.id,nodeId))}>批准当前节点</Button>
                <Button variant="ghost" disabled={busy} onClick={() => action(() => api.rejectWorkflowNode(run.id,nodeId))}>拒绝并停止</Button>
              </span>)}
              <details><summary>节点结果与来源</summary><textarea aria-label={`运行 ${run.id} 结果`} readOnly rows={8} value={JSON.stringify(run.node_states,null,2)} /></details>
              {run.node_states &&
                Object.entries(run.node_states).map(
                  ([nodeId, state]: any) =>
                    state.status === "WAITING_APPROVAL" && run.status === "WAITING_APPROVAL" &&
                    state.output?.execution === "DEFERRED" && (
                      <Button
                        key={nodeId}
                        variant="ghost"
                        disabled={busy} onClick={() => action(() => api.triggerAgentNode(run.id, nodeId))}
                      >
                        触发 Agent
                      </Button>
                    ),
                )}
            </div>
          ))}
        </section>
      )}
    </Panel>
  );
}
