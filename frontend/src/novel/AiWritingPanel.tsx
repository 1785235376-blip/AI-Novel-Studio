import { useMemo, useState } from "react";
import { Badge, Button, EmptyState, Panel } from "../ui/primitives";
import type { TextModel, TextRuntimeDiagnostics } from "../api";
import type { TextModelSelection } from "../store";
import { DeepSeekCredentialControl } from "./DeepSeekCredentialControl";
import { AiContextPreviewPanel, type ContextPreviewTarget } from "./AiContextPreviewPanel";
import { GenerationWorkflowTimeline } from "./GenerationWorkflowTimeline";
import "./novel.css";

export type AiOperation = "continue" | "rewrite" | "polish" | "brainstorm";
const stylePresets = ["克制冷峻 · 短句为主", "细腻抒情 · 强化感官", "紧张悬疑 · 加快节奏", "轻松幽默 · 对话自然"];
export type AiDraft = {
  id: string;
  output: string;
  original?: string;
  status: "working" | "ready" | "failed";
  error?: string;
  latency_ms?: number;
  acceptBlocked?: boolean;
  acceptBlockedReason?: string;
  tracked?: boolean;
};
export type AiVariantDraft = AiDraft & {
  variantIndex: number;
  baseChapterVersion?: number;
};
export type AiExperienceState =
  | "no-model"
  | "loading"
  | "unconfigured"
  | "unavailable"
  | "ready"
  | "generating"
  | "cancelling"
  | "failed"
  | "result-ready"
  | "cancelled";
const operationLabels: Record<AiOperation, string> = {
  continue: "创作下一章",
  rewrite: "改写",
  polish: "润色",
  brainstorm: "头脑风暴",
};
type DiffLine = { kind: "same" | "added" | "removed"; text: string };
export function lineDiff(original: string, generated: string): DiffLine[] {
  const left = original.split("\n"),
    right = generated.split("\n"),
    result: DiffLine[] = [];
  const size = Math.max(left.length, right.length);
  for (let i = 0; i < size; i++) {
    if (left[i] === right[i] && left[i] !== undefined)
      result.push({ kind: "same", text: left[i] });
    else {
      if (left[i] !== undefined)
        result.push({ kind: "removed", text: left[i] });
      if (right[i] !== undefined)
        result.push({ kind: "added", text: right[i] });
    }
  }
  return result;
}
export const generationFailureMessage = (value?: string | null) =>
  value === "请先在正文中选择需要改写的文字。" ||
  value === "候选生成超时，请重新生成此候选。" ||
  value === "生成连接中断且恢复超时，请重试" ||
  value === "生成连接中断，恢复失败，请重试" ||
  value === "服务重启导致生成中断，请重新生成。"
    ? value
    : "生成失败，请重试";

export function AiDraftReview({
  draft,
  accepting = false,
  rejecting = false,
  onAccept,
  onReject,
  onRetry,
  onResolveConflict,
}: {
  draft?: AiDraft;
  accepting?: boolean;
  rejecting?: boolean;
  onAccept: (draft: AiDraft) => Promise<void> | void;
  onReject: (draft: AiDraft) => Promise<void> | void;
  onRetry?: (draft: AiDraft) => Promise<void> | void;
  onResolveConflict?: (draft: AiDraft) => Promise<void> | void;
}) {
  const [mode, setMode] = useState<"preview" | "diff">("preview");
  const diff = useMemo(
    () => (draft ? lineDiff(draft.original || "", draft.output) : []),
    [draft],
  );
  if (!draft)
    return (
      <EmptyState
        title="尚未生成草稿"
        detail="选择写作方式并生成后，可在这里预览、比较和决定是否采用。"
      />
    );
  if (draft.status === "working")
    return (
      <p role="status" aria-live="polite">
        AI 正在生成草稿…{draft.latency_ms ? ` 已耗时 ${Math.round(draft.latency_ms / 1000)} 秒` : ""}
      </p>
    );
  if (draft.status === "failed")
    return (
      <section className="novel-draft-review">
        <header>
          <strong>生成结果</strong>
          <Badge tone="error">候选失败</Badge>
        </header>
        <p>{generationFailureMessage(draft.error)}{draft.latency_ms ? `（耗时 ${Math.round(draft.latency_ms / 1000)} 秒）` : ""}</p>
        <p className="novel-help">其他已完成的候选仍可预览和采用。</p>
        <div className="novel-actions">
          {onRetry && (
            <Button
              variant="primary"
              type="button"
              disabled={accepting || rejecting}
              onClick={() => onRetry(draft)}
            >
              重新生成此候选
            </Button>
          )}
          <Button
            type="button"
            disabled={rejecting}
            onClick={() => onReject(draft)}
          >
            {rejecting ? "正在移除…" : "移除失败候选"}
          </Button>
        </div>
      </section>
    );
  return (
    <section className="novel-draft-review">
      <header>
        <strong>生成结果</strong>
        <Badge tone="info">待确认修改</Badge>
        <div
          className="novel-tabs"
          role="tablist"
          aria-label="生成结果查看方式"
        >
          <button
            role="tab"
            aria-selected={mode === "preview"}
            onClick={() => setMode("preview")}
          >
            预览
          </button>
          <button
            role="tab"
            aria-selected={mode === "diff"}
            onClick={() => setMode("diff")}
          >
            差异
          </button>
        </div>
      </header>
      {mode === "preview" ? (
        <pre>{draft.output}</pre>
      ) : (
        <div className="novel-diff" aria-label="原文与草稿差异">
          {diff.map((line, index) => (
            <div key={index} className={`novel-diff--${line.kind}`}>
              <span aria-hidden="true">
                {line.kind === "added"
                  ? "+"
                  : line.kind === "removed"
                    ? "-"
                    : " "}
              </span>
              {line.text || " "}
            </div>
          ))}
        </div>
      )}
      <p className="novel-help">
        {draft.acceptBlockedReason || "采用草稿会通过版本校验保存；不会静默覆盖较新的内容。"}
      </p>
      <div className="novel-actions">
        {draft.acceptBlocked && onResolveConflict && (
          <Button
            variant="primary"
            type="button"
            disabled={accepting || rejecting}
            onClick={() => onResolveConflict(draft)}
          >
            比较与手动合并
          </Button>
        )}
        <Button
          type="button"
          disabled={accepting || rejecting}
          onClick={() => onReject(draft)}
        >
          {rejecting ? "正在放弃…" : "放弃草稿"}
        </Button>
        <Button
          variant="primary"
          type="button"
          disabled={accepting || rejecting || draft.acceptBlocked}
          onClick={() => onAccept(draft)}
        >
          {accepting ? "正在采用…" : "采用草稿"}
        </Button>
      </div>
    </section>
  );
}

export function aiExperienceState({
  selection,
  readiness,
  readinessLoading,
  readinessError,
  generating,
  cancelling,
  draft,
  cancelled,
}: {
  selection?: TextModelSelection;
  readiness?: TextRuntimeDiagnostics;
  readinessLoading: boolean;
  readinessError: boolean;
  generating: boolean;
  cancelling: boolean;
  draft?: AiDraft;
  cancelled: boolean;
}): AiExperienceState {
  if (cancelling) return "cancelling";
  if (generating) return "generating";
  if (draft?.status === "failed") return "failed";
  if (draft?.status === "ready") return "result-ready";
  if (cancelled) return "cancelled";
  if (!selection) return "no-model";
  if (readinessLoading) return "loading";
  if (readinessError || !readiness) return "unavailable";
  if (readiness.state === "NOT_CONFIGURED") return "unconfigured";
  if (readiness.state !== "READY") return "unavailable";
  return "ready";
}
const stateWording: Record<AiExperienceState, string> = {
  "no-model": "尚未选择模型",
  loading: "正在检查模型状态…",
  unconfigured: "尚未配置",
  unavailable: "暂不可用",
  ready: "可以开始生成",
  generating: "生成中…",
  cancelling: "正在停止…",
  failed: "生成失败",
  "result-ready": "生成结果待确认",
  cancelled: "已停止生成",
};

export function AiWritingPanel({
  novelId,
  chapterNumber,
  contextTarget = "local",
  draft,
  variants = [],
  activeVariant = 0,
  generating = false,
  cancelling = false,
  cancelled = false,
  recovering = false,
  error,
  accepting = false,
  rejecting = false,
  models = [],
  selection = null,
  packagedMode = false,
  credentialConfigured = false,
  onCredentialRefresh = async () => false,
  vaultMode = false,
  onSaveVault,
  onDeleteVault,
  onTestVault,
  onSelectionChange = () => {},
  readiness,
  readinessLoading = false,
  readinessError = false,
  onOpenDiagnostics,
  onGenerate,
  onGenerateVariants,
  onSelectVariant,
  onCancel,
  onAccept,
  onReject,
  onRetry,
  onResolveConflict,
}: {
  novelId?: string;
  chapterNumber?: number;
  contextTarget?: ContextPreviewTarget;
  draft?: AiDraft;
  variants?: AiVariantDraft[];
  activeVariant?: number;
  generating?: boolean;
  cancelling?: boolean;
  cancelled?: boolean;
  recovering?: boolean;
  error?: string | null;
  accepting?: boolean;
  rejecting?: boolean;
  models?: TextModel[];
  selection?: TextModelSelection;
  packagedMode?: boolean;
  credentialConfigured?: boolean;
  onCredentialRefresh?: () => Promise<boolean>;
  vaultMode?: boolean;
  onSaveVault?: (value: string) => Promise<boolean>;
  onDeleteVault?: () => Promise<boolean>;
  onTestVault?: () => Promise<boolean>;
  onSelectionChange?: (selection: TextModelSelection) => void;
  readiness?: TextRuntimeDiagnostics;
  readinessLoading?: boolean;
  readinessError?: boolean;
  onOpenDiagnostics?: () => void;
  onGenerate: (
    operation: AiOperation,
    instruction: string,
    style: string,
  ) => Promise<void> | void;
  onGenerateVariants?: (
    operation: AiOperation,
    instruction: string,
    count: number,
    style: string,
  ) => Promise<void> | void;
  onSelectVariant?: (index: number) => void;
  onCancel?: () => Promise<void> | void;
  onAccept: (draft: AiDraft) => Promise<void> | void;
  onReject: (draft: AiDraft) => Promise<void> | void;
  onRetry?: (draft: AiDraft) => Promise<void> | void;
  onResolveConflict?: (draft: AiDraft) => Promise<void> | void;
}) {
  const [operation, setOperation] = useState<AiOperation>("continue"),
    [instruction, setInstruction] = useState(""),
    [style, setStyle] = useState(""),
    [variantCount, setVariantCount] = useState(1);
  const value = selection ? `${selection.providerId}:${selection.modelId}` : "";
  const state = aiExperienceState({
    selection: selection || undefined,
    readiness,
    readinessLoading,
    readinessError,
    generating,
    cancelling,
    draft,
    cancelled,
  });
  const canGenerate =
    state === "ready" || state === "failed" || state === "cancelled";
  return (
    <Panel className="novel-ai-panel" title="AI 写作助手">
      <div className="novel-tabs" role="tablist" aria-label="AI 写作方式">
        {(Object.keys(operationLabels) as AiOperation[]).map((value) => (
          <button
            key={value}
            role="tab"
            aria-selected={operation === value}
            disabled={generating || cancelling}
            onClick={() => setOperation(value)}
          >
            {operationLabels[value]}
          </button>
        ))}
      </div>
      <label>
        文本模型
        <select
          value={value}
          disabled={generating || cancelling}
          onChange={(event) => {
            const model = models.find(
              (item) =>
                `${item.provider_id}:${item.model_id}` === event.target.value,
            );
            onSelectionChange(
              model
                ? { providerId: model.provider_id, modelId: model.model_id }
                : null,
            );
          }}
        >
          <option value="">尚未选择文本模型</option>
          {models.map((model) => (
            <option
              key={`${model.provider_id}:${model.model_id}`}
              value={`${model.provider_id}:${model.model_id}`}
              disabled={!packagedMode && !model.available}
            >
              {model.display_name}
              {model.available || packagedMode ? "" : "（不可用）"}
            </option>
          ))}
        </select>
      </label>
      <section
        className={`novel-ai-status novel-ai-status--${state}`}
        aria-labelledby="ai-status-title"
      >
        <div>
          <strong id="ai-status-title">当前模型</strong>
          <Badge
            tone={
              state === "ready"
                ? "success"
                : state === "failed" || state === "unavailable"
                  ? "error"
                  : "warning"
            }
          >
            {stateWording[state]}
          </Badge>
        </div>
        <p role="status" aria-live="polite">
          {selection
            ? models.find(
                (model) =>
                  model.provider_id === selection.providerId &&
                  model.model_id === selection.modelId,
              )?.display_name || "已选择文本模型"
            : "选择模型后可查看是否能够开始写作。"}
        </p>
        {state === "unconfigured" && <p>配置完成后即可使用 AI 写作。</p>}
        {state === "unavailable" && (
          <p>模型暂时无法使用，请稍后重试或前往“模型状态”查看详情。</p>
        )}
        {state === "failed" && (
          <p role="alert">{generationFailureMessage(error)}</p>
        )}
        {onOpenDiagnostics && selection && (
          <Button type="button" onClick={onOpenDiagnostics}>
            查看模型状态
          </Button>
        )}
      </section>
      {selection?.providerId === "deepseek" && (
        <DeepSeekCredentialControl
          configured={credentialConfigured}
          onRefresh={onCredentialRefresh}
          vaultMode={vaultMode}
          onSaveVault={onSaveVault}
          onDeleteVault={onDeleteVault}
          onTestVault={onTestVault}
        />
      )}
      <div className="novel-tabs" role="group" aria-label="候选方案数量">
        <span>候选方案</span>
        {[1, 2, 3].map((count) => (
          <button
            key={count}
            type="button"
            aria-pressed={variantCount === count}
            disabled={generating || cancelling}
            onClick={() => setVariantCount(count)}
          >
            {count}
          </button>
        ))}
      </div>
      <label>
        附加要求（可选）
        <textarea
          value={instruction}
          disabled={generating || cancelling}
          onChange={(e) => setInstruction(e.target.value)}
          placeholder="例如：保持紧张节奏，突出人物犹豫。"
        />
      </label>
      <label>
        写作风格（可选）
        <input value={style} maxLength={120} disabled={generating || cancelling} onChange={(e) => setStyle(e.target.value)} placeholder="例如：克制、冷峻、短句为主" />
      </label>
      <div className="style-presets" aria-label="写作风格预设">
        {stylePresets.map((preset) => <button key={preset} type="button" disabled={generating || cancelling} aria-pressed={style === preset} onClick={() => setStyle(preset)}>{preset}</button>)}
      </div>
      {novelId && chapterNumber !== undefined && (
        <AiContextPreviewPanel
          novelId={novelId}
          chapterNumber={chapterNumber}
          operation={operation}
          instruction={instruction}
          defaultTarget={contextTarget}
          disabled={generating || cancelling}
        />
      )}
      <div className="novel-ai-actions">
        {generating || cancelling ? (
          <Button type="button" disabled={cancelling} onClick={onCancel}>
            {cancelling ? "正在停止…" : "停止生成"}
          </Button>
        ) : (
          <Button
            variant="primary"
            disabled={!canGenerate}
            onClick={() => {
              const requestInstruction = instruction.trim();
              return variantCount > 1 && onGenerateVariants
                ? onGenerateVariants(operation, requestInstruction, variantCount, style.trim())
                : onGenerate(operation, requestInstruction, style.trim());
            }}
          >{`生成${operationLabels[operation]}草稿`}</Button>
        )}
      </div>
      <GenerationWorkflowTimeline
        starting={generating && !draft && variants.length === 0}
        drafts={variants.length ? variants : draft ? [draft] : []}
        accepting={accepting}
        rejecting={rejecting}
        cancelled={cancelled}
        recovering={recovering}
        onRetry={variants.length > 1 ? onRetry : undefined}
      />
      {variants.length > 1 && (
        <div className="novel-tabs" role="tablist" aria-label="候选方案">
          {variants.map((variant, index) => (
            <button
              key={variant.id}
              role="tab"
              aria-selected={activeVariant === index}
              onClick={() => onSelectVariant?.(index)}
            >
              方案 {variant.variantIndex}
              {variant.status === "working"
                ? " · 生成中"
                : variant.status === "failed"
                  ? " · 失败"
                  : " · 可用"}
            </button>
          ))}
        </div>
      )}
      <AiDraftReview
        draft={variants[activeVariant] || draft}
        accepting={accepting}
        rejecting={rejecting}
        onAccept={onAccept}
        onReject={onReject}
        onRetry={onRetry}
        onResolveConflict={onResolveConflict}
      />
    </Panel>
  );
}
