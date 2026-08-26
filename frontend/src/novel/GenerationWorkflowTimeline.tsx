import { Check, Circle, LoaderCircle, RotateCcw, X } from "lucide-react";
import { Badge, Button, StatusMessage } from "../ui/primitives";
import type { AiDraft } from "./AiWritingPanel";
import "./GenerationWorkflowTimeline.css";

type TimelineState = "waiting" | "active" | "complete" | "failed" | "cancelled";

export type GenerationWorkflowTimelineProps = {
  starting?: boolean;
  drafts?: AiDraft[];
  accepting?: boolean;
  rejecting?: boolean;
  cancelled?: boolean;
  recovering?: boolean;
  onRetry?: (draft: AiDraft) => Promise<void> | void;
};

type TimelineStep = {
  id: "context" | "plan" | "generation" | "review";
  label: string;
  detail: string;
  state: TimelineState;
};

const stateLabels: Record<TimelineState, string> = {
  waiting: "等待",
  active: "进行中",
  complete: "完成",
  failed: "失败",
  cancelled: "已停止",
};

function timelineSteps({
  starting = false,
  drafts = [],
  accepting = false,
  rejecting = false,
  cancelled = false,
}: GenerationWorkflowTimelineProps): TimelineStep[] {
  const hasJob = cancelled || drafts.some((draft) => draft.tracked !== false);
  const working = drafts.filter((draft) => draft.status === "working").length;
  const ready = drafts.filter((draft) => draft.status === "ready").length;
  const failed = drafts.filter((draft) => draft.status === "failed").length;
  const generationState: TimelineState = cancelled
    ? "cancelled"
    : starting || working
      ? "active"
      : failed && !ready
        ? "failed"
        : ready
          ? "complete"
          : "waiting";
  const reviewState: TimelineState = accepting || rejecting
    ? "active"
    : ready
      ? "active"
      : cancelled
        ? "cancelled"
        : "waiting";

  return [
    {
      id: "context",
      label: "读取创作上下文",
      detail: hasJob ? "生成任务已接收本次上下文" : starting ? "正在提交本次上下文" : "开始生成后读取",
      state: hasJob ? "complete" : starting ? "active" : "waiting",
    },
    {
      id: "plan",
      label: "建立生成计划",
      detail: hasJob ? "服务已创建可追踪任务" : "等待任务创建",
      state: hasJob ? "complete" : "waiting",
    },
    {
      id: "generation",
      label: "生成章节草稿",
      detail: working
        ? drafts.length > 1 ? `${working} 个方案生成中` : "草稿生成中"
        : ready && failed ? `${ready} 个可审核，${failed} 个失败`
          : ready ? drafts.length > 1 ? `${ready} 个方案已生成` : "草稿已生成"
            : failed ? `${failed} 个任务失败` : cancelled ? "任务已由用户停止" : "等待生成",
      state: generationState,
    },
    {
      id: "review",
      label: "作者审核",
      detail: accepting ? "正在采用并进入版本保存" : rejecting ? "正在放弃草稿" : ready ? "比较草稿后采用或放弃" : "等待可审核草稿",
      state: reviewState,
    },
  ];
}

function StepIcon({ state }: { state: TimelineState }) {
  if (state === "complete") return <Check aria-hidden="true" />;
  if (state === "active") return <LoaderCircle aria-hidden="true" />;
  if (state === "failed" || state === "cancelled") return <X aria-hidden="true" />;
  return <Circle aria-hidden="true" />;
}

export function GenerationWorkflowTimeline(props: GenerationWorkflowTimelineProps) {
  const drafts = props.drafts || [];
  const failedDrafts = drafts.filter((draft) => draft.status === "failed");
  const steps = timelineSteps(props);

  return (
    <section className="generation-workflow" aria-labelledby="generation-workflow-title">
      <header className="generation-workflow__header">
        <div>
          <strong id="generation-workflow-title">生成流程</strong>
          <span>上下文 → 计划 → 草稿 → 审核</span>
        </div>
        {props.recovering && <Badge tone="info">已恢复任务</Badge>}
      </header>
      <ol className="generation-workflow__steps">
        {steps.map((step) => (
          <li key={step.id} className={`generation-workflow__step is-${step.state}`} aria-current={step.state === "active" ? "step" : undefined}>
            <span className="generation-workflow__marker"><StepIcon state={step.state} /></span>
            <span className="generation-workflow__copy">
              <span><strong>{step.label}</strong><Badge tone={step.state === "complete" ? "success" : step.state === "failed" ? "error" : step.state === "active" ? "info" : "neutral"}>{stateLabels[step.state]}</Badge></span>
              <small>{step.detail}</small>
            </span>
          </li>
        ))}
      </ol>
      {failedDrafts.length > 0 && props.onRetry && (
        <StatusMessage tone="error">
          <div className="generation-workflow__failure">
            <span>{failedDrafts[0].error || "生成任务失败，请重试。"}</span>
            {failedDrafts.map((draft) => (
              <Button key={draft.id} type="button" variant="secondary" onClick={() => props.onRetry?.(draft)}>
                <RotateCcw aria-hidden="true" />
                {drafts.length > 1 ? `重试方案 ${"variantIndex" in draft ? (draft as AiDraft & { variantIndex: number }).variantIndex : ""}`.trim() : "重试生成"}
              </Button>
            ))}
          </div>
        </StatusMessage>
      )}
    </section>
  );
}

export { timelineSteps };
