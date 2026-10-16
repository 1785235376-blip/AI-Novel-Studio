import type { TimelineTransferPreview } from './studioTimelineTransferTypes';

/** Paths belong to the original export owner, never to normalized import indices. */
export function transferClipTarget(preview: TimelineTransferPreview, path: string) {
  if (preview.direction !== 'EXPORT' || preview.format !== 'OTIO') return;
  const match = /^tracks\[(0|[1-9]\d*)\]\.clips(?:\[(0|[1-9]\d*)\](?:\.transition_out)?|\.([A-Za-z0-9][A-Za-z0-9_-]{0,239}))$/.exec(path);
  if (!match) return;
  const track = preview.timeline.tracks[Number(match[1])];
  if (!track || preview.timeline.tracks.filter(row => row.id === track.id).length !== 1) return;
  const clip = match[2] !== undefined ? track.clips[Number(match[2])] : track.clips.find(row => row.id === match[3]);
  if (!clip || preview.timeline.tracks.flatMap(row => row.clips).filter(row => row.id === clip.id).length !== 1) return;
  return { track, clip };
}

export const transferLossText: Record<string, string> = {
  TRACK_LOCK_REQUIRES_STUDIO_METADATA: '轨道锁仅保留在 Studio 扩展元数据中。',
  TRACK_MUTE_GAIN_REQUIRES_STUDIO_METADATA: '轨道静音和音量仅保留在 Studio 扩展元数据中。',
  TRACK_ROLE_REQUIRES_STUDIO_METADATA: '轨道用途仅保留在 Studio 扩展元数据中。',
  CLIP_MIX_FADES_REQUIRE_STUDIO_METADATA: '片段静音、音量及淡入淡出不能作为原生 NLE 混音还原。',
  VIDEO_CROSS_DISSOLVE_NOT_NATIVE_NLE_PRESERVED_IN_STUDIO_METADATA: '交叉溶解仅保留在 Studio 元数据中；外部原生轨道不还原该效果。',
  CLIP_PIXEL_CROP_REQUIRES_STUDIO_METADATA: '像素裁剪仅保留在 Studio 元数据中。',
  VIDEO_GEOMETRY_OPACITY_REQUIRE_STUDIO_METADATA: '画面位置、尺寸或不透明度仅保留在 Studio 元数据中。',
  EMBEDDED_VIDEO_AUDIO_MIX_REQUIRES_STUDIO_METADATA: '视频原声的混音设置仅保留在 Studio 元数据中。',
  STILL_IMAGE_DURATION_INTEROPERABILITY_NOT_RUN: '静态画面展示时长尚未在目标编辑器实测。',
  CAPTIONS_REQUIRE_STUDIO_METADATA_NO_NLE_SUBTITLE_TRACK: '字幕保留在 Studio 元数据中，没有生成原生 NLE 字幕轨。',
  CANVAS_RATE_DIMENSIONS_REQUIRE_STUDIO_METADATA: '输出画布尺寸和帧率依赖 Studio 元数据；原生片段时间值另行保留。',
  FORMAL_ASSET_REFERENCES_ONLY_NO_MEDIA_PACKAGING: '只有精确素材版本的相对引用，媒体文件未打包。',
  RESOLVE_PREMIERE_INTEROPERABILITY_NOT_RUN: 'Resolve / Premiere 尚未实测，实际兼容性为 LOCAL_REQUIRED。',
  NLE_LINEAR_TIME_WARP_INTEROPERABILITY_NOT_RUN: '原生 LinearTimeWarp 已写出；目标编辑器的变速表现尚未实测。',
  VIDEO_OVERLAP_EXPORTED_AS_PARALLEL_LANES: '重叠视频片段转换为并行原生轨道；不代表合成效果保真。',
  AUDIO_OVERLAP_EXPORTED_AS_PARALLEL_LANES: '重叠音频片段转换为并行原生轨道；不代表混音效果保真。',
  LANE_NAME_TRUNCATED_ID_RETAINED_IN_STUDIO_METADATA: '原生轨道名称截短；完整 ID 保留在 Studio 元数据中。',
  STUDIO_METADATA_STALE_AFTER_NATIVE_EDIT_NOT_RESTORED: '原生剪辑已变化，旧 Studio 扩展未恢复。',
  GLOBAL_TIMECODE_NOT_STUDIO_TIMELINE_PLACEMENT: '全局时间码没有转换为 Studio 片段摆放。',
  EXCHANGE_TITLE_IS_NOT_A_STUDIO_TIMELINE_FIELD: '交换文件标题未导入为 Studio 时间线字段。',
  NATIVE_DISSOLVE_IMPORTED_AS_CUT: '原生叠化导入为直接切点。',
  NATIVE_CLIP_NAME_NORMALIZED_TO_STUDIO_ID: '原生片段名称转换为 Studio 片段 ID。',
  NATIVE_TRACK_NAME_NORMALIZED_TO_STUDIO_ID: '原生轨道名称转换为 Studio 轨道 ID。',
  GAP_ONLY_TRACK_NOT_IMPORTED: '只有间隙的轨道未导入。',
  NATIVE_FRAME_RATES_DIFFER_FROM_REQUESTED_STUDIO_OUTPUT_FPS: '原生帧率与目标输出帧率不同，请核对时间基准。',
};
