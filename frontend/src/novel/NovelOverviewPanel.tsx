import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import { Badge, EmptyState, Panel } from "../ui/primitives";

const COUNT_LABELS: { key: string; label: string }[] = [
  { key: "chapters", label: "章节" },
  { key: "characters", label: "人物" },
  { key: "locations", label: "地点" },
  { key: "timeline", label: "时间线" },
  { key: "foreshadowing", label: "伏笔" },
  { key: "world_rules", label: "规则" },
  { key: "research", label: "研究资料" },
];

export function NovelOverviewPanel({ novelId }: { novelId: string }) {
  const qc = useQueryClient();
  const overview = useQuery({
    queryKey: ["novel-overview", novelId],
    queryFn: () => api.novelOverview(novelId),
    enabled: !!novelId,
  });
  const goal = useQuery({
    queryKey: ["writing-goal", novelId],
    queryFn: () => api.writingGoal(novelId),
    enabled: !!novelId,
  });
  const [targetWords, setTargetWords] = useState(100000);
  const [targetChapters, setTargetChapters] = useState(50);
  const [deadline, setDeadline] = useState("");
  useEffect(() => {
    const data = goal.data || overview.data?.writing_goal;
    if (data) {
      setTargetWords(Number(data.target_words) || 0);
      setTargetChapters(Number(data.target_chapters) || 0);
      setDeadline(data.deadline || "");
    }
  }, [goal.data, overview.data]);
  const save = useMutation({
    mutationFn: () =>
      api.updateWritingGoal(novelId, {
        target_words: targetWords,
        target_chapters: targetChapters,
        deadline: deadline || undefined,
      }),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["writing-goal", novelId] });
      qc.invalidateQueries({ queryKey: ["novel-overview", novelId] });
    },
  });
  if (!novelId) return <EmptyState title="未选择小说" detail="先打开一部小说再查看概览。" />;
  if (overview.isLoading) return <Panel title="项目概览"><p role="status">正在加载真实项目计数…</p></Panel>;
  if (overview.error) {
    const view = overview.error instanceof ApiError ? overview.error.problem.message : "概览加载失败";
    return <Panel title="项目概览"><p className="novel-error" role="alert">{view}</p></Panel>;
  }
  const data = overview.data!;
  const counts = data.counts || {};
  return (
    <>
      <Panel title="项目概览">
        <p className="novel-help">计数来自当前小说的持久化数据，不是“服务尚未接入”占位。</p>
        <dl className="novel-overview-counts" aria-label="项目计数">
          <div><dt>字数</dt><dd>{data.content?.word_count ?? 0}</dd></div>
          {COUNT_LABELS.map((item) => (
            <div key={item.key}><dt>{item.label}</dt><dd>{counts[item.key] ?? 0}</dd></div>
          ))}
        </dl>
        <h3>待处理项</h3>
        {data.pending_items?.length ? (
          <ul className="novel-record-list" aria-label="待处理项">
            {data.pending_items.map((item, index) => (
              <li key={`${item.kind}-${index}`}><article><p>{item.label}</p></article></li>
            ))}
          </ul>
        ) : (
          <p className="novel-help">当前没有待处理项。</p>
        )}
        <h3>近期活动</h3>
        {data.recent_activity?.length ? (
          <ul className="novel-record-list" aria-label="近期活动">
            {data.recent_activity.map((event) => (
              <li key={event.id}>
                <article>
                  <header><strong>{event.action}</strong><Badge>{event.target_type}</Badge></header>
                  <p className="novel-help">{event.created_at} · {event.target_id}</p>
                </article>
              </li>
            ))}
          </ul>
        ) : (
          <p className="novel-help">还没有审计活动。</p>
        )}
      </Panel>
      <section className="panel writing-goal-panel">
        <h2>写作目标</h2>
        <p>目标进度：字数 {Math.round((goal.data?.words_progress || data.writing_goal?.words_progress || 0) * 100)}% · 章节 {Math.round((goal.data?.chapters_progress || data.writing_goal?.chapters_progress || 0) * 100)}%</p>
        <label>目标字数<input type="number" min={1} value={targetWords} onChange={(e) => setTargetWords(Number(e.target.value))} /></label>
        <label>目标章节<input type="number" min={1} value={targetChapters} onChange={(e) => setTargetChapters(Number(e.target.value))} /></label>
        <label>截止日期<input type="date" value={deadline ? deadline.slice(0, 10) : ""} onChange={(e) => setDeadline(e.target.value)} /></label>
        <button className="primary" disabled={save.isPending || targetWords < 1 || targetChapters < 1} onClick={() => save.mutate()}>{save.isPending ? "保存中…" : "保存写作目标"}</button>
        {save.isSuccess && <small className="notice">目标已更新</small>}
        {save.error && <small className="notice">保存失败，请重试</small>}
      </section>
    </>
  );
}
