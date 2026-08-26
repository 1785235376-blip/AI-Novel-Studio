import { useEffect, useState } from "react";
import { useMutation, useQuery } from "@tanstack/react-query";
import { api, type Chapter } from "../api";
import { useStudio } from "../store";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";
import { AgentResultReview, type AgentReviewJob } from "./AgentResultReview";
import { AgentJobDetail } from "./AgentJobDetail";

function AgentJobHistoryLegacy({
  novelId,
  agents = [],
}: {
  novelId?: string;
  agents?: { id: string; name: string }[];
}) {
  const [agentId, setAgentId] = useState(""),
    [status, setStatus] = useState(""),
    [page, setPage] = useState(1),
    [selectedJobId, setSelectedJobId] = useState<string>();
  const history = useQuery({
    queryKey: ["agent-job-history", novelId, agentId, status, page],
    queryFn: () =>
      api.agentJobs({
        novelId,
        agentId: agentId || undefined,
        status: status || undefined,
        page,
        pageSize: 10,
      }),
    enabled: !!novelId,
  });
  return (
    <Panel title="Agent Job 历史">
      <section className="novel-draft-review">
        <div className="novel-actions">
          <label>
            Agent 筛选
            <select
              aria-label="历史 Agent 筛选"
              value={agentId}
              onChange={(e) => {
                setAgentId(e.target.value);
                setPage(1);
              }}
            >
              <option value="">全部 Agent</option>
              {agents.map((a) => (
                <option key={a.id} value={a.id}>
                  {a.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            状态筛选
            <select
              aria-label="历史状态筛选"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">全部状态</option>
              {[
                "QUEUED",
                "WORKING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                "ACCEPTED",
                "REJECTED",
              ].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
        </div>
        {history.isLoading && <p role="status">正在加载历史…</p>}
        <ul className="novel-record-list" aria-label="Agent Job 历史记录">
          {history.data?.items.map((item) => (
            <li key={item.id}>
              <article>
                <header>
                  <strong>{item.agent_name}</strong>
                  <Badge>{item.status}</Badge>
                </header>
                <p className="novel-help">
                  {item.instruction || "未填写说明"} · {item.created_at}
                </p>
                {item.error_code && (
                  <p className="novel-error">失败原因：{item.error_code}</p>
                )}
                {item.retry_of && (
                  <p className="novel-help">重试自：{item.retry_of}</p>
                )}
                {item.review && (
                  <p className="novel-help">
                    审核：{item.review.decision} · {item.review.reviewed_by}
                  </p>
                )}
              </article>
            </li>
          ))}
        </ul>
        <div className="novel-actions">
          <Button
            disabled={page <= 1}
            onClick={() => setPage((p) => Math.max(1, p - 1))}
          >
            上一页
          </Button>
          <span>
            第 {page} 页 · 共 {history.data?.total || 0} 条
          </span>
          <Button
            disabled={!history.data?.has_more}
            onClick={() => setPage((p) => p + 1)}
          >
            下一页
          </Button>
        </div>
      </section>
    </Panel>
  );
}

export function AgentJobHistory({ novelId }: { novelId?: string }) {
  const branchId = useStudio((value) => value.scope?.branchId);
  const [status, setStatus] = useState(""),
    [agentId, setAgentId] = useState(""),
    [createdAfter, setCreatedAfter] = useState(""),
    [createdBefore, setCreatedBefore] = useState(""),
    [page, setPage] = useState(1),
    [auditAfter, setAuditAfter] = useState(""),
    [auditBefore, setAuditBefore] = useState(""),
    [auditPage, setAuditPage] = useState(1),
    [auditSelected, setAuditSelected] = useState<string>(),
    [selected, setSelected] = useState<string>();
  const catalog = useQuery({ queryKey: ["agent-job-history-catalog"], queryFn: api.agents, retry: false });
  const history = useQuery({
    queryKey: ["agent-job-history-v2", novelId, branchId, status, agentId, createdAfter, createdBefore, page],
    queryFn: () =>
      api.agentJobs({
        novelId,
        branchId,
        status: status || undefined,
        agentId: agentId || undefined,
        createdAfter: createdAfter || undefined,
        createdBefore: createdBefore || undefined,
        page,
        pageSize: 10,
      }),
    enabled: !!novelId,
  });
  const audit = useQuery({
    queryKey: ["agent-job-export-audit", novelId, branchId, auditAfter, auditBefore, auditPage],
    queryFn: () => api.agentJobAudit(novelId!, branchId!, { createdAfter: auditAfter || undefined, createdBefore: auditBefore || undefined, page: auditPage, pageSize: 10 }),
    enabled: !!novelId && !!branchId,
    retry: false,
  });
  return (
    <>
      <Panel title="Agent Job 历史">
        <section className="novel-draft-review">
          <label>
            Agent 筛选
            <select aria-label="历史 Agent 筛选" value={agentId} onChange={(e) => { setAgentId(e.target.value); setPage(1); }}>
              <option value="">全部 Agent</option>
              {catalog.data?.agents.map((agent) => <option key={agent.id} value={agent.id}>{agent.name}</option>)}
            </select>
          </label>
          <label>
            状态筛选
            <select
              aria-label="历史状态筛选"
              value={status}
              onChange={(e) => {
                setStatus(e.target.value);
                setPage(1);
              }}
            >
              <option value="">全部状态</option>
              {[
                "QUEUED",
                "WORKING",
                "COMPLETED",
                "FAILED",
                "CANCELLED",
                "ACCEPTED",
                "REJECTED",
              ].map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
            </select>
          </label>
          <label>开始日期<input aria-label="历史开始日期" type="date" value={createdAfter} onChange={(e) => { setCreatedAfter(e.target.value); setPage(1); }} /></label>
          <label>结束日期<input aria-label="历史结束日期" type="date" value={createdBefore} onChange={(e) => { setCreatedBefore(e.target.value); setPage(1); }} /></label>
          <Button onClick={async () => { const blob=await api.agentJobsExport({novelId,branchId,agentId:agentId||undefined,status:status||undefined,createdAfter:createdAfter||undefined,createdBefore:createdBefore||undefined}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='agent-jobs.csv'; link.click(); URL.revokeObjectURL(url); }}>导出 CSV</Button>
          <ul className="novel-record-list">
            {history.data?.items.map((item) => (
              <li key={item.id}>
                <article>
                  <header>
                    <strong>{item.agent_name}</strong>
                    <Badge>{item.status}</Badge>
                  </header>
                  <p className="novel-help">
                    {item.instruction || "未填写说明"} · {item.created_at}
                  </p>
                  <Button onClick={() => setSelected(item.id)}>查看详情</Button>
                </article>
              </li>
            ))}
          </ul>
          <div className="novel-actions">
            <Button disabled={page <= 1} onClick={() => setPage((p) => p - 1)}>
              上一页
            </Button>
            <span>
              第 {page} 页 · 共 {history.data?.total || 0} 条
            </span>
            <Button
              disabled={!history.data?.has_more}
              onClick={() => setPage((p) => p + 1)}
            >
              下一页
            </Button>
          </div>
        </section>
      </Panel>
      {branchId && (
        <Panel title="导出审计">
          <section className="novel-draft-review">
            <label>开始日期<input aria-label="审计开始日期" type="date" value={auditAfter} onChange={(e) => { setAuditAfter(e.target.value); setAuditPage(1); }} /></label>
            <label>结束日期<input aria-label="审计结束日期" type="date" value={auditBefore} onChange={(e) => { setAuditBefore(e.target.value); setAuditPage(1); }} /></label>
            <Button onClick={async () => { const blob=await api.agentJobAuditExport(novelId!,branchId!,{createdAfter:auditAfter||undefined,createdBefore:auditBefore||undefined}); const url=URL.createObjectURL(blob); const link=document.createElement('a'); link.href=url; link.download='agent-job-audit.csv'; link.click(); URL.revokeObjectURL(url); }}>导出审计 CSV</Button>
          </section>
          {audit.isLoading && <p className="novel-help">正在加载审计记录…</p>}
          {!audit.isLoading && !(audit.data?.items?.length) && (
            <EmptyState title="暂无导出记录" detail="当前分支的 Agent Job CSV 导出会记录在这里。" />
          )}
          {!!audit.data?.items?.length && (
            <>
            <ul className="novel-record-list">
              {audit.data.items.map((event) => {
                const metadata = event.metadata || {};
                const filters = (metadata.filters || {}) as Record<string, unknown>;
                return (
                  <li key={event.id}>
                    <article>
                      <header><strong>{event.actor_id}</strong><Badge tone="info">AGENT_JOB_EXPORT</Badge></header>
                      <p className="novel-help">{event.timestamp} · 结果 {String(metadata.result_count ?? 0)} 条</p>
                      <p className="novel-help">筛选：{String(filters.status || "全部状态")} / {String(filters.agent_id || "全部 Agent")}</p>
                      <Button onClick={() => setAuditSelected(auditSelected === event.id ? undefined : event.id)}>
                        {auditSelected === event.id ? "收起详情" : "查看摘要"}
                      </Button>
                      {auditSelected === event.id && (
                        <pre className="novel-help">{JSON.stringify({
                          action: event.action,
                          actor_id: event.actor_id,
                          target_type: event.target_type,
                          target_id: event.target_id,
                          timestamp: event.timestamp,
                          metadata: { result_count: metadata.result_count, filters },
                        }, null, 2)}</pre>
                      )}
                    </article>
                  </li>
                );
              })}
            </ul>
            <div className="novel-actions">
              <Button disabled={auditPage <= 1} onClick={() => setAuditPage((p) => p - 1)}>上一页</Button>
              <span>第 {auditPage} 页 · 共 {audit.data.total} 条</span>
              <Button disabled={!audit.data.has_more} onClick={() => setAuditPage((p) => p + 1)}>下一页</Button>
            </div>
            </>
          )}
        </Panel>
      )}
      {selected && (
        <>
          <AgentJobDetail jobId={selected} />
          <Button onClick={() => setSelected(undefined)}>关闭详情</Button>
        </>
      )}
    </>
  );
}

export function AgentTeamPanel({ chapter }: { chapter?: Chapter }) {
  const query = useQuery({
      queryKey: ["creative-agent-catalog"],
      queryFn: api.agents,
      retry: false,
    }),
    models = useQuery({
      queryKey: ["text-models"],
      queryFn: api.textModels,
      retry: false,
    });
  const actor = useStudio((value) => value.actor),
    scope = useStudio((value) => value.scope),
    selectedModel = useStudio((value) => value.textModel);
  const [agentId, setAgentId] = useState("planner"),
    [instruction, setInstruction] = useState(""),
    [mode, setMode] = useState<"deterministic" | "model">("deterministic"),
    [job, setJob] = useState<any>();
  const create = useMutation({
    mutationFn: async () => {
      if (!chapter) throw new Error("请先选择章节");
      const created = await api.createAgentJob({
        agent_id: agentId,
        novel_id: chapter.novel_id,
        chapter: chapter.number,
        instruction,
        target: mode === "model" ? "cloud" : "local",
        execution_mode: mode,
        provider_id: mode === "model" ? selectedModel?.providerId : undefined,
        model_id: mode === "model" ? selectedModel?.modelId : undefined,
        branch_id: scope?.branchId,
      });
      setJob(created);
      return api.startAgentJob(created.id);
    },
    onSuccess: setJob,
  });
  const cancel = useMutation({
      mutationFn: () => api.cancelAgentJob(job.id),
      onSuccess: setJob,
    }),
    retry = useMutation({
      mutationFn: async () => {
        const next = await api.retryAgentJob(job.id);
        setJob(next);
        return api.startAgentJob(next.id);
      },
      onSuccess: setJob,
    }),
    review = useMutation({
      mutationFn: (decision: "ACCEPTED" | "REJECTED") =>
        api.reviewAgentJob(job.id, decision, actor?.id || "local-author"),
      onSuccess: setJob,
    }),
    apply = useMutation({
      mutationFn: () => api.applyAgentJob(job.id, actor?.id || "local-author"),
      onSuccess: setJob,
    });
  useEffect(() => {
    if (
      !job?.id ||
      ["COMPLETED", "FAILED", "CANCELLED", "ACCEPTED", "REJECTED"].includes(
        job.status,
      )
    )
      return;
    const timer = setInterval(
      () =>
        api
          .agentJob(job.id)
          .then(setJob)
          .catch(() => {}),
      500,
    );
    return () => clearInterval(timer);
  }, [job?.id, job?.status]);
  if (query.isLoading)
    return (
      <Panel title="Creative Agent 团队">
        <p role="status">正在加载 Agent 角色…</p>
      </Panel>
    );
  if (query.error)
    return (
      <Panel title="Creative Agent 团队">
        <div className="novel-error" role="alert">
          <strong>无法加载 Agent 团队</strong>
          <p>{String(query.error)}</p>
        </div>
      </Panel>
    );
  if (!query.data?.agents.length)
    return (
      <Panel title="Creative Agent 团队">
        <EmptyState title="暂无 Agent" detail="当前没有已注册的创作角色。" />
      </Panel>
    );
  const busy =
      job &&
      !["COMPLETED", "FAILED", "CANCELLED", "ACCEPTED", "REJECTED"].includes(
        job.status,
      ),
    selected = query.data.agents.find((item) => item.id === agentId);
  return (
    <>
      <Panel title="Creative Agent 任务">
        <section
          className="novel-draft-review"
          aria-labelledby="agent-job-title"
        >
          <header>
            <strong id="agent-job-title">创建 Agent 任务</strong>
            {job && <Badge>{job.status}</Badge>}
          </header>
          <label>
            Agent 角色
            <select
              value={agentId}
              disabled={!!busy}
              onChange={(event) => setAgentId(event.target.value)}
            >
              {query.data.agents.map((agent) => (
                <option key={agent.id} value={agent.id}>
                  {agent.name}
                </option>
              ))}
            </select>
          </label>
          <p className="novel-help">{selected?.description}</p>
          <label>
            执行方式
            <select
              value={mode}
              disabled={!!busy}
              onChange={(event) =>
                setMode(event.target.value as "deterministic" | "model")
              }
            >
              <option value="deterministic">本地契约验证</option>
              <option value="model" disabled={!selectedModel}>
                当前文本模型
              </option>
            </select>
          </label>
          {mode === "model" && (
            <p className="novel-help">
              {selectedModel
                ? `模型：${selectedModel.providerId} / ${selectedModel.modelId}`
                : "请先选择可用模型。"}
            </p>
          )}
          <label>
            任务说明
            <textarea
              value={instruction}
              disabled={!!busy}
              onChange={(event) => setInstruction(event.target.value)}
            />
          </label>
          <div className="novel-actions">
            {busy ? (
              <Button
                disabled={cancel.isPending}
                onClick={() => cancel.mutate()}
              >
                取消任务
              </Button>
            ) : (
              <Button
                variant="primary"
                disabled={
                  !chapter ||
                  create.isPending ||
                  (mode === "model" && !selectedModel)
                }
                onClick={() => create.mutate()}
              >
                启动任务
              </Button>
            )}
            {job && ["FAILED", "CANCELLED"].includes(job.status) && (
              <Button disabled={retry.isPending} onClick={() => retry.mutate()}>
                重试任务
              </Button>
            )}
          </div>
          {job?.error && (
            <p className="novel-error" role="alert">
              {job.error}
            </p>
          )}
        </section>
      </Panel>
      {job?.status === "COMPLETED" && (
        <AgentResultReview
          job={job as AgentReviewJob}
          reviewing={review.isPending}
          onAccept={() => review.mutate("ACCEPTED")}
          onReject={() => review.mutate("REJECTED")}
        />
      )}{" "}
      {job?.status === "ACCEPTED" && (
        <>
          <AgentResultReview
            job={job as AgentReviewJob}
            onAccept={() => {}}
            onReject={() => {}}
          />
          <Panel title="受控应用">
            <Button
              variant="primary"
              disabled={apply.isPending || job.review?.applied}
              onClick={() => apply.mutate()}
            >
              {job.review?.applied ? "已应用" : "应用已审核修改"}
            </Button>
          </Panel>
        </>
      )}
      <Panel title="Agent 角色目录">
        <ul className="novel-record-list" aria-label="Creative Agent 角色">
          {query.data.agents.map((agent) => (
            <li key={agent.id}>
              <article>
                <header>
                  <strong>{agent.name}</strong>
                  <Badge tone={agent.requires_approval ? "warning" : "info"}>
                    {agent.requires_approval ? "需要作者确认" : "只读检查"}
                  </Badge>
                </header>
                <p>{agent.description}</p>
                <p className="novel-help">输出契约：{agent.output_schema}</p>
                <p className="novel-help">允许工具：{agent.tools.join("、")}</p>
              </article>
            </li>
          ))}
        </ul>
      </Panel>
    </>
  );
}
