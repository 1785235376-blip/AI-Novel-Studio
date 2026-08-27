import { useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError, type Chapter } from "../api";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";

type Finding = {
  id: string;
  finding_type?: string;
  severity?: string;
  description?: string;
  status?: string;
  code?: string;
};

export function ContinuityCheckPanel({ projectId, chapter }: { projectId: string; chapter?: Chapter }) {
  const qc = useQueryClient();
  const rules = useQuery({
    queryKey: ["world-rules", projectId, "APPROVED"],
    queryFn: () => api.worldRules(projectId, "APPROVED"),
    enabled: !!projectId,
  });
  const stored = useQuery({
    queryKey: ["continuity-findings", projectId],
    queryFn: () => api.continuityFindings(projectId),
    enabled: !!projectId,
  });
  const [facts, setFacts] = useState('{\n  "events": [],\n  "locations": [],\n  "knowledge": []\n}');
  const [result, setResult] = useState<{ status?: string; findings?: Finding[]; foreshadowing?: { overdue?: Finding[]; pending?: Finding[] }; execution_label?: string; engine_status?: string; placeholder?: boolean }>();
  const [error, setError] = useState("");
  const [filter, setFilter] = useState("ALL");
  const scan = useMutation({
    mutationFn: () => api.scanChapterContinuity(projectId, { chapter_id: chapter?.id, chapter: chapter?.number }),
    onSuccess: (body) => {
      setError("");
      setResult(body);
      qc.invalidateQueries({ queryKey: ["continuity-findings", projectId] });
    },
    onError: (reason) => {
      setError(reason instanceof ApiError ? reason.problem.message : "检查失败，请稍后重试");
    },
  });
  async function runJson() {
    try {
      setError("");
      const parsed = JSON.parse(facts);
      setResult(await api.continuityCheck(projectId, { ...parsed, world_rules: rules.data?.items || [] }));
      qc.invalidateQueries({ queryKey: ["continuity-findings", projectId] });
    } catch (reason) {
      setError(reason instanceof SyntaxError ? "事实 JSON 格式错误" : "检查失败，请稍后重试");
    }
  }
  const scanFindings = result?.findings || [];
  const rows = [...scanFindings, ...(stored.data || [])]
    .filter((item, index, all) => all.findIndex((other) => other.id === item.id) === index)
    .filter((item) => filter === "ALL" || item.finding_type === filter);
  const types = Array.from(new Set([...scanFindings, ...(stored.data || [])].map((item) => item.finding_type).filter(Boolean))) as string[];
  const overdue = result?.foreshadowing?.overdue || [];
  if (!projectId) return <EmptyState title="未选择小说" detail="先打开一部小说再做一致性检查。" />;
  return (
    <Panel title="一致性检查" actions={<Badge tone="info">{result?.execution_label || "契约校验，未调用模型"}</Badge>}>
      {!chapter ? (
        <EmptyState title="请先选择章节" detail="主路径会读取当前章节正文和故事资料库，不再要求粘贴 JSON。" />
      ) : (
        <p className="novel-help">
          检查第 {chapter.number} 章「{chapter.title}」的正文、人物状态、世界规则禁词和逾期伏笔。这是契约校验，不是模型评审。
        </p>
      )}
      <div className="novel-actions">
        <Button variant="primary" onClick={() => scan.mutate()} disabled={!chapter || scan.isPending} loading={scan.isPending}>
          检查当前章节
        </Button>
      </div>
      {result && (
        <p className="novel-help" role="status">
          状态 {result.status}
          {result.engine_status ? ` · 规则引擎 ${result.engine_status}` : ""}
          {result.placeholder === false ? " · 不是占位结果" : ""}
        </p>
      )}
      {overdue.length > 0 && (
        <div>
          <strong>逾期伏笔</strong>
          <ul className="novel-record-list" aria-label="逾期伏笔">
            {overdue.map((item: any) => (
              <li key={item.id || item.title}><article><p>{item.title || item.description}</p></article></li>
            ))}
          </ul>
        </div>
      )}
      {error && <p role="alert">{error}</p>}
      {(rules.isError || stored.isError) && <p role="alert">问题清单加载失败，请稍后重试。</p>}
      <div>
        <strong>问题清单</strong>
        {stored.isLoading && <p role="status">正在加载历史问题…</p>}
        <select value={filter} onChange={(event) => setFilter(event.target.value)} aria-label="筛选问题类型">
          <option value="ALL">全部类型</option>
          {types.map((type) => <option key={type} value={type}>{type}</option>)}
        </select>
        {!stored.isLoading && !rows.length && <p className="notice">暂无问题</p>}
        {rows.map((item) => (
          <p key={item.id} className="notice">
            [{item.severity}] {item.description}{" "}
            {item.status === "RESOLVED" ? <small>已处理</small> : (
              <button
                type="button"
                onClick={async () => {
                  try {
                    await api.resolveContinuityFinding(projectId, item.id);
                    qc.invalidateQueries({ queryKey: ["continuity-findings", projectId] });
                    setResult((old) => old ? { ...old, findings: (old.findings || []).map((row) => row.id === item.id ? { ...row, status: "RESOLVED" } : row) } : old);
                  } catch {
                    setError("标记问题失败，请稍后重试");
                  }
                }}
              >
                标记已处理
              </button>
            )}
          </p>
        ))}
      </div>
      <details>
        <summary>高级：粘贴事实 JSON</summary>
        <p className="novel-help">仅在需要手工注入时间线/地点/知识事实时使用。日常检查请点「检查当前章节」。</p>
        <textarea value={facts} onChange={(event) => setFacts(event.target.value)} rows={9} style={{ width: "100%" }} aria-label="事实 JSON" />
        <Button onClick={runJson} disabled={!projectId}>运行 JSON 检查</Button>
      </details>
    </Panel>
  );
}
