/**
 * UX-06 多轨剪辑、预览与交付操作的**呈现层**类型。
 *
 * 时间线 / 轨道 / 片段 / 字幕的每一个领域类型都从唯一 owner
 * `frontend/src/creative/studioTimelineTypes.ts` 派生；本文件不新增持久化字段、
 * 不改变已保存的时间线契约，也不建立第二套时间线引擎。
 *
 * 下面的冻结上限字面量是原 owner 的事实（只读引用），仅用于"在触界之前"提示用户；
 * 本模块**不提高任何上限**。来源逐条标注：
 *   - `app/services/studio_timeline_render.py` 的 `MAX_DURATION_MS` / `MAX_CLIPS` /
 *     `MAX_SOURCE_BYTES` / `MAX_CAPTION_CHARACTERS` / `RENDER_TIMEOUT_SECONDS`
 *     与 `render_studio_timeline` 的单素材 `max_bytes` 上限；
 *   - `app/services/studio_timeline_schema.py` 的轨道、分量、尺寸、帧率、字幕上限；
 *   - `app/services/studio_timeline_subtitles.py` 的 `MAX_SIDECAR_BYTES`；
 *   - `app/services/studio_timeline_edit.py` 的每批操作数与字节上限。
 */
import { TIMELINE_LIMITS } from '../creative/studioTimelineTypes';
import type {
  StudioTimeline, StudioTimelineCaption, StudioTimelineClip, StudioTimelineSource,
  StudioTimelineTrack, StudioTimelineTransition,
} from '../creative/studioTimelineTypes';

export type { StudioTimeline, StudioTimelineCaption, StudioTimelineClip, StudioTimelineSource, StudioTimelineTrack };

/** 原 owner 的时间基数：整数毫秒 + 整数帧率。本面只读，不改变它。 */
export type NleTimebase = { durationMs: number; fps: number; mediaKind?: never } | { durationMs: number; mediaKind: 'AUDIO'; fps?: never };

/**
 * 原 owner 的上限（冻结字面量）。`frontend/src/creative/studioTimelineTypes.ts` 的
 * `TIMELINE_LIMITS` 与后端 `app/services/studio_timeline_*.py` 一致。
 */
export const NLE_OWNER_LIMITS = {
  /** `TIMELINE_LIMITS.duration` = `MAX_DURATION_MS` = 600_000（10 分钟）。 */
  durationMs: TIMELINE_LIMITS.duration,
  /** `TIMELINE_LIMITS.tracks` = `1 <= len(tracks) <= 8`。 */
  tracks: TIMELINE_LIMITS.tracks,
  /** `TIMELINE_LIMITS.kindTracks` = 视频与音频各最多 4 条。 */
  tracksPerKind: TIMELINE_LIMITS.kindTracks,
  /** `TIMELINE_LIMITS.clips` = `MAX_CLIPS` = 30（总计，同时每轨 1..30）。 */
  clips: TIMELINE_LIMITS.clips,
  /** `TIMELINE_LIMITS.captions` = 500。 */
  captions: TIMELINE_LIMITS.captions,
  /** `TIMELINE_LIMITS.captionCharacters` = `MAX_CAPTION_CHARACTERS` = 32_000。 */
  captionCharacters: TIMELINE_LIMITS.captionCharacters,
  /** `_integer(row.width, 16, 1920)`。 */
  width: 1920,
  /** `_integer(row.height, 16, 1080)`。 */
  height: 1080,
  /** `_integer(row.fps, 1, 60)`。 */
  fpsMin: 1,
  fpsMax: 60,
  /** `_integer(clip.in_ms, 0, 36_000_000)` / `out_ms` 的上界。 */
  sourceTrimMs: 36_000_000,
  /** `render_studio_timeline(..., max_bytes)` 的 `_integer(max_bytes, 1, 25 * 1024 * 1024)`。 */
  singleAssetBytes: 25 * 1024 * 1024,
  /** `MAX_SOURCE_BYTES = 200 * 1024 * 1024`（一次渲染读取的素材字节总和）。 */
  totalSourceBytes: 200 * 1024 * 1024,
  /** `RENDER_TIMEOUT_SECONDS = 120`；导出预览收据的 `limits.render_timeout_seconds` 必须是它。 */
  renderTimeoutSeconds: 120,
  /** `MAX_SIDECAR_BYTES = 192000`。 */
  subtitleSidecarBytes: 192_000,
  /** `apply_timeline_edits` 的 `1 <= len(operations) <= 40`。 */
  editOperationsPerBatch: 40,
  /** `apply_timeline_edits` 的 128_000 字节批次上限。 */
  editBatchBytes: 128_000,
  /** 轨道与片段音量：`-60 <= gain_db <= 12`；视频轨道固定为 0。 */
  gainMinDb: -60,
  gainMaxDb: 12,
} as const;

/** 稳定的机器码。用户可见文案一律中文，机器码不变。 */
export const NLE_CODES = {
  timelineInvalid: 'NLE_TIMELINE_INVALID',
  timebaseInvalid: 'NLE_TIMEBASE_INVALID',
  viewInvalid: 'NLE_VIEW_INVALID',
  integerRequired: 'NLE_INTEGER_REQUIRED',
  marksInvalid: 'NLE_MARKS_INVALID',
  rangeInRequired: 'NLE_RANGE_IN_REQUIRED',
  rangeOutRequired: 'NLE_RANGE_OUT_REQUIRED',
  rangeOutBeforeIn: 'NLE_RANGE_OUT_BEFORE_IN',
  rangeOutsideSource: 'NLE_RANGE_OUTSIDE_SOURCE',
  rangeOutsideTimeline: 'NLE_RANGE_OUTSIDE_TIMELINE',
  rangeBeforeSourceIn: 'NLE_RANGE_BEFORE_SOURCE_IN',
  snapToleranceInvalid: 'NLE_SNAP_TOLERANCE_INVALID',
  trackNotFound: 'NLE_TRACK_NOT_FOUND',
  trackGainOutOfRange: 'NLE_TRACK_GAIN_OUT_OF_RANGE',
  trackGainVideoFixed: 'NLE_TRACK_GAIN_VIDEO_FIXED',
  trackLocked: 'NLE_TRACK_LOCKED',
  editSelectionRequired: 'NLE_EDIT_SELECTION_REQUIRED',
  editKindUnsupported: 'NLE_EDIT_KIND_UNSUPPORTED',
  editClipNotFound: 'NLE_EDIT_CLIP_NOT_FOUND',
  editTrackNotFound: 'NLE_EDIT_TRACK_NOT_FOUND',
  editNewIdRequired: 'NLE_EDIT_NEW_ID_REQUIRED',
  editIdInvalid: 'NLE_EDIT_ID_INVALID',
  editSplitOutsideClip: 'NLE_EDIT_SPLIT_OUTSIDE_CLIP',
  editFractionalMs: 'NLE_EDIT_FRACTIONAL_MS',
  editMoveKindInvalid: 'NLE_EDIT_MOVE_KIND_INVALID',
  editStillSlipInvalid: 'NLE_EDIT_STILL_SLIP_INVALID',
  editSlipOutsideSource: 'NLE_EDIT_SLIP_OUTSIDE_SOURCE',
  editSourceKindInvalid: 'NLE_EDIT_SOURCE_KIND_INVALID',
  editSourceSnapshotInvalid: 'NLE_EDIT_SOURCE_SNAPSHOT_INVALID',
  editRangeInvalid: 'NLE_EDIT_RANGE_INVALID',
  editTrimEmpty: 'NLE_EDIT_TRIM_EMPTY',
  editTrimOutsideSource: 'NLE_EDIT_TRIM_OUTSIDE_SOURCE',
  editBatchLimit: 'NLE_EDIT_BATCH_LIMIT',
  previewRequestInvalid: 'NLE_PREVIEW_REQUEST_INVALID',
  previewSourceInvalid: 'NLE_PREVIEW_SOURCE_INVALID',
  previewTimelineInvalid: 'NLE_PREVIEW_TIMELINE_INVALID',
  previewPositionInvalid: 'NLE_PREVIEW_POSITION_INVALID',
  captionIndexInvalid: 'NLE_CAPTION_INDEX_INVALID',
  captionShapeInvalid: 'NLE_CAPTION_SHAPE_INVALID',
  captionLimit: 'NLE_CAPTION_LIMIT',
  captionCharacterLimit: 'NLE_CAPTION_CHARACTER_LIMIT',
  subtitleShapeInvalid: 'NLE_SUBTITLE_SHAPE_INVALID',
  subtitleFormatInvalid: 'NLE_SUBTITLE_FORMAT_INVALID',
  subtitleByteLimit: 'NLE_SUBTITLE_BYTE_LIMIT',
  subtitleHeaderInvalid: 'NLE_SUBTITLE_HEADER_INVALID',
  subtitleLineEndingsInvalid: 'NLE_SUBTITLE_LINE_ENDINGS_INVALID',
  subtitleNumberedCuesRequired: 'NLE_SUBTITLE_NUMBERED_CUES_REQUIRED',
  subtitleCueLimit: 'NLE_SUBTITLE_CUE_LIMIT',
  subtitleCharacterLimit: 'NLE_SUBTITLE_CHARACTER_LIMIT',
  subtitleNoTranscriptionOwner: 'NLE_SUBTITLE_NO_TRANSCRIPTION_OWNER',
  exportShapeInvalid: 'NLE_EXPORT_RECEIPT_INVALID',
  exportPresetInvalid: 'NLE_EXPORT_PRESET_INVALID',
  exportPreviewDigestInvalid: 'NLE_EXPORT_PREVIEW_DIGEST_INVALID',
  limitsShapeInvalid: 'NLE_LIMITS_SHAPE_INVALID',
  limitsRaiseRefused: 'NLE_LIMITS_RAISE_REFUSED',
} as const;

export type NleCode = typeof NLE_CODES[keyof typeof NLE_CODES];

/** 明确拒绝：绝不静默改成别的动作。 */
export type NleRefusal = { ok: false; code: string; message: string };
export type NleOk<T> = { ok: true; value: T };

export type NleRange = { startMs: number; endMs: number; durationMs: number };
export type NleMarks = { inMs: number | null; outMs: number | null };
export type NleMarkPoint = 'IN' | 'OUT';
/** 素材可裁剪范围；只有原服务能证明实际素材时长。 */
export type NleSourceRange = { inMs: number; outMs: number };

export type NleRangeCheck =
  | { ok: true; range: NleRange; sourceRangeChecked: boolean }
  | NleRefusal;
export type NleMarksCheck = { ok: true; marks: NleMarks } | NleRefusal;

/** 视窗是**仅呈现**状态：`scale` 为"每毫秒像素数"，不属于持久化时间线。 */
export type NleViewWindow = { startMs: number; scale: number };
export type NleWindowCheck = { ok: true; window: NleViewWindow } | NleRefusal;
export type NleWindowRange = { startMs: number; endMs: number; windowMs: number };

export type NleRulerTick = {
  index: number;
  ms: number;
  major: boolean;
  label: string;
  /** 由整数毫秒基派生（`floor(ms * fps / 1000)`），不是权威帧边界。 */
  frame?: number;
};
export type NleRuler = {
  window: NleViewWindow;
  range: NleWindowRange;
  stepMs: number;
  minorStepMs: number;
  ticks: NleRulerTick[];
  truncated: boolean;
};

export type NleSnapKind = 'MARK_IN' | 'MARK_OUT' | 'PLAYHEAD' | 'CLIP_START' | 'CLIP_END';
export type NleSnapCandidate = { ms: number; kind: NleSnapKind; trackId: string | null; clipId: string | null; label: string };
export type NleSnapSet = { candidates: NleSnapCandidate[]; toleranceMs: number; truncated: boolean };
export type NleSnapResult = { ms: number; snapped: boolean; candidate: NleSnapCandidate | null };

export type NleTrackHeaderState = {
  trackId: string;
  kind: StudioTimelineTrack['kind'];
  order: number;
  role: string;
  locked: boolean;
  muted: boolean;
  gainDb: number;
  gainMinDb: number;
  gainMaxDb: number;
  gainAdjustable: boolean;
  clipCount: number;
  clipIds: string[];
};
export type NleTrackHeaderCheck = { ok: true; header: NleTrackHeaderState } | NleRefusal;

export type NleClipFacts = {
  trackId: string;
  trackKind: StudioTimelineTrack['kind'];
  clip: StudioTimelineClip;
  startMs: number;
  durationMs: number;
  endMs: number;
  sourceKind: StudioTimelineSource['asset_kind'];
  speedNum: number;
  speedDen: number;
};

/** 原 owner 的编辑操作 id（`app/services/studio_timeline_edit.py: apply_timeline_edits`）。 */
export type NleOwnerOperationId =
  | 'canvas.update' | 'track.insert' | 'track.remove' | 'track.update' | 'track.reorder'
  | 'clip.insert' | 'clip.update' | 'clip.remove' | 'clip.move' | 'clip.duplicate'
  | 'clip.split' | 'clip.trim' | 'clip.slip'
  | 'caption.insert' | 'caption.update' | 'caption.remove';

/** `clip.update` 在 owner 处接受的字段子集（本面只生成其中一部分）。 */
export type NleClipChanges = {
  source_snapshot?: StudioTimelineSource;
  start_ms?: number;
  in_ms?: number;
  out_ms?: number;
  x?: number; y?: number; width?: number; height?: number;
  speed_num?: number; speed_den?: number; opacity?: number;
  gain_db?: number; muted?: boolean; include_audio?: boolean;
  fade_in_ms?: number; fade_out_ms?: number;
  color_adjustment?: StudioTimelineClip['color_adjustment'] | null;
  crop?: StudioTimelineClip['crop'] | null;
  transition_out?: StudioTimelineTransition | null;
};

/** 只使用原 owner 已经接受的形状；绝不发明它不实现的动作。 */
export type NleOwnerOperation =
  | { op: 'clip.split'; clip_id: string; at_ms: number; new_clip_id: string }
  | { op: 'clip.trim'; clip_id: string; in_ms: number; out_ms: number; ripple: boolean }
  | { op: 'clip.remove'; clip_id: string; ripple: boolean }
  | { op: 'clip.move'; clip_id: string; track_id: string; start_ms: number }
  | { op: 'clip.duplicate'; clip_id: string; new_clip_id: string; track_id: string; start_ms: number }
  | { op: 'clip.slip'; clip_id: string; offset_ms: number }
  | { op: 'clip.update'; clip_id: string; changes: NleClipChanges }
  | { op: 'caption.insert'; caption: StudioTimelineCaption }
  | { op: 'caption.update'; index: number; caption: StudioTimelineCaption }
  | { op: 'caption.remove'; index: number };

export type NleEditKind = 'split' | 'trim' | 'move' | 'copy' | 'slip' | 'ripple' | 'source-replace';
export type NleCaptionKind = 'caption-insert' | 'caption-update' | 'caption-remove';
export type NleEditPlan =
  | { ok: true; kind: NleEditKind | NleCaptionKind; op: NleOwnerOperationId; payload: NleOwnerOperation; batchBytes: number }
  | NleRefusal;

/** 冻结的 `onEdit` 参数形状：`kind` 为原 owner 操作 id，`payload` 为完整操作对象。 */
export type NleEditRequest = { kind: string; payload: unknown };

export type NleTrimPlan =
  | { ok: true; inMs: number; outMs: number; mediaInDeltaMs: number; mediaOutDeltaMs: number; durationMs: number; timelineDeltaMs: number }
  | NleRefusal;

export type NleSubtitleCueState = {
  index: number; startMs: number; endMs: number; durationMs: number;
  text: string; lines: number; characters: number;
  locateReady: boolean; editReady: boolean; problems: string[];
};
export type NleSubtitleFormat = 'SRT' | 'VTT';
export type NleSubtitleModel = {
  cues: NleSubtitleCueState[];
  cueCount: number;
  characters: number;
  locateReady: boolean;
  editReady: boolean;
  importReady: boolean;
  importCode: string | null;
  importMessage: string;
  exportReady: boolean;
  exportCode: string | null;
  exportMessage: string;
  exportFormat: NleSubtitleFormat | null;
  transcriptionAvailable: false;
  transcriptionCode: string;
  transcriptionMessage: string;
  manualAvailable: boolean;
  limits: { captions: number; captionCharacters: number; sidecarBytes: number };
};

export type NleExportQuality = 'PREVIEW' | 'FINAL';
export type NleExportStage = 'NONE' | 'PREVIEW_CHECKED' | 'DISPATCHED_UNKNOWN' | 'RECEIPT_RETURNED' | 'INVALID';
export type NleExportQualityFact = { quality: NleExportQuality; preset: string; label: string; detail: string };
export type NleExportStatus = {
  stage: NleExportStage;
  requestedQuality: NleExportQuality | null;
  previewQuality: NleExportQualityFact | null;
  finalExportQuality: NleExportQualityFact | null;
  /** 永远是 `false`：产物是私有候选，需在制作任务中人工审核（`product_acceptance: 'LOCAL_REQUIRED'`）。 */
  deliveryReady: false;
  head: string;
  detail: string;
  warnings: string[];
  code: string | null;
  requestId: string | null;
  previewDigest: string | null;
  limits: { renderTimeoutSeconds: number; maxOutputBytes: number } | null;
};

export type NleUsage = {
  tracks: number; clips: number; durationMs: number; captions: number; captionCharacters: number; largestAssetBytes?: number; totalAssetBytes?: number;
};
export type NleLimitRow = {
  key: string; label: string; ownerLimit: number; used: number | null; remaining: number | null;
  ratio: number | null; near: boolean; reached: boolean; unit: string; source: string;
};
export type NleLimitsNotice = {
  rows: NleLimitRow[];
  warnings: string[];
  splitAdvice: string;
  nearAny: boolean;
  reachedAny: boolean;
  raiseRefused: boolean;
  refusedRaises: Array<{ key: string; offered: number; ownerLimit: number }>;
  code: string | null;
};

export type NleView = { window: NleViewWindow; range: NleWindowRange };

/**
 * 按需缩略图 / 波形的读取契约（纯描述符，本模块一律不做 I/O、不缓存、不解码）。
 * `key` 同时绑定**原始素材版本摘要**与**时间线版本摘要**：任一变化都会得到新键，
 * 因此陈旧预览不可能被当成当前预览复用；调用方按需读取，绝不在每次拖动时解码素材。
 */
export type NleMediaPreviewKind = 'THUMBNAIL' | 'WAVEFORM';
export type NleMediaPreviewRequest = {
  kind: NleMediaPreviewKind;
  atMs: number;
  assetId: string;
  assetKind: StudioTimelineSource['asset_kind'];
  assetVersion: number;
  assetDigest: string;
  timelineId: string;
  timelineVersion: number;
  timelineDigest: string;
  key: string;
};

/** 面板统一使用的"时间线可用"判定；失败时携带原 owner 的中文说明。 */
export type NleTimelineCheck = { ok: true; timeline: StudioTimeline } | NleRefusal;
export type NleTimeline = StudioTimeline;
export type NleClipSelection = readonly string[];
