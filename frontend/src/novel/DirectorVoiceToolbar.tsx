import { useEffect, useRef, useState } from "react";
import { Button } from "../ui/primitives";
import { api } from "../api";
import { buildVoiceManifest } from "./DirectorShotList";
import type { DirectorShot } from "./MultimodalDirectorWorkspace";
import { FOCUS_FAILED_TASKS_EVENT, publishTaskSummary } from "../ui/taskSummary";

export function DirectorVoiceToolbar({
  shots,
  batch,
  onBatch,
  novelId,
  onRetryFailed,
}: {
  shots: DirectorShot[];
  batch: any[];
  onBatch: (items: any[]) => void;
  novelId?: string;
  onRetryFailed?: () => void;
}) {
  const retryButton = useRef<HTMLButtonElement>(null);
  const [focusRequested, setFocusRequested] = useState(false);
  useEffect(() => { publishTaskSummary("audio", batch); }, [batch]);
  useEffect(() => { const listener = (event: Event) => { const detail = (event as CustomEvent).detail; if (detail?.source === "audio") { const target = detail.taskId ? batch.find((item) => String(item.id || item.task_id || item.shot_id) === String(detail.taskId)) : undefined; setFocusRequested(Boolean(target) || !detail.taskId); requestAnimationFrame(() => retryButton.current?.focus()); } }; window.addEventListener(FOCUS_FAILED_TASKS_EVENT, listener); return () => window.removeEventListener(FOCUS_FAILED_TASKS_EVENT, listener); }, [batch]);
  const run = async () =>
    onBatch(
      await api.synthesizeDirectorShots(shots, {
        provider_id: "openai",
        model_id: "gpt-4o-mini-tts",
        novel_id: novelId,
      }),
    );
  const exportManifest = (csv = false) => {
    const rows = buildVoiceManifest(shots, batch);
    const content = csv
      ? [
          "shot_id,dialogue,voice,emotion,status,audio_uri",
          ...rows.map((row) =>
            Object.values(row)
              .map((value) => `"${String(value).replace(/"/g, '""')}"`)
              .join(","),
          ),
        ].join("\n")
      : JSON.stringify(rows, null, 2);
    const blob = new Blob([content], {
      type: csv ? "text/csv" : "application/json",
    });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `director-voice-list.${csv ? "csv" : "json"}`;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <div className="multimodal-director__voice-toolbar">
      <Button
        onClick={run}
        disabled={
          !shots.some((shot) => (shot.dialogue || shot.subtitle) && shot.voice)
        }
      >
        生成全部可用配音
      </Button>
      {batch.some((item) => item.status === "failed") && (
        <Button ref={retryButton} variant="ghost" onClick={onRetryFailed}>
          重试失败配音
        </Button>
      )}
      <Button variant="ghost" onClick={() => exportManifest(false)}>
        导出配音 JSON
      </Button>
      <Button variant="ghost" onClick={() => exportManifest(true)}>
        导出配音 CSV
      </Button>
      {batch.length > 0 && (
        <small>
          成功 {batch.filter((item) => item.status === "succeeded").length} ·
          跳过 {batch.filter((item) => item.status === "skipped").length} · 失败{" "}
          {batch.filter((item) => item.status === "failed").length}
        </small>
      )}
      {focusRequested && <small role="status">已定位到失败配音，可直接重试。</small>}
    </div>
  );
}
