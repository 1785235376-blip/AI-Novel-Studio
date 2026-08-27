import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api, ApiError } from "../api";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";

const SOURCE_TYPES = ["NOTE", "BOOK", "ARTICLE", "WEBSITE", "ARCHIVE", "INTERVIEW", "OTHER"] as const;

type Draft = {
  title: string;
  source_type: (typeof SOURCE_TYPES)[number];
  status: "ACTIVE" | "ARCHIVED";
  tags: string;
  excerpt: string;
  notes: string;
};

const emptyDraft = (): Draft => ({ title: "", source_type: "NOTE", status: "ACTIVE", tags: "", excerpt: "", notes: "" });

function parseTags(value: string) {
  return value.split(/[,，]/).map((item) => item.trim()).filter(Boolean);
}

export function ResearchPanel({ novelId }: { novelId: string }) {
  const qc = useQueryClient();
  const [status, setStatus] = useState("");
  const [sourceType, setSourceType] = useState("");
  const [tag, setTag] = useState("");
  const [draft, setDraft] = useState<Draft>(emptyDraft);
  const [editingId, setEditingId] = useState<string>();
  const [editingVersion, setEditingVersion] = useState<number>();
  const [pendingDelete, setPendingDelete] = useState<{ id: string; version: number; title: string }>();
  const [message, setMessage] = useState("");
  const query = useQuery({
    queryKey: ["research", novelId, status, sourceType, tag],
    queryFn: () => api.listResearch(novelId, { status: status || undefined, source_type: sourceType || undefined, tag: tag || undefined }),
    enabled: !!novelId,
  });
  const refresh = () => qc.invalidateQueries({ queryKey: ["research", novelId] });
  const bodyFromDraft = () => ({
    title: draft.title.trim(),
    source_type: draft.source_type,
    status: draft.status,
    tags: parseTags(draft.tags),
    excerpt: draft.excerpt,
    notes: draft.notes,
  });
  const create = useMutation({
    mutationFn: () => api.createResearch(novelId, bodyFromDraft()),
    onSuccess: (item) => {
      setMessage(`已新建资料 ${item.id}`);
      setDraft(emptyDraft());
      refresh();
    },
    onError: (error) => setMessage(error instanceof ApiError ? error.problem.message : "新建失败"),
  });
  const save = useMutation({
    mutationFn: () => api.updateResearch(novelId, editingId!, bodyFromDraft(), editingVersion),
    onSuccess: () => {
      setMessage("资料已保存");
      setEditingId(undefined);
      setDraft(emptyDraft());
      refresh();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) {
        setMessage("版本冲突：记录已被更新，请重新加载后再编辑。");
        refresh();
        return;
      }
      setMessage(error instanceof ApiError ? error.problem.message : "保存失败");
    },
  });
  const remove = useMutation({
    mutationFn: () => api.deleteResearch(novelId, pendingDelete!.id, pendingDelete!.version),
    onSuccess: () => {
      setMessage("资料已删除");
      setPendingDelete(undefined);
      refresh();
    },
    onError: (error) => {
      if (error instanceof ApiError && error.status === 409) setMessage("删除冲突：请刷新后重试。");
      else setMessage(error instanceof ApiError ? error.problem.message : "删除失败");
    },
  });
  const items = query.data?.items || [];
  const filteredHint = useMemo(() => [status, sourceType, tag].filter(Boolean).join(" / ") || "未筛选", [status, sourceType, tag]);
  if (!novelId) return <EmptyState title="未选择小说" detail="研究资料按小说隔离，请先打开一部小说。" />;
  return (
    <Panel title="研究资料" actions={<Badge tone="info">{query.data?.storage || "durable_sidecar"}</Badge>}>
      <p className="novel-help">本地 sidecar（v1_capabilities/research.json），不读取外部网络。筛选：{filteredHint}</p>
      <div className="novel-actions">
        <label>状态
          <select aria-label="研究资料状态筛选" value={status} onChange={(e) => setStatus(e.target.value)}>
            <option value="">全部状态</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>
        </label>
        <label>来源
          <select aria-label="研究资料来源筛选" value={sourceType} onChange={(e) => setSourceType(e.target.value)}>
            <option value="">全部来源</option>
            {SOURCE_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>标签<input aria-label="研究资料标签筛选" value={tag} onChange={(e) => setTag(e.target.value)} /></label>
      </div>
      {query.isLoading && <p role="status">正在加载研究资料…</p>}
      {query.error && <p className="novel-error" role="alert">加载失败，请稍后重试。</p>}
      {!query.isLoading && !items.length && <EmptyState title="暂无研究资料" detail="新建一条记录后可以筛选、编辑、处理版本冲突并删除。" />}
      <ul className="novel-record-list" aria-label="研究资料列表">
        {items.map((item) => (
          <li key={item.id}>
            <article>
              <header>
                <strong>{item.title}</strong>
                <Badge>{item.status}</Badge>
              </header>
              <p className="novel-help">{item.source_type} · v{item.version} · {(item.tags || []).join("、") || "无标签"}</p>
              <p>{item.excerpt || item.notes || "无摘要"}</p>
              <div className="novel-actions">
                <Button onClick={() => {
                  setEditingId(item.id);
                  setEditingVersion(item.version);
                  setDraft({
                    title: item.title || "",
                    source_type: item.source_type || "NOTE",
                    status: item.status === "ARCHIVED" ? "ARCHIVED" : "ACTIVE",
                    tags: (item.tags || []).join(","),
                    excerpt: item.excerpt || "",
                    notes: item.notes || "",
                  });
                }}>编辑</Button>
                <Button variant="danger" onClick={() => setPendingDelete({ id: item.id, version: item.version, title: item.title })}>删除</Button>
              </div>
            </article>
          </li>
        ))}
      </ul>
      {pendingDelete && (
        <section className="novel-dialog" role="alertdialog" aria-label="删除确认">
          <p>确认删除「{pendingDelete.title}」？此操作写入 sidecar 删除标记，不能从其他小说访问。</p>
          <div className="novel-actions">
            <Button onClick={() => setPendingDelete(undefined)}>取消</Button>
            <Button variant="danger" disabled={remove.isPending} onClick={() => remove.mutate()}>再次确认删除</Button>
          </div>
        </section>
      )}
      <form className="novel-ai-panel" onSubmit={(event) => { event.preventDefault(); editingId ? save.mutate() : create.mutate(); }}>
        <h3>{editingId ? "编辑资料" : "新建资料"}</h3>
        <label>标题<input required value={draft.title} onChange={(e) => setDraft({ ...draft, title: e.target.value })} /></label>
        <label>来源类型
          <select value={draft.source_type} onChange={(e) => setDraft({ ...draft, source_type: e.target.value as Draft["source_type"] })}>
            {SOURCE_TYPES.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </label>
        <label>状态
          <select value={draft.status} onChange={(e) => setDraft({ ...draft, status: e.target.value as Draft["status"] })}>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ARCHIVED">ARCHIVED</option>
          </select>
        </label>
        <label>标签<input value={draft.tags} onChange={(e) => setDraft({ ...draft, tags: e.target.value })} placeholder="用逗号分隔，需唯一" /></label>
        <label>摘要<textarea value={draft.excerpt} onChange={(e) => setDraft({ ...draft, excerpt: e.target.value })} /></label>
        <label>笔记<textarea value={draft.notes} onChange={(e) => setDraft({ ...draft, notes: e.target.value })} /></label>
        <div className="novel-actions">
          {editingId && <Button type="button" onClick={() => { setEditingId(undefined); setDraft(emptyDraft()); }}>取消编辑</Button>}
          <Button variant="primary" type="submit" disabled={create.isPending || save.isPending || !draft.title.trim()}>
            {editingId ? "保存修改" : "新建资料"}
          </Button>
        </div>
      </form>
      {message && <p role="status" className="novel-help">{message}</p>}
    </Panel>
  );
}
