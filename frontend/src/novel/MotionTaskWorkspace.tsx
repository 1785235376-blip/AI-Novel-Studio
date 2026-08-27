import { useCallback, useEffect, useMemo, useState } from "react";
import { api, type VideoProviderStatus } from "../api";
import { Badge, Button, EmptyState } from "../ui/primitives";
import type { VideoInspection } from "./VideoTaskInspector";
import "./MotionTaskWorkspace.css";

type MotionTask = {
  id: string;
  status: string;
  progress?: number;
  provider_id?: string;
  model_id?: string;
  start_frame?: string;
  end_frame?: string;
  remote_task_id?: string;
  error?: string;
  result?: { url?: string; asset_id?: string; provider_id?: string; model_id?: string };
  asset_import?: { import_status?: string; error?: string; asset?: { id?: string } };
};

export function sortVideoProviders(items: VideoProviderStatus[]) {
  return [...items].sort((left, right) =>
    Number(Boolean(right.available)) - Number(Boolean(left.available)) ||
    Number(Boolean(right.local)) - Number(Boolean(left.local)) ||
    String(left.display_name || left.id).localeCompare(String(right.display_name || right.id)),
  );
}

export function MotionTaskWorkspace({ novelId, screenplayId, taskIds, onInspect }: {
  novelId: string;
  screenplayId: string;
  taskIds?: string[];
  onInspect?: (inspection: VideoInspection) => void;
}) {
  const [tasks, setTasks] = useState<MotionTask[]>([]);
  const [providers, setProviders] = useState<VideoProviderStatus[]>([]);
  const [loading, setLoading] = useState(true);
  const [providerError, setProviderError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<Record<string, boolean>>({});
  const [frames, setFrames] = useState<Record<string, { start_frame: string; end_frame: string }>>({});

  const refresh = useCallback(async () => {
    const rows = await api.screenplays(novelId);
    const screenplay = rows.find((item: any) => String(item.id) === screenplayId);
    const next = (screenplay?.motion_tasks || []).filter((task: MotionTask) => !taskIds?.length || taskIds.includes(String(task.id)));
    setTasks(next);
    setFrames((current) => Object.fromEntries(next.map((task: MotionTask) => [task.id, current[task.id] || { start_frame: task.start_frame || "", end_frame: task.end_frame || "" }])));
    setLoading(false);
  }, [novelId, screenplayId, taskIds?.join("|")]);

  useEffect(() => { void refresh().catch(() => { setMessage("视频任务读取失败。"); setLoading(false); }); }, [refresh]);
  useEffect(() => {
    Promise.resolve().then(() => api.videoProviders()).then((data) => setProviders(sortVideoProviders(data.items || []))).catch(() => setProviderError("Provider 状态读取失败，暂时不能提交视频任务。"));
  }, []);
  useEffect(() => {
    const remote = tasks.filter((task) => ["PENDING", "RUNNING"].includes(String(task.status).toUpperCase()) && task.remote_task_id);
    if (!remote.length) return;
    const timer = window.setInterval(async () => {
      await Promise.allSettled(remote.map((task) => api.syncMotionTask(novelId, screenplayId, task.id)));
      await refresh().catch(() => undefined);
    }, 3000);
    return () => window.clearInterval(timer);
  }, [tasks, novelId, screenplayId, refresh]);

  const providerById = useMemo(() => new Map(providers.map((provider) => [provider.id, provider])), [providers]);
  const act = async (taskId: string, action: () => Promise<unknown>, success: string) => {
    setBusy((current) => ({ ...current, [taskId]: true })); setMessage("");
    try { await action(); setMessage(success); await refresh(); }
    catch { setMessage("操作失败，任务状态未被伪造，请检查 Provider 与任务错误信息。"); }
    finally { setBusy((current) => ({ ...current, [taskId]: false })); }
  };
  const importAsset = (task: MotionTask) => act(task.id, async () => {
    const status = task.asset_import?.import_status;
    if (!status || status === "READY_TO_IMPORT" || status === "NOT_REQUESTED") await api.importMotionAsset(novelId, screenplayId, task.id);
    await api.downloadMotionAsset(novelId, screenplayId, task.id);
  }, "视频已下载并写入当前项目资产库。");

  if (loading) return <p className="novel-help">正在读取真实视频任务...</p>;
  if (!tasks.length) return <EmptyState title="暂无视频任务" detail="先批准转场并创建 Motion Task，再从这里提交生成。" />;
  return <section className="motion-runtime" aria-label="视频生成任务">
    <header><strong>视频生成运行时</strong><Button variant="ghost" onClick={() => void refresh()}>刷新</Button></header>
    {providerError && <p role="alert">{providerError}</p>}
    {message && <p role="status">{message}</p>}
    {tasks.map((task) => {
      const status = String(task.status || "PENDING").toUpperCase();
      const provider = providerById.get(String(task.provider_id || ""));
      const draft = frames[task.id] || { start_frame: "", end_frame: "" };
      const ready = Boolean(provider?.available && draft.start_frame && draft.end_frame);
      return <article key={task.id} className="motion-runtime__task">
        <header><strong>任务 {task.id}</strong><Badge>{status}</Badge></header>
        <label>视频 Provider
          <select disabled={busy[task.id] || ["RUNNING", "SUCCEEDED"].includes(status)} value={task.provider_id || ""} onChange={(event) => {
            const selected = providerById.get(event.target.value); if (!selected?.available) return;
            void act(task.id, () => api.updateMotionProvider(novelId, screenplayId, task.id, selected.id, selected.model || task.model_id || ""), "Provider 已更新。");
          }}>
            <option value="">请选择可用 Provider</option>
            {providers.map((item) => <option key={item.id} value={item.id} disabled={!item.available}>{item.local ? "本地 · " : "云端 · "}{item.display_name || item.id}{item.available ? "" : "（不可用）"}</option>)}
          </select>
        </label>
        {!provider?.available && <p role="alert">{task.error === "VIDEO_PROVIDER_NOT_CONFIGURED" ? "VIDEO_PROVIDER_NOT_CONFIGURED · 未配置视频 Provider，任务保持 PENDING，不会出现 SUCCEEDED 或 placeholder://video/*。" : "当前 Provider 未配置或不可达，执行已禁用。请先在 AI 主控的 Provider 设置中完成配置。"}</p>}
        <div className="novel-split-fields">
          <label>起始帧 URL<input value={draft.start_frame} onChange={(event) => setFrames((current) => ({ ...current, [task.id]: { ...draft, start_frame: event.target.value } }))} /></label>
          <label>结束帧 URL<input value={draft.end_frame} onChange={(event) => setFrames((current) => ({ ...current, [task.id]: { ...draft, end_frame: event.target.value } }))} /></label>
        </div>
        <Button variant="ghost" disabled={busy[task.id] || status === "RUNNING"} onClick={() => void act(task.id, () => api.updateMotionFrames(novelId, screenplayId, task.id, draft), "首尾帧已保存。")}>保存首尾帧</Button>
        {status === "PENDING" && <Button variant="primary" disabled={busy[task.id] || !ready || Boolean(providerError)} onClick={() => void act(task.id, () => api.executeMotionTask(novelId, screenplayId, task.id), "任务已真实提交，正在等待 Provider 返回。")}>执行生成</Button>}
        {["PENDING", "RUNNING"].includes(status) && <Button variant="ghost" disabled={busy[task.id]} onClick={() => void act(task.id, () => api.cancelMotionTask(novelId, screenplayId, task.id), "取消请求已确认。")}>取消</Button>}
        {status === "FAILED" && <Button variant="primary" disabled={busy[task.id] || !provider?.available} onClick={() => void act(task.id, () => api.retryMotionTask(novelId, screenplayId, task.id), "任务已进入待重试状态。")}>重试</Button>}
        {task.remote_task_id && ["PENDING", "RUNNING"].includes(status) && <Button variant="ghost" disabled={busy[task.id]} onClick={() => void act(task.id, () => api.syncMotionTask(novelId, screenplayId, task.id), "已同步 Provider 状态。")}>立即同步</Button>}
        <progress aria-label={`任务 ${task.id} 进度`} max={100} value={Math.max(0, Math.min(100, Number(task.progress || 0)))} />
        <small>{Math.max(0, Math.min(100, Number(task.progress || 0)))}% · {task.model_id || "未选择模型"}</small>
        {task.error && task.error !== "VIDEO_PROVIDER_NOT_CONFIGURED" && <p role="alert">{task.error}</p>}
        {task.result?.url && !String(task.result.url).toLowerCase().startsWith("placeholder://") ? <video className="motion-runtime__video" controls src={task.result.url} aria-label={`任务 ${task.id} 视频结果`} /> : <p className="novel-help">尚无真实视频结果。</p>}
        {status === "SUCCEEDED" && task.result?.url && <Button variant="primary" disabled={busy[task.id] || task.asset_import?.import_status === "COMPLETED"} onClick={() => void importAsset(task)}>{task.asset_import?.import_status === "COMPLETED" ? "已进入资产库" : "下载并导入资产库"}</Button>}
        <small>资产导入：{task.asset_import?.import_status || "NOT_REQUESTED"}{task.asset_import?.asset?.id ? ` · ${task.asset_import.asset.id}` : ""}</small>
        <Button variant="ghost" onClick={() => {
          const detail = { novelId, screenplay_id: screenplayId, motion_task_id: task.id };
          localStorage.setItem(`multimodal-selected-motion:${novelId}`, JSON.stringify(detail));
          window.dispatchEvent(new CustomEvent("multimodal-motion-binding", { detail }));
          setMessage(`已选择任务 ${task.id}，请在目标镜头上确认绑定。`);
        }}>选择用于镜头绑定</Button>
        {onInspect && <Button variant="ghost" onClick={() => onInspect({ id: task.id, status, screenplayId, providerId: task.provider_id, modelId: task.model_id, progress: task.progress, startFrame: task.start_frame, endFrame: task.end_frame, resultUrl: task.result?.url, assetId: task.result?.asset_id, error: task.error })}>检查详情</Button>}
      </article>;
    })}
  </section>;
}
