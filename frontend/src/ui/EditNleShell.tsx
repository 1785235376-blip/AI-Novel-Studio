/**
 * [HERMIA-FE-20261022 W-P0-06 / W-UX-05] CapCut/PR/AE-density EDIT workspace shell.
 * Composes existing nle/** panels; does NOT rewrite timeline engine internals.
 * Demo sequence is local UI state only (read-only shell when no production client).
 * W-UX-05: dual monitors / multi-track / zoom / media pool / inspector polish — small cut.
 */
import {useCallback, useMemo, useState} from 'react';
import {Button} from './primitives';
import {TimelineWorkspacePanel} from '../nle/TimelineWorkspacePanel';
import {ClipInspectorPanel} from '../nle/ClipInspectorPanel';
import {ExportDeliveryPanel} from '../nle/ExportDeliveryPanel';
import {checkedTimeline} from '../creative/studioTimelineTypes';
import {NLE_VIEW_SCALE_MAX, NLE_VIEW_SCALE_MIN, timelineUsage, timebaseOf, zoomWindow} from '../nle/timelineOps';
import './EditNleShell.css';

const DIGEST = 'a'.repeat(64);

export function demoEditTimeline(novelId: string) {
  return checkedTimeline({
    schema_version: 2,
    duration_ms: 20_000,
    width: 1920,
    height: 1080,
    fps: 24,
    tracks: [
      {
        id: 'v1', kind: 'VIDEO', order: 0, role: 'PRIMARY', muted: false, gain_db: 0,
        clips: [
          {id: 'c-v1', source_snapshot: {id: 'asset-shot-a', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST},
            start_ms: 0, in_ms: 0, out_ms: 5000, x: 0, y: 0, width: 1920, height: 1080,
            speed_num: 1, speed_den: 1, opacity: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, include_audio: true},
          {id: 'c-v2', source_snapshot: {id: 'asset-shot-b', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST},
            start_ms: 5000, in_ms: 0, out_ms: 4000, x: 0, y: 0, width: 1920, height: 1080,
            speed_num: 1, speed_den: 1, opacity: 1, muted: false, gain_db: 0, fade_in_ms: 120, fade_out_ms: 0, include_audio: true},
        ],
      },
      {
        id: 'v2', kind: 'VIDEO', order: 1, role: 'OVERLAY', muted: false, gain_db: 0,
        clips: [
          {id: 'c-ov', source_snapshot: {id: 'asset-overlay', kind: 'ASSET', asset_kind: 'image', version: 1, digest: DIGEST},
            start_ms: 8000, in_ms: 0, out_ms: 2500, x: 64, y: 64, width: 480, height: 270,
            speed_num: 1, speed_den: 1, opacity: 0.92, muted: true, gain_db: 0, fade_in_ms: 0, fade_out_ms: 200, include_audio: false},
        ],
      },
      {
        id: 'a1', kind: 'AUDIO', order: 2, role: 'DIALOGUE', muted: false, gain_db: -2,
        clips: [
          {id: 'c-a1', source_snapshot: {id: 'asset-vo', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: DIGEST},
            start_ms: 0, in_ms: 0, out_ms: 9000, speed_num: 1, speed_den: 1, muted: false, gain_db: -2, fade_in_ms: 0, fade_out_ms: 80},
        ],
      },
      {
        id: 'a2', kind: 'AUDIO', order: 3, role: 'MUSIC', muted: false, gain_db: -12,
        clips: [
          {id: 'c-a2', source_snapshot: {id: 'asset-bgm', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: DIGEST},
            start_ms: 0, in_ms: 0, out_ms: 18000, speed_num: 1, speed_den: 1, muted: false, gain_db: -12, fade_in_ms: 400, fade_out_ms: 800},
        ],
      },
    ],
    captions: [
      {start_ms: 400, end_ms: 2200, text: '示例字幕 · 可在字幕轨审阅'},
      {start_ms: 5200, end_ms: 7800, text: '第二句 · 对齐画面'},
    ],
  });
}

const MEDIA_BIN = [
  {id: 'shot-a', kind: '视频', label: '镜头 A · 开场'},
  {id: 'shot-b', kind: '视频', label: '镜头 B · 对白'},
  {id: 'overlay', kind: '图片', label: '叠层 · 角标'},
  {id: 'vo', kind: '音频', label: '旁白轨'},
  {id: 'bgm', kind: '音频', label: '背景音乐'},
];

export function EditNleMediaRail({novelId}: {novelId: string}) {
  return (
    <nav className="edit-nle-rail" aria-label="剪辑媒体池" data-drag-semantics="reference">
      <div className="edit-nle-rail__eyebrow">媒体池</div>
      <strong>序列 · 演示</strong>
      <p className="edit-nle-rail__hint">拖入时间线＝引用资产，不复制源文件。完整可写路径在独立工作室「制作操作」。≠ VIDEO 假轨。</p>
      <ul className="edit-nle-rail__bin">
        {MEDIA_BIN.map(item => (
          <li key={item.id} draggable={false} data-media-bin={item.id} title="拖入＝引用（演示壳示意）">
            <span className="edit-nle-rail__kind">{item.kind}</span>
            <span>{item.label}</span>
            <small>{novelId.slice(0, 8)}…/{item.id}</small>
            <em className="edit-nle-rail__ref">引用</em>
          </li>
        ))}
      </ul>
      <div className="edit-nle-rail__future">
        <span>序列树</span>
        <small>主序列（演示）</small>
        <small>待导入 · 需项目素材（诚实空）</small>
      </div>
    </nav>
  );
}

export function EditNleInspector({
  novelId, timeline, selectedClipIds, playheadMs, editable,
}: {
  novelId: string;
  timeline: ReturnType<typeof demoEditTimeline>;
  selectedClipIds: string[];
  playheadMs: number;
  editable: boolean;
}) {
  const usage = timelineUsage(timeline);
  return (
    <div className="edit-nle-inspector" aria-label="片段检视">
      <header className="edit-nle-inspector__head">
        <strong>检视器</strong>
        <small>{selectedClipIds.length ? `已选 ${selectedClipIds.length}` : '未选片段 · 序列属性'}</small>
      </header>
      {selectedClipIds.length ? (
        <ClipInspectorPanel
          timeline={timeline}
          selectedClipIds={selectedClipIds}
          playheadMs={playheadMs}
          marks={{inMs: null, outMs: null}}
          editable={editable}
          onEdit={() => {}}
        />
      ) : (
        <section className="edit-nle-inspector__empty-cta" aria-label="序列下一步" data-honest-kind="empty_selection">
          <p>在时间线上点选片段以查看入出点、增益与链接。无选中时保留序列出口，避免空白占位。</p>
          <dl>
            <div><dt>项目</dt><dd>{novelId}</dd></div>
            <div><dt>时长</dt><dd>{timeline.duration_ms} ms · {timeline.fps} fps</dd></div>
            <div><dt>轨道 / 片段</dt><dd>{timeline.tracks.length} / {usage.clips}</dd></div>
            <div><dt>下一步</dt><dd>导入媒体 · 从视频送入 · 或导出成片</dd></div>
          </dl>
        </section>
      )}
      <ExportDeliveryPanel mediaKind="VIDEO" usage={usage} />
    </div>
  );
}

export function EditNleShell({
  novelId, timeline, playheadMs, onPlayhead, selectedClipIds, onSelectClips,
}: {
  novelId: string;
  timeline: ReturnType<typeof demoEditTimeline>;
  playheadMs: number;
  onPlayhead: (ms: number) => void;
  selectedClipIds: string[];
  onSelectClips: (ids: string[]) => void;
}) {
  const timebase = useMemo(() => timebaseOf(timeline), [timeline]);
  const usage = useMemo(() => timelineUsage(timeline), [timeline]);
  const [viewStartMs, setViewStartMs] = useState(0);
  const [viewScale, setViewScale] = useState(0.08);
  const [markInMs, setMarkInMs] = useState<number | null>(null);
  const [markOutMs, setMarkOutMs] = useState<number | null>(null);
  const [snap, setSnap] = useState(true);
  const setPlayheadMs = onPlayhead;
  const setSelectedClipIds = onSelectClips;
  const editable = false; // shell demo; mutate path = IndependentStudio

  const onView = useCallback((next: {startMs: number; scale: number}) => {
    setViewStartMs(next.startMs);
    setViewScale(next.scale);
  }, []);

  const zoom = (factor: number) => {
    const next = zoomWindow({startMs: viewStartMs, scale: viewScale}, factor, playheadMs, timebase);
    setViewStartMs(next.startMs);
    setViewScale(next.scale);
  };

  const scrub = (delta: number) => {
    setPlayheadMs(Math.max(0, Math.min(timebase.durationMs, playheadMs + delta)));
  };

  return (
    <div
      className="edit-nle-shell"
      aria-label="剪辑工作区 · 多轨时间线"
      data-edit-density="w-ux-05"
      data-nle-tracks={timeline.tracks.length}
      data-snap={snap ? 'on' : 'off'}
    >
      <div className="edit-nle-shell__preview" aria-label="监视器与工具条">
        <div className="edit-nle-shell__monitor edit-nle-shell__monitor--source" data-monitor="source">
          <span className="edit-nle-shell__monitor-label">源监视器</span>
          <strong>{selectedClipIds[0] || '—'}</strong>
          <small>选中片段 · 只读演示 · 双监视器</small>
        </div>
        <div className="edit-nle-shell__monitor" data-monitor="program">
          <span className="edit-nle-shell__monitor-label">节目监视器</span>
          <strong>{(playheadMs / 1000).toFixed(2)}s</strong>
          <small>{timeline.width}×{timeline.height} · {timeline.fps} fps · {usage.clips} 片段 · 演示序列（只读壳）</small>
        </div>
        <div className="edit-nle-shell__toolbar" role="toolbar" aria-label="剪辑工具条">
          <Button type="button" onClick={() => scrub(-1000)}>−1s</Button>
          <Button type="button" onClick={() => setPlayheadMs(0)}>⏹</Button>
          <Button type="button" onClick={() => scrub(40)}>▶ 帧</Button>
          <Button type="button" onClick={() => scrub(1000)}>+1s</Button>
          <span className="edit-nle-shell__sep" />
          <Button type="button" data-mark="in" onClick={() => setMarkInMs(playheadMs)} title="入点">I 入点</Button>
          <Button type="button" data-mark="out" onClick={() => setMarkOutMs(playheadMs)} title="出点">O 出点</Button>
          <Button type="button" aria-pressed={snap} data-snap-toggle="true" onClick={() => setSnap(v => !v)}>
            {snap ? '吸附开' : '吸附关'}
          </Button>
          <span className="edit-nle-shell__sep" />
          <Button type="button" disabled={viewScale <= NLE_VIEW_SCALE_MIN} onClick={() => zoom(0.8)}>缩小</Button>
          <Button type="button" disabled={viewScale >= NLE_VIEW_SCALE_MAX} onClick={() => zoom(1.25)}>放大</Button>
          <small>
            缩放 {(viewScale * 1000).toFixed(1)} px/s · 播放头 {playheadMs} ms
            {markInMs != null ? ` · In ${markInMs}` : ''}
            {markOutMs != null ? ` · Out ${markOutMs}` : ''}
            · 轨 {timeline.tracks.length}
          </small>
        </div>
      </div>
      <div className="edit-nle-shell__hero" aria-label="多轨时间线主表面" data-timeline-hero="true">
        <div className="edit-nle-shell__track-meta" aria-label="轨道摘要">
          <span>多轨 hero · {timeline.tracks.length} 轨 · {usage.clips} 片段</span>
          <small>V/A/字幕并行 · ≠ VIDEO 画布假轨 · 只读演示壳</small>
        </div>
        <TimelineWorkspacePanel
          projectId={novelId}
          identity={`edit-shell:${novelId}`}
          timeline={timeline}
          selectedClipIds={selectedClipIds}
          playheadMs={playheadMs}
          viewStartMs={viewStartMs}
          viewScale={viewScale}
          editable={editable}
          onSelectClips={setSelectedClipIds}
          onPlayhead={setPlayheadMs}
          onView={onView}
          onEdit={() => {}}
        />
      </div>
      <p className="edit-nle-shell__foot notice">
        [HERMIA-FE-20261022 W-UX-05] 剪辑 ≠ 视频画布。双监视器·入出点·吸附·缩放再抛光；复用 nle/** 不大拆。可写引擎仍走 IndependentStudio。不嵌入小说中区。
      </p>
    </div>
  );
}

