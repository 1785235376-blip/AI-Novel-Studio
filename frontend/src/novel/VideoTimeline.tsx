import type { DirectorShot } from "./MultimodalDirectorWorkspace";
import { Button } from "../ui/primitives";
import "./VideoTimeline.css";
export function parseShotDuration(value: string) {
  const match = String(value || "").match(/([\d.]+)/);
  return match ? Number(match[1]) || 0 : 0;
}
export function parseKeyframeMarkers(value: string, duration: number) {
  return Array.from(new Set(value.split(",").map((part) => Number(part.trim())).filter((part) => Number.isFinite(part) && part >= 0 && part <= duration))).sort((a, b) => a - b).map((part) => String(part));
}
export function getTransitionStatus(shot: DirectorShot) {
  const transition = shot.transition || "CUT";
  if (transition === "CUT") return "直接剪切";
  if (!shot.transition_duration || parseShotDuration(shot.transition_duration) <= 0) return "参数不完整";
  if (shot.motion_task_id) return "等待 Provider 任务";
  return "已配置参数";
}
export function buildVideoTimeline(shots: DirectorShot[]) {
  let cursor = 0;
  return shots.map((shot, index) => {
    const shotDuration = parseShotDuration(shot.duration);
    const transitionDuration = parseShotDuration(shot.transition_duration || "");
    const duration = shotDuration + transitionDuration;
    const item = {
      shot,
      index,
      start: cursor,
      end: cursor + duration,
      duration,
      shotDuration,
      transitionDuration,
    };
    cursor += duration;
    return item;
  });
}
export function buildTimelineTracks(shots: DirectorShot[]) {
  return buildVideoTimeline(shots).map((item) => ({
    ...item,
    subtitle: item.shot.subtitle || item.shot.dialogue || "",
    audio: [item.shot.voice, item.shot.ambience, item.shot.sound_effect, item.shot.music]
      .filter(Boolean)
      .join(" / "),
    keyframes: item.shot.keyframes || [],
  }));
}
export function buildTimelineExport(shots: DirectorShot[]) {
  return buildTimelineTracks(shots).map((item) => ({
    shot_id: item.shot.shot_id || `shot-${item.index + 1}`,
    name: item.shot.name,
    start: Number(item.start.toFixed(3)),
    end: Number(item.end.toFixed(3)),
    duration: Number(item.duration.toFixed(3)),
    shot_duration: Number(item.shotDuration.toFixed(3)),
    transition: item.shot.transition || "CUT",
    transition_duration: Number(item.transitionDuration.toFixed(3)),
    subtitle: item.subtitle,
    audio: item.audio,
    keyframes: item.keyframes,
  }));
}
export function buildEdlExport(shots: DirectorShot[]) {
  return buildTimelineExport(shots).map((item, index) => `${String(index + 1).padStart(3, "0")}  AX       V     C        ${item.start.toFixed(3)} ${item.end.toFixed(3)} ${item.start.toFixed(3)} ${item.end.toFixed(3)}\n* FROM CLIP NAME: ${item.name}\n* TRANSITION: ${item.transition}${item.transition_duration ? ` ${item.transition_duration}s` : ""}`).join("\n");
}
export function VideoTimeline({
  shots,
  onReorder,
  onDurationChange,
  onSplit,
  onMerge,
  onDuplicate,
  onDelete,
  onTransitionChange,
  onTransitionDurationChange,
  onSubtitleChange,
  onKeyframesChange,
}: {
  shots: DirectorShot[];
  onReorder?: (shots: DirectorShot[]) => void;
  onDurationChange?: (index: number, duration: string) => void;
  onSplit?: (index: number, at: number) => void;
  onMerge?: (index: number) => void;
  onDuplicate?: (index: number) => void;
  onDelete?: (index: number) => void;
  onTransitionChange?: (index: number, transition: string) => void;
  onTransitionDurationChange?: (index: number, duration: string) => void;
  onSubtitleChange?: (index: number, subtitle: string) => void;
  onKeyframesChange?: (index: number, keyframes: string[]) => void;
}) {
  const items = buildVideoTimeline(shots);
  const tracks = buildTimelineTracks(shots);
  const total = items.at(-1)?.end || 0;
  const move = (index: number, delta: number) => {
    if (!onReorder) return;
    const target = index + delta;
    if (target < 0 || target >= shots.length) return;
    const next = [...shots];
    [next[index], next[target]] = [next[target], next[index]];
    onReorder(next);
  };
  const download = (content: string, filename: string, type: string) => {
    const url = URL.createObjectURL(new Blob([content], { type }));
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = filename;
    anchor.click();
    URL.revokeObjectURL(url);
  };
  return (
    <section className="video-timeline" aria-label="视频时间线">
      <div className="video-timeline__header"><div><strong>视频时间线</strong><p>总时长：{total.toFixed(1)} 秒 · {items.length} 个镜头</p></div><div className="video-timeline__exports">
        <Button variant="ghost" aria-label="导出时间线 JSON" onClick={() => download(JSON.stringify(buildTimelineExport(shots), null, 2), "video-timeline.json", "application/json")}>导出 JSON</Button>
        <Button variant="ghost" aria-label="导出时间线 EDL" onClick={() => download(buildEdlExport(shots), "video-timeline.edl", "text/plain")}>导出 EDL</Button>
      </div></div>
      <div className="video-timeline__track video-timeline__track--subtitles" aria-label="字幕轨">
        <small>字幕 / 对白轨</small>
        {tracks.map((item) => <div key={`subtitle-${item.shot.shot_id || item.index}`} style={{ minHeight: 18, width: total ? `${Math.max(4, item.duration / total * 100)}%` : "4%", background: item.subtitle ? "var(--color-info, #38bdf8)" : "var(--color-muted, #cbd5e1)", padding: "2px 4px", overflow: "hidden", whiteSpace: "nowrap" }} aria-label={`${item.shot.name} 字幕 ${item.subtitle ? "已设置" : "未设置"}`}>{item.subtitle || "未设置"}</div>)}
      </div>
      <div className="video-timeline__track video-timeline__track--audio" aria-label="音频轨">
        <small>音频轨</small>
        {tracks.map((item) => <div key={`audio-${item.shot.shot_id || item.index}`} style={{ minHeight: 18, width: total ? `${Math.max(4, item.duration / total * 100)}%` : "4%", background: item.audio ? "var(--color-success, #34d399)" : "var(--color-muted, #cbd5e1)", padding: "2px 4px", overflow: "hidden", whiteSpace: "nowrap" }} aria-label={`${item.shot.name} 音频 ${item.audio ? "已设置" : "未设置"}`}>{item.audio || "未设置"}</div>)}
      </div>
      {items.map((item) => (
        <div
          key={item.shot.shot_id || item.index}
          style={{ display: "grid", gap: 4, marginBottom: 6 }}
        >
          <div
            style={{
              position: "relative",
              height: 8,
              width: total
                ? `${Math.max(4, (item.duration / total) * 100)}%`
                : "4%",
              background: "var(--color-accent, #64748b)",
              borderRadius: 2,
            }}
            aria-label={`${item.shot.name} 时长 ${item.duration} 秒`}
          >
            {(item.shot.keyframes || []).map((marker, markerIndex) => {
              const point = Number(marker);
              if (!Number.isFinite(point) || item.shotDuration <= 0 || point > item.shotDuration) return null;
              return <span key={`${marker}-${markerIndex}`} aria-label={`${item.shot.name} 关键帧 ${marker} 秒`} style={{ position: "absolute", left: `${(point / item.shotDuration) * 100}%`, top: -3, width: 2, height: 14, background: "var(--color-warning, #f59e0b)" }} />;
            })}
          </div>
          <span>
            {item.start.toFixed(1)}s - {item.end.toFixed(1)}s · {item.shot.name}{" "}
            · {item.shot.camera || "未设置机位"}{" "}
            <input aria-label={`镜头 ${item.shot.name} 时长`} type="number" min="0" step="0.1" value={item.shotDuration} onChange={(event) => onDurationChange?.(item.index, `${event.target.value}s`)} />
            <select aria-label={`镜头 ${item.shot.name} 转场`} value={item.shot.transition || "CUT"} onChange={(event) => onTransitionChange?.(item.index, event.target.value)}><option>CUT</option><option>DISSOLVE</option><option>WIPE</option><option>FADE</option></select>
            <input aria-label={`镜头 ${item.shot.name} 转场时长`} type="number" min="0" step="0.1" value={parseShotDuration(item.shot.transition_duration || "")} onChange={(event) => onTransitionDurationChange?.(item.index, `${event.target.value}s`)} />
            <small aria-label={`${item.shot.name} 转场状态`}>{getTransitionStatus(item.shot)}</small>
            <input aria-label={`镜头 ${item.shot.name} 字幕`} type="text" value={item.shot.subtitle || item.shot.dialogue || ""} placeholder="字幕/对白" onChange={(event) => onSubtitleChange?.(item.index, event.target.value)} />
            <input aria-label={`镜头 ${item.shot.name} 关键帧`} type="text" value={(item.shot.keyframes || []).join(", ")} placeholder="关键帧秒数，如 0.5, 1.2" onChange={(event) => onKeyframesChange?.(item.index, parseKeyframeMarkers(event.target.value, item.shotDuration))} />
            <small>{(item.shot.keyframes || []).length} 个关键帧</small>
            <small>占用 {item.duration.toFixed(1)}s（镜头 {item.shotDuration.toFixed(1)}s + 转场 {item.transitionDuration.toFixed(1)}s）</small>
            <Button variant="ghost" disabled={item.shotDuration <= 0.2} aria-label={`拆分镜头 ${item.shot.name}`} onClick={() => onSplit?.(item.index, item.shotDuration / 2)}>拆分</Button>
            <Button variant="ghost" disabled={item.index === shots.length - 1} aria-label={`合并镜头 ${item.shot.name}`} onClick={() => onMerge?.(item.index)}>合并下一镜头</Button>
            <Button variant="ghost" aria-label={`复制镜头 ${item.shot.name}`} onClick={() => onDuplicate?.(item.index)}>复制</Button>
            <Button variant="ghost" disabled={shots.length <= 1} aria-label={`删除镜头 ${item.shot.name}`} onClick={() => onDelete?.(item.index)}>删除</Button>
            <Button
              variant="ghost"
              disabled={item.index === 0}
              aria-label={`镜头 ${item.shot.name} 上移`}
              onClick={() => move(item.index, -1)}
            >
              上移
            </Button>
            <Button
              variant="ghost"
              disabled={item.index === shots.length - 1}
              aria-label={`镜头 ${item.shot.name} 下移`}
              onClick={() => move(item.index, 1)}
            >
              下移
            </Button>
          </span>
        </div>
      ))}
    </section>
  );
}
