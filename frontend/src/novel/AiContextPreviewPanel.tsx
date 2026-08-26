import { useEffect, useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, ApiError, apiErrorView, type AgentContextPreview } from "../api";
import { Badge, Button, EmptyState, Spinner, StatusMessage } from "../ui/primitives";
import "./AiContextPreview.css";

export type ContextPreviewOperation = "continue" | "rewrite" | "polish" | "brainstorm";
export type ContextPreviewTarget = "local" | "cloud";

type SourceStatus = "loaded" | "empty" | "unconfigured" | "loading" | "error" | "permission";
type SourceCard = {
  id: string;
  label: string;
  value?: unknown;
  status: SourceStatus;
  summary?: string;
  emptyHint: string;
};

const agentForOperation: Record<ContextPreviewOperation, string> = {
  continue: "writer",
  rewrite: "writer",
  polish: "editor",
  brainstorm: "planner",
};

const statusLabels: Record<SourceStatus, string> = {
  loaded: "已读取",
  empty: "无相关数据",
  unconfigured: "未配置",
  loading: "加载中",
  error: "加载失败",
  permission: "权限不足",
};

const statusTones: Record<SourceStatus, "neutral" | "info" | "success" | "warning" | "error"> = {
  loaded: "success",
  empty: "neutral",
  unconfigured: "warning",
  loading: "info",
  error: "error",
  permission: "error",
};

const isRecord = (value: unknown): value is Record<string, unknown> =>
  typeof value === "object" && value !== null && !Array.isArray(value);

const own = (value: Record<string, unknown> | undefined, key: string) =>
  !!value && Object.prototype.hasOwnProperty.call(value, key);

const hasValue = (value: unknown): boolean => {
  if (value === undefined || value === null) return false;
  if (typeof value === "string") return value.trim().length > 0;
  if (Array.isArray(value)) return value.length > 0;
  if (isRecord(value)) return Object.keys(value).length > 0;
  return true;
};

const asArray = (value: unknown): unknown[] | undefined =>
  Array.isArray(value) ? value : undefined;

const asRecord = (value: unknown): Record<string, unknown> | undefined =>
  isRecord(value) ? value : undefined;

function valueSummary(value: unknown, revealLabels = true): string {
  if (Array.isArray(value)) {
    const names = revealLabels ? value
      .slice(0, 3)
      .map((item) => {
        const row = asRecord(item);
        return row ? String(row.name || row.title || row.id || "") : "";
      })
      .filter(Boolean) : [];
    const suffix = value.length > 3 ? ` 等 ${value.length} 项` : ` ${value.length} 项`;
    return names.length ? `${names.join("、")}${suffix}` : `${value.length} 项`;
  }
  if (isRecord(value)) {
    const keys = Object.keys(value);
    return keys.length <= 4
      ? `${keys.length} 个字段：${keys.join("、")}`
      : `${keys.length} 个字段`;
  }
  if (typeof value === "string") return value.length > 100 ? `${value.slice(0, 100)}…` : value;
  return String(value);
}

function queryErrorStatus(error: unknown): "error" | "permission" {
  return error instanceof ApiError && (error.status === 401 || error.status === 403)
    ? "permission"
    : "error";
}

function queryErrorMessage(error: unknown, fallback: string): string {
  return apiErrorView(error, fallback).message;
}

function querySource(
  value: unknown,
  query: { isPending: boolean; error: unknown },
  absent: "empty" | "unconfigured" = "empty",
  revealLabels = true,
): { value?: unknown; status: SourceStatus; summary?: string } {
  if (query.isPending) return { status: "loading" };
  if (query.error) return { status: queryErrorStatus(query.error) };
  if (!hasValue(value)) return { value, status: absent };
  return { value, status: "loaded", summary: valueSummary(value, revealLabels) };
}

function sourceCards(
  context: AgentContextPreview,
  goalQuery: { isPending: boolean; error: unknown; data?: unknown },
  canonQuery: { isPending: boolean; error: unknown; data?: unknown },
  worldRulesQuery: { isPending: boolean; error: unknown; data?: { items?: unknown[] } },
  revealLabels: boolean,
  allowRelatedQueries: boolean,
): SourceCard[] {
  const sections = context.sections || {};
  const writingContext = asRecord(sections.writing_context);
  const storyState = asRecord(writingContext?.current_story_state);
  const characterRows = sections.characters;
  const activeCharacters = storyState?.active_characters;
  const characterValue = hasValue(characterRows) || hasValue(activeCharacters)
    ? { active_characters: activeCharacters, records: characterRows }
    : undefined;
  const contextCanonValue = hasValue(sections.canon)
    ? sections.canon
    : hasValue(writingContext?.canon)
      ? writingContext?.canon
      : undefined;
  const contextRules = writingContext?.must_not_include;
  const approvedRules = worldRulesQuery.data?.items;
  const rulesValue = hasValue(contextRules) || hasValue(approvedRules)
    ? { context_constraints: contextRules, approved_rules: approvedRules }
    : undefined;
  const chapterValue = own(writingContext, "chapter") || context.chapter_id
    ? { number: writingContext?.chapter, id: context.chapter_id, version: context.chapter_version }
    : undefined;
  const volumeValue = writingContext?.volume;
  const timelineValue = hasValue(sections.timeline)
    ? sections.timeline
    : storyState?.timeline;
  const foreshadowingValue = hasValue(sections.foreshadowing)
    ? sections.foreshadowing
    : writingContext?.active_foreshadowing;
  const loreValue = writingContext?.lore_memory;
  const packValue = writingContext?.context_pack_v2;

  const cards: SourceCard[] = [];
  const add = (card: SourceCard) => cards.push(card);
  const simple = (
    id: string,
    label: string,
    value: unknown,
    emptyHint: string,
    absent: "empty" | "unconfigured" = "empty",
    summary?: string,
  ) => {
    const state = querySource(value, { isPending: false, error: undefined }, absent, revealLabels);
    add({ id, label, emptyHint, ...state, summary: summary || state.summary });
  };
  simple("chapter", "当前章节", chapterValue, "在左侧章节树中打开一个有效章节。");
  simple("volume", "当前卷", volumeValue, "在剧情规划或卷编辑入口补充卷信息。");
  const characterSummary = [
    hasValue(activeCharacters) ? `当前：${valueSummary(activeCharacters, revealLabels)}` : "",
    hasValue(characterRows) ? `资料：${valueSummary(characterRows, revealLabels)}` : "",
  ].filter(Boolean).join(" · ");
  simple("characters", "当前人物状态", characterValue, "在故事资料库 → 人物中补充人物，并在当前故事状态中关联。", "empty", characterSummary);
  simple("locations", "当前地点", sections.locations, "在故事资料库 → 地点中补充地点资料。");
  simple("timeline", "当前时间线", timelineValue, "在故事资料库 → 时间线中补充已确认事件。");
  const canonSourceQuery = allowRelatedQueries && !hasValue(contextCanonValue)
    ? canonQuery
    : { isPending: false, error: undefined, data: undefined };
  const worldRulesSourceQuery = allowRelatedQueries && !hasValue(contextRules)
    ? worldRulesQuery
    : { isPending: false, error: undefined, data: undefined };
  const contextCanon = hasValue(contextCanonValue) ? contextCanonValue : canonQuery.data;
  add({
    id: "canon",
    label: "已确认 Canon",
    emptyHint: allowRelatedQueries
      ? "在故事资料库 → Canon 中审核并确认事实。"
      : "云端安全上下文未返回未经筛选的 Canon；切换到本地目标后可检查本机资料。",
    ...querySource(contextCanon, canonSourceQuery, allowRelatedQueries ? "empty" : "unconfigured", revealLabels),
  });
  simple("foreshadowing", "相关伏笔", foreshadowingValue, "在故事资料库 → 伏笔中补充并标记开放伏笔。");
  add({
    id: "lore",
    label: "Lore Memory",
    emptyHint: "启用 Lore Memory，并在记忆审核入口批准可用记忆。",
    ...querySource(loreValue, { isPending: false, error: undefined }, "unconfigured", revealLabels),
  });
  add({
    id: "goal",
    label: "当前写作目标",
    emptyHint: "在概览 → 写作目标中设置目标字数、章节数或截止日期。",
    ...querySource(goalQuery.data, goalQuery, "empty", revealLabels),
  });
  add({
    id: "rules",
    label: "世界规则约束",
    emptyHint: "在一致性检查 → 世界规则中审核并批准规则。",
    ...querySource(rulesValue, worldRulesSourceQuery, "unconfigured", revealLabels),
  });
  add({
    id: "pack",
    label: "Context Pack",
    emptyHint: "当前运行时未启用 Context Pack V2；不代表生成失败。",
    ...querySource(packValue, { isPending: false, error: undefined }, "unconfigured", revealLabels),
  });
  return cards;
}

function SourceRow({ source }: { source: SourceCard }) {
  return (
    <li className="ai-context-preview__source">
      <div className="ai-context-preview__source-head">
        <strong>{source.label}</strong>
        <Badge tone={statusTones[source.status]}>{statusLabels[source.status]}</Badge>
      </div>
      {source.status === "loaded" && (
        <p className="novel-help">{source.summary || valueSummary(source.value)}</p>
      )}
      {source.status === "loading" && (
        <p className="novel-help" role="status">正在读取此来源…</p>
      )}
      {(source.status === "error" || source.status === "permission") && (
        <p className="novel-help">{source.status === "permission" ? "当前会话没有读取权限。" : "来源读取失败，请重试。"}</p>
      )}
      {(source.status === "empty" || source.status === "unconfigured") && (
        <EmptyState title={statusLabels[source.status]} detail={source.emptyHint} />
      )}
    </li>
  );
}

export function AiContextPreviewPanel({
  novelId,
  chapterNumber,
  operation,
  instruction,
  defaultTarget = "local",
  disabled = false,
}: {
  novelId?: string;
  chapterNumber?: number;
  operation: ContextPreviewOperation;
  instruction: string;
  defaultTarget?: ContextPreviewTarget;
  disabled?: boolean;
}) {
  const [target, setTarget] = useState<ContextPreviewTarget>(defaultTarget);
  const [request, setRequest] = useState<{
    operation: ContextPreviewOperation;
    instruction: string;
    target: ContextPreviewTarget;
  }>();
  const [refreshNonce, setRefreshNonce] = useState(0);
  useEffect(() => {
    setRequest(undefined);
  }, [novelId, chapterNumber]);
  useEffect(() => {
    setTarget(defaultTarget);
  }, [defaultTarget]);

  const agentId = agentForOperation[operation];
  const canPreview = !!novelId && chapterNumber !== undefined;
  const contextQuery = useQuery({
    queryKey: [
      "ai-context-preview",
      novelId,
      chapterNumber,
      request?.operation,
      agentId,
      request?.instruction,
      request?.target,
      refreshNonce,
    ],
    queryFn: () =>
      api.agentContext(
        agentId,
        novelId!,
        chapterNumber!,
        request?.instruction || "",
        request?.target || target,
      ),
    enabled: canPreview && !!request,
    retry: false,
  });
  const secondaryEnabled = canPreview && !!request && !!contextQuery.data;
  const goalQuery = useQuery({
    queryKey: ["ai-context-preview-writing-goal", novelId, refreshNonce],
    queryFn: () => api.writingGoal(novelId!),
    enabled: secondaryEnabled,
    retry: false,
  });
  const canonQuery = useQuery({
    queryKey: ["ai-context-preview-canon", novelId, refreshNonce],
    queryFn: () => api.resource(novelId!, "canon"),
    enabled: secondaryEnabled && request?.target === "local",
    retry: false,
  });
  const worldRulesQuery = useQuery({
    queryKey: ["ai-context-preview-world-rules", novelId, refreshNonce],
    queryFn: () => api.worldRules(novelId!, "APPROVED"),
    enabled: secondaryEnabled && request?.target === "local",
    retry: false,
  });
  const cards = useMemo(
    () =>
      contextQuery.data
        ? sourceCards(
            contextQuery.data,
            goalQuery,
            canonQuery,
            worldRulesQuery,
            request?.target !== "cloud",
            request?.target === "local",
          )
        : [],
    [contextQuery.data, goalQuery, canonQuery, worldRulesQuery, request?.target],
  );
  const currentInstruction = instruction.trim();
  const requestIsCurrent =
    !!request &&
    request.operation === operation &&
    request.instruction === currentInstruction &&
    request.target === target;
  const refresh = () => {
    if (!canPreview) return;
    setRequest({ operation, instruction: currentInstruction, target });
    setRefreshNonce((value) => value + 1);
  };
  const contextError = contextQuery.error
    ? queryErrorMessage(contextQuery.error, "上下文服务暂时无法读取。")
    : "";
  const writingContext = asRecord(contextQuery.data?.sections?.writing_context);
  const privacyOmissions = asArray(writingContext?.privacy_omissions);

  return (
    <section className="ai-context-preview" aria-labelledby="ai-context-preview-title">
      <header className="ai-context-preview__header">
        <div>
          <h3 id="ai-context-preview-title">AI Context Preview</h3>
          <p className="novel-help">生成前查看本次角色上下文服务实际返回的资料。</p>
        </div>
        <Badge tone={requestIsCurrent && contextQuery.isSuccess ? "success" : "info"}>
          {requestIsCurrent && contextQuery.isSuccess ? "已同步" : "生成前检查"}
        </Badge>
      </header>
      <div className="ai-context-preview__controls">
        <label>
          上下文目标
          <select
            aria-label="上下文目标"
            value={target}
            disabled={disabled}
            onChange={(event) => setTarget(event.target.value as ContextPreviewTarget)}
          >
            <option value="local">本地上下文</option>
            <option value="cloud">云端安全上下文</option>
          </select>
        </label>
        <Button
          type="button"
          variant="secondary"
          disabled={!canPreview || disabled}
          loading={contextQuery.isFetching}
          onClick={refresh}
        >
          刷新上下文
        </Button>
      </div>
      {!canPreview && (
        <EmptyState title="尚未选择章节" detail="在左侧章节树打开章节后，才能读取真实上下文。" />
      )}
      {canPreview && !request && (
        <StatusMessage tone="info">点击“刷新上下文”，读取当前写作方式对应的 Context Service 数据。</StatusMessage>
      )}
      {canPreview && request && contextQuery.isPending && (
        <div className="ai-context-preview__loading" role="status">
          <Spinner size="sm" /> 正在读取章节、世界观与上下文策略…
        </div>
      )}
      {canPreview && request && contextQuery.error && (
        <StatusMessage tone="error">
          <strong>{contextQueryErrorTitle(contextQuery.error)}</strong>
          <p>{contextError}</p>
          <Button type="button" onClick={refresh} disabled={disabled}>重试读取</Button>
        </StatusMessage>
      )}
      {canPreview && request && contextQuery.data && !contextQuery.error && (
        <>
          {!requestIsCurrent && (
            <StatusMessage tone="warning">写作方式、附加要求或目标已变化；刷新后才会得到对应上下文。</StatusMessage>
          )}
          <dl className="ai-context-preview__meta">
            <div><dt>Agent</dt><dd>{contextQuery.data.agent_name || contextQuery.data.agent_id || agentId}</dd></div>
            <div><dt>目标</dt><dd>{contextQuery.data.target === "cloud" ? "云端安全" : "本地"}</dd></div>
            <div><dt>章节版本</dt><dd>{contextQuery.data.chapter_version ?? "—"}</dd></div>
            <div><dt>Context Hash</dt><dd><code>{contextQuery.data.context_hash || "—"}</code></dd></div>
          </dl>
          {privacyOmissions && privacyOmissions.length > 0 && (
            <StatusMessage tone="info">云端安全策略省略 {privacyOmissions.length} 项本地资料；未把省略内容伪装成已读取。</StatusMessage>
          )}
          <ul className="ai-context-preview__sources" aria-label="AI 上下文来源">
            {cards.map((source) => <SourceRow key={source.id} source={source} />)}
          </ul>
        </>
      )}
    </section>
  );
}

function contextQueryErrorTitle(error: unknown): string {
  return queryErrorStatus(error) === "permission" ? "没有读取上下文的权限" : "上下文读取失败";
}
