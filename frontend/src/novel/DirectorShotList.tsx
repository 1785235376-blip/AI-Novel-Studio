import { useEffect, useState } from "react";
import { DirectorShotCard } from "./DirectorShotCard";
import type { DirectorShot } from "./MultimodalDirectorWorkspace";
import { api } from "../api";
import { Button } from "../ui/primitives";
import { DirectorVoiceToolbar } from "./DirectorVoiceToolbar";
import { VideoTimeline } from "./VideoTimeline";
import { MotionTaskWorkspace } from "./MotionTaskWorkspace";

export function buildVoiceManifest(shots: DirectorShot[], batch: any[]) {
  return shots.map((shot) => {
    const result = batch.find((item) => item.shot_id === shot.shot_id);
    return {
      shot_id: shot.shot_id,
      dialogue: shot.dialogue || shot.subtitle || "",
      voice: shot.voice || "",
      emotion: shot.emotion || "neutral",
      status: result?.status || "not_requested",
      audio_uri: result?.result?.audio_uri || result?.audio_uri || "",
    };
  });
}
export function buildMotionBatchCsv(shots: DirectorShot[]) {
  const headers = [
    "shot_id",
    "name",
    "duration",
    "camera",
    "screenplay_id",
    "motion_task_id",
    "constraint_status",
  ];
  return [
    headers,
    ...shots.map((shot) =>
      headers.map((header) => String((shot as any)[header] || "")),
    ),
  ]
    .map((row) =>
      row.map((value) => `"${value.replace(/"/g, '""')}"`).join(","),
    )
    .join("\n");
}

export function DirectorShotList({
  shots,
  profiles,
  onChange,
  novelId,
  references = [],
}: {
  shots: DirectorShot[];
  profiles: { name: string }[];
  onChange: (shots: DirectorShot[]) => void;
  novelId?: string;
  references?: unknown[];
}) {
  const resultKey = `multimodal-voice-results:${novelId || "workspace"}`;
  const [batch, setBatch] = useState<any[]>(() => {
    try {
      const saved = localStorage.getItem(resultKey);
      return saved ? JSON.parse(saved) : [];
    } catch {
      return [];
    }
  });
  const [constraintStatuses, setConstraintStatuses] = useState<
    Record<string, string>
  >({});
  useEffect(() => {
    try {
      localStorage.setItem(
        resultKey,
        JSON.stringify(
          batch.map((item) => ({
            shot_id: item.shot_id,
            status: item.status,
            audio_uri: item.result?.audio_uri || item.audio_uri,
          })),
        ),
      );
    } catch {
      /* optional */
    }
  }, [batch, resultKey]);
  const voiceManifest = buildVoiceManifest(shots, batch);
  const exportManifest = (csv = false) => {
    const content = csv
      ? [
          "shot_id,dialogue,voice,emotion,status,audio_uri",
          ...voiceManifest.map((row) =>
            Object.values(row)
              .map((value) => `"${String(value).replace(/"/g, '""')}"`)
              .join(","),
          ),
        ].join("\n")
      : JSON.stringify(voiceManifest, null, 2);
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
  const retry = async (shot: any, index: number) => {
    if (!shot) return;
    setBatch((v) =>
      v.map((item) =>
        item.shot_id === shot.shot_id ? { ...item, status: "retrying" } : item,
      ),
    );
    try {
      const result = await api.synthesizeDirectorShotDialogue(shot, {
        provider_id: "openai",
        model_id: "gpt-4o-mini-tts",
        voice: shot.voice,
        emotion: shot.emotion || "neutral",
        novel_id: novelId,
      });
      setBatch((v) =>
        v.map((item) =>
          item.shot_id === shot.shot_id
            ? { shot_id: shot.shot_id, status: "succeeded", result }
            : item,
        ),
      );
    } catch {
      setBatch((v) =>
        v.map((item) =>
          item.shot_id === shot.shot_id ? { ...item, status: "failed" } : item,
        ),
      );
    }
  };
  const retryFailed = async () => {
    await Promise.all(
      batch
        .filter((item) => item.status === "failed")
        .map((item) =>
          retry(
            shots.find((shot) => shot.shot_id === item.shot_id),
            0,
          ),
        ),
    );
  };
  const saveConstraints = (shot: DirectorShot) =>
    api.saveDirectorShotConstraints(
      novelId!,
      shot.screenplay_id!,
      shot.motion_task_id!,
      shot,
      references,
    );
  const values = Object.values(constraintStatuses);
  const ready = shots.filter((shot, index) =>
    Boolean(
      novelId &&
      shot.screenplay_id &&
      shot.motion_task_id &&
      (constraintStatuses[shot.shot_id || String(index)] ||
        shot.constraint_status) === "confirmed",
    ),
  ).length;
  const incomplete = shots.length - ready;
  const screenplayIds = Array.from(
    new Set(shots.map((shot) => shot.screenplay_id).filter(Boolean)),
  );
  const [taskMessage, setTaskMessage] = useState("");
  useEffect(() => {
    if (!novelId || screenplayIds.length !== 1) return;
    api
      .screenplays(novelId)
      .then((items: any[]) => {
        const screenplay = items.find((item) => item.id === screenplayIds[0]);
        const tasks = screenplay?.motion_tasks || [];
        const next = shots.map((shot) => {
          if (shot.motion_task_id || !shot.shot_id) return shot;
          const matches = tasks.filter(
            (task: any) => task.transition_id === shot.shot_id,
          );
          if (matches.length === 1)
            return {
              ...shot,
              motion_task_id: matches[0].id,
              binding_source: "auto" as const,
            };
          if (matches.length > 1)
            return {
              ...shot,
              binding_candidates: matches.map((task: any) => task.id),
            };
          return shot;
        });
        if (
          next.some(
            (shot, index) =>
              JSON.stringify(shot) !== JSON.stringify(shots[index]),
          )
        )
          onChange(next);
      })
      .catch(() => {
        /* task matching is optional */
      });
  }, [novelId, screenplayIds.join("|")]);
  const createMissingTasks = async () => {
    if (!novelId || screenplayIds.length !== 1) {
      setTaskMessage("需要先为镜头绑定同一个剧本。");
      return;
    }
    try {
      await api.createMotionTasks(novelId, screenplayIds[0]!);
      window.dispatchEvent(
        new CustomEvent("motion-tasks-created", {
          detail: { novelId, screenplayId: screenplayIds[0] },
        }),
      );
      setTaskMessage("已创建该剧本缺失的视频任务，任务列表正在刷新。");
    } catch {
      setTaskMessage("创建视频任务失败，请检查剧本状态。");
    }
  };
  const batchItems = () =>
    shots.filter((shot, index) =>
      Boolean(
        novelId &&
        shot.screenplay_id &&
        shot.motion_task_id &&
        (constraintStatuses[shot.shot_id || String(index)] ||
          shot.constraint_status) === "confirmed",
      ),
    );
  const download = (content: string, type: string, name: string) => {
    const blob = new Blob([content], { type });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = name;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  const exportBatch = () =>
    download(
      JSON.stringify(
        {
          novel_id: novelId,
          exported_at: new Date().toISOString(),
          shots: batchItems(),
        },
        null,
        2,
      ),
      "application/json",
      "director-motion-batch.json",
    );
  const exportBatchCsv = () =>
    download(
      buildMotionBatchCsv(batchItems()),
      "text/csv",
      "director-motion-batch.csv",
    );
  const draftKey = `multimodal-motion-batch-draft:${novelId || "workspace"}`;
  const [draftMessage, setDraftMessage] = useState("");
  const [drafts, setDrafts] = useState<any[]>(() => {
    try {
      const value = JSON.parse(localStorage.getItem(draftKey) || "[]");
      return Array.isArray(value) ? value.slice(0, 5) : [];
    } catch {
      return [];
    }
  });
  const saveDraft = () => {
    try {
      const savedAt = new Date().toISOString();
      const next = [
        { saved_at: savedAt, shots: batchItems() },
        ...drafts,
      ].slice(0, 5);
      setDrafts(next);
      localStorage.setItem(draftKey, JSON.stringify(next));
      setDraftMessage(
        `批次草稿已保存 · ${new Date(savedAt).toLocaleTimeString()}`,
      );
    } catch {
      setDraftMessage("批次草稿保存失败");
    }
  };
  const loadDraft = (value = drafts[0]) => {
    if (value?.shots?.length) {
      onChange(value.shots);
      setDraftMessage(
        `已恢复批次草稿 · ${value.saved_at ? new Date(value.saved_at).toLocaleTimeString() : "未知时间"}`,
      );
    } else setDraftMessage("没有可恢复的批次草稿");
  };
  const removeDraft = (savedAt: string) => {
    const next = drafts.filter((draft) => draft.saved_at !== savedAt);
    setDrafts(next);
    try {
      localStorage.setItem(draftKey, JSON.stringify(next));
    } catch {
      /* optional */
    }
  };
  const clearDrafts = () => {
    if (!window.confirm("确定清空当前小说的全部批次草稿吗？")) return;
    setDrafts([]);
    try {
      localStorage.removeItem(draftKey);
    } catch {
      /* optional */
    }
  };
  const splitShot = (index:number, at:number) => { const shot=shots[index]; const first={...shot,shot_id:`${shot.shot_id||`shot-${index+1}`}-a`,name:`${shot.name} A`,duration:`${at}s`}; const remaining=Math.max(0,(parseFloat(shot.duration)||0)-at); const second={...shot,shot_id:`${shot.shot_id||`shot-${index+1}`}-b`,name:`${shot.name} B`,duration:`${remaining.toFixed(1)}s`,dialogue:''}; onChange([...shots.slice(0,index),first,second,...shots.slice(index+1)]); };
  const mergeShots = (index:number) => { const first=shots[index], second=shots[index+1]; if(!second)return; onChange([...shots.slice(0,index),{...first,duration:`${(parseFloat(first.duration)||0)+(parseFloat(second.duration)||0)}s`,action:[first.action,second.action].filter(Boolean).join('；'),dialogue:[first.dialogue,second.dialogue].filter(Boolean).join(' ')},...shots.slice(index+2)]); };
  return (
    <div className="multimodal-director__shot-list">
      <VideoTimeline shots={shots} onReorder={onChange} onDurationChange={(index, duration) => onChange(shots.map((shot, current) => current === index ? { ...shot, duration } : shot))} onTransitionChange={(index, transition) => onChange(shots.map((shot, current) => current === index ? { ...shot, transition } : shot))} onTransitionDurationChange={(index, duration) => onChange(shots.map((shot, current) => current === index ? { ...shot, transition_duration: duration } : shot))} onSubtitleChange={(index, subtitle) => onChange(shots.map((shot, current) => current === index ? { ...shot, subtitle } : shot))} onKeyframesChange={(index, keyframes) => onChange(shots.map((shot, current) => current === index ? { ...shot, keyframes } : shot))} onSplit={splitShot} onMerge={mergeShots} />
      <DirectorVoiceToolbar
        shots={shots}
        batch={batch}
        onBatch={setBatch}
        novelId={novelId}
        onRetryFailed={retryFailed}
      />
      {values.length > 0 && (
        <p className="novel-help" role="status">
          镜头约束：已确认 {values.filter((v) => v === "confirmed").length} ·
          待确认{" "}
          {
            values.filter((v) => v === "saving" || v === "pending_confirmation")
              .length
          }{" "}
          · 失败 {values.filter((v) => v === "failed").length}
        </p>
      )}
      <p className="novel-help" role="status">
        批次准备：可提交 {ready} · 待补齐 {incomplete}{" "}
        <Button variant="ghost" disabled={!ready} onClick={exportBatch}>
          导出 JSON
        </Button>
        <Button variant="ghost" disabled={!ready} onClick={exportBatchCsv}>
          导出 CSV
        </Button>
        <Button variant="ghost" disabled={!ready} onClick={saveDraft}>
          保存批次草稿
        </Button>
        <Button
          variant="ghost"
          disabled={!drafts.length}
          onClick={() => loadDraft()}
        >
          恢复最新草稿
        </Button>
        {drafts.length > 0 && (
          <Button variant="ghost" onClick={clearDrafts}>
            清空草稿
          </Button>
        )}
        <Button
          variant="ghost"
          disabled={!novelId || screenplayIds.length !== 1}
          onClick={createMissingTasks}
        >
          创建剧本缺失任务
        </Button>
      </p>
      {taskMessage && (
        <p className="novel-help" role="status">
          {taskMessage}
        </p>
      )}
      {novelId && screenplayIds.length === 1 && (
        <MotionTaskWorkspace
          novelId={novelId}
          screenplayId={screenplayIds[0]!}
          taskIds={shots
            .map((shot) => shot.motion_task_id)
            .filter((taskId): taskId is string => Boolean(taskId))}
        />
      )}
      {drafts.length > 0 && (
        <details>
          <summary>批次草稿（{drafts.length}）</summary>
          {drafts.map((draft, index) => (
            <p className="novel-help" key={draft.saved_at}>
              版本 {index + 1} · {new Date(draft.saved_at).toLocaleString()} ·{" "}
              {draft.shots?.length || 0} 个镜头{" "}
              <Button variant="ghost" onClick={() => loadDraft(draft)}>
                恢复
              </Button>
              <Button
                variant="ghost"
                onClick={() => removeDraft(draft.saved_at)}
              >
                删除
              </Button>
            </p>
          ))}
        </details>
      )}
      {draftMessage && (
        <p className="novel-help" role="status">
          {draftMessage}
        </p>
      )}
      {batch.length > 0 && (
        <div className="novel-help">
          {batch.map((item) => (
            <span key={item.shot_id}>
              {" "}
              {item.shot_id} · {item.status}
              {item.status === "failed" && (
                <Button
                  variant="ghost"
                  onClick={() =>
                    retry(
                      shots.find((shot) => shot.shot_id === item.shot_id),
                      0,
                    )
                  }
                >
                  重试
                </Button>
              )}{" "}
            </span>
          ))}
        </div>
      )}
      {shots.map((shot, index) => (
        <DirectorShotCard
          key={shot.shot_id || index}
          shot={shot}
          index={index}
          profiles={profiles}
          novelId={novelId}
          onSaveConstraints={saveConstraints}
          onConstraintStatus={(key, status) => {
            setConstraintStatuses((current) => ({ ...current, [key]: status }));
            onChange(
              shots.map((item, j) =>
                j === index
                  ? {
                      ...item,
                      constraint_status:
                        status as DirectorShot["constraint_status"],
                    }
                  : item,
              ),
            );
          }}
          onChange={(i, patch) =>
            onChange(
              shots.map((item, j) => (j === i ? { ...item, ...patch } : item)),
            )
          }
        />
      ))}
    </div>
  );
}
