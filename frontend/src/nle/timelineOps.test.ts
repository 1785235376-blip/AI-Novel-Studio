// @vitest-environment jsdom
/**
 * UX-06 纯函数契约测试：时间基精确性（无浮点累加、无漂移）、标尺/缩放/吸附候选、
 * 入出点校验、轨道状态校验、编辑指令映射（含明确拒绝）、字幕模型、导出状态诚实性与上限提示。
 */
import { describe, expect, it } from 'vitest';
import { checkedTimeline } from '../creative/studioTimelineTypes';
import type { StudioTimeline } from '../creative/studioTimelineTypes';
import {
  NLE_CODES, NLE_OWNER_LIMITS,
} from './timelineOpsTypes';
import {
  NLE_DEFAULT_SNAP_TOLERANCE_MS,
  captionCommand, clipFacts, editBatchState, editCommand, exportStatus, frameIndex, limitsNotice,
  mediaPreviewRequest, ownerOperationSupported, rulerLabel, rulerTicks, safeTimeline, scrollWindow, selectedClipFacts,
  setInOut, snapCandidates, snapClipStart, snapTime, subtitleTrackModel, timebaseOf, timelineUsage,
  trackGainState, trackHeaderState, trimClip, validateMarks, validateRange, validateTimebase,
  validateWindow, windowRange, zoomWindow,
} from './timelineOps';

const DIGEST = 'a'.repeat(64);
const videoSource = { id: 'asset-video', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST };
const audioSource = { id: 'asset-audio', kind: 'ASSET', asset_kind: 'audio', version: 2, digest: DIGEST };
const imageSource = { id: 'asset-image', kind: 'ASSET', asset_kind: 'image', version: 1, digest: DIGEST };

function videoClip(id: string, start: number, inMs: number, outMs: number, extra: Record<string, unknown> = {}) {
  return {
    id, source_snapshot: videoSource, start_ms: start, in_ms: inMs, out_ms: outMs,
    x: 0, y: 0, width: 1280, height: 720, speed_num: 1, speed_den: 1, opacity: 1, muted: false,
    gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, include_audio: false, ...extra,
  };
}
function audioClip(id: string, start: number, inMs: number, outMs: number, extra: Record<string, unknown> = {}) {
  return {
    id, source_snapshot: audioSource, start_ms: start, in_ms: inMs, out_ms: outMs,
    speed_num: 1, speed_den: 1, muted: false, gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, ...extra,
  };
}
function imageClip(id: string, start: number, outMs: number, extra: Record<string, unknown> = {}) {
  return {
    id, source_snapshot: imageSource, start_ms: start, in_ms: 0, out_ms: outMs,
    x: 0, y: 0, width: 1280, height: 720, speed_num: 1, speed_den: 1, opacity: 1, muted: false,
    gain_db: 0, fade_in_ms: 0, fade_out_ms: 0, include_audio: false, ...extra,
  };
}
function track(id: string, kind: 'VIDEO' | 'AUDIO', order: number, clips: unknown[], extra: Record<string, unknown> = {}) {
  return { id, kind, order, role: kind === 'VIDEO' ? 'PRIMARY' : 'DIALOGUE', muted: false, gain_db: 0, clips, ...extra };
}
const build = (tracks: unknown[], captions: unknown[] = [], duration = 10_000): StudioTimeline => checkedTimeline({
  schema_version: 2, duration_ms: duration, width: 1280, height: 720, fps: 25, tracks, captions,
});

/** 主夹具：第二条视频轨道上有一个静态画面片段（用于滑移拒绝）。 */
function mainTimeline(): StudioTimeline {
  return build([
    track('video-1', 'VIDEO', 0, [videoClip('clip-a', 0, 0, 4000), videoClip('clip-b', 4000, 0, 3000)]),
    track('audio-1', 'AUDIO', 1, [audioClip('clip-c', 0, 0, 5000)]),
    track('video-2', 'VIDEO', 2, [imageClip('clip-d', 5000, 2000)]),
  ], [{ start_ms: 0, end_ms: 1000, text: '第一句' }]);
}
function singleTimeline(clip: Record<string, unknown>, kind: 'VIDEO' | 'AUDIO' = 'VIDEO'): StudioTimeline {
  return build([track('only-track', kind, 0, [clip])]);
}

const MAIN = mainTimeline();
const MAIN_TB = timebaseOf(MAIN);

describe('整数时间基：标尺刻度与裁剪都不做浮点累加', () => {
  it('由整数毫秒与整数帧率派生帧序号（向下取整）', () => {
    expect(frameIndex(0, 25)).toBe(0);
    expect(frameIndex(1000, 25)).toBe(25);
    expect(frameIndex(999, 25)).toBe(24);
    expect(frameIndex(41, 24)).toBe(0);
    expect(frameIndex(42, 24)).toBe(1);
    expect(Number.isSafeInteger(frameIndex(600_000, 60))).toBe(true);
  });

  it('rulerLabel 只用整数除法与取模', () => {
    expect(rulerLabel(0)).toBe('00:00.000');
    expect(rulerLabel(1000)).toBe('00:01.000');
    expect(rulerLabel(61_001)).toBe('01:01.001');
    expect(rulerLabel(3_600_000)).toBe('1:00:00.000');
    expect(rulerLabel(600_000)).toBe('10:00.000');
  });

  it('刻度位置是步长的精确整数倍，相邻间隔恒等，且从不超出总长', () => {
    const ruler = rulerTicks({ startMs: 0, scale: 0.5 }, MAIN_TB, 960);
    expect(ruler.ticks.length).toBeGreaterThan(1);
    for (const tick of ruler.ticks) {
      expect(Number.isSafeInteger(tick.ms)).toBe(true);
      expect(tick.ms % ruler.minorStepMs).toBe(0);
      expect(tick.ms).toBeLessThanOrEqual(MAIN_TB.durationMs);
      expect(tick.ms).toBeGreaterThanOrEqual(ruler.range.startMs);
    }
    for (let index = 1; index < ruler.ticks.length; index++) {
      expect(ruler.ticks[index].ms - ruler.ticks[index - 1].ms).toBe(ruler.minorStepMs);
    }
    expect(ruler.truncated).toBe(false);
    expect(ruler.ticks.filter(tick => tick.major).length).toBeLessThanOrEqual(13);
    expect(ruler.range.endMs).toBeLessThanOrEqual(MAIN_TB.durationMs);
  });

  it('视窗起点不是步长整数倍时刻度仍然精确落位，不产生漂移', () => {
    const ruler = rulerTicks({ startMs: 333, scale: 1 }, MAIN_TB, 300);
    expect(ruler.range.startMs).toBe(333);
    for (const tick of ruler.ticks) {
      expect(tick.ms % ruler.minorStepMs).toBe(0);
      expect(tick.ms).toBeGreaterThanOrEqual(333);
    }
    const repeat = rulerTicks({ startMs: 333, scale: 1 }, MAIN_TB, 300);
    expect(repeat.ticks.map(tick => tick.ms)).toEqual(ruler.ticks.map(tick => tick.ms));
  });

  it('反复向内裁剪 1000 次也不漂移，并在素材入点上停止', () => {
    let clip = mainTimeline().tracks[0].clips[0];
    const start = clip.out_ms;
    for (let step = 0; step < 1000; step++) {
      const plan = trimClip(clip, { outDeltaMs: -1 });
      expect(plan.ok).toBe(true);
      if (!plan.ok) return;
      expect(plan.outMs).toBe(clip.out_ms - 1);
      clip = { ...clip, in_ms: plan.inMs, out_ms: plan.outMs };
    }
    expect(clip.out_ms).toBe(start - 1000);
    expect(clip.in_ms).toBe(0);
    for (let step = 0; step < 5000; step++) {
      const plan = trimClip(clip, { outDeltaMs: -1 });
      if (!plan.ok) { expect(plan.code).toBe(NLE_CODES.editTrimEmpty); break; }
      clip = { ...clip, out_ms: plan.outMs };
      expect(plan.outMs).toBeGreaterThan(plan.inMs);
    }
    expect(clip.out_ms).toBe(1);
  });

  it('裁剪绝不超出已证明的素材范围，并在边界上停止', () => {
    const clip = mainTimeline().tracks[0].clips[0];
    const inward = trimClip(clip, { outDeltaMs: -100 }, { sourceRange: { inMs: 0, outMs: 4000 } });
    expect(inward.ok).toBe(true);
    if (!inward.ok) return;
    expect(inward.outMs).toBe(3900);
    let current = { ...clip, out_ms: inward.outMs };
    for (let step = 0; step < 200; step++) {
      const plan = trimClip(current, { outDeltaMs: 1 }, { sourceRange: { inMs: 0, outMs: 4000 } });
      if (!plan.ok) { expect(plan.code).toBe(NLE_CODES.editTrimOutsideSource); break; }
      current = { ...current, out_ms: plan.outMs };
    }
    expect(current.out_ms).toBe(4000);
    const raised = trimClip(clip, { outDeltaMs: 1 }, { sourceRange: { inMs: 0, outMs: 4000 } });
    expect(raised.ok).toBe(false);
    if (!raised.ok) expect(raised.code).toBe(NLE_CODES.editTrimOutsideSource);
  });

  it('不能映射到整数毫秒的裁剪增量被拒绝', () => {
    const slow = { ...mainTimeline().tracks[0].clips[0], speed_num: 1, speed_den: 2 };
    const plan = trimClip(slow, { outDeltaMs: -1 });
    expect(plan.ok).toBe(false);
    if (!plan.ok) expect(plan.code).toBe(NLE_CODES.editFractionalMs);
    const exact = trimClip(slow, { outDeltaMs: -2 });
    expect(exact.ok).toBe(true);
    if (exact.ok) expect(exact.mediaOutDeltaMs).toBe(-1);
  });
});

describe('视窗：缩放与滚动的边界', () => {
  it('validateWindow 只接受范围内的整数起点与有限缩放', () => {
    expect(validateWindow({ startMs: 0, scale: 0.5 }, MAIN_TB).ok).toBe(true);
    expect(validateWindow({ startMs: -1, scale: 0.5 }, MAIN_TB).ok).toBe(false);
    expect(validateWindow({ startMs: 0, scale: 0 }, MAIN_TB).ok).toBe(false);
    expect(validateWindow({ startMs: 0, scale: 9 }, MAIN_TB).ok).toBe(false);
    expect(validateWindow({ startMs: 0, scale: Number.NaN }, MAIN_TB).ok).toBe(false);
    expect(validateWindow({ startMs: 0, scale: 1, extra: 1 }, MAIN_TB).ok).toBe(false);
    expect(validateWindow({ startMs: 1.5, scale: 1 }, MAIN_TB).ok).toBe(false);
    expect(validateTimebase({ durationMs: 0, fps: 25 }).ok).toBe(false);
    expect(validateTimebase({ durationMs: 10_000, fps: 61 }).ok).toBe(false);
    expect(validateTimebase({ durationMs: 10_000, fps: 25 })).toEqual({ ok: true, value: { durationMs: 10_000, fps: 25 } });
  });

  it('视窗末端受总长约束，永不超出 owner 的时长', () => {
    expect(windowRange({ startMs: 9500, scale: 0.001 }, 960, MAIN_TB).endMs).toBe(10_000);
    expect(windowRange({ startMs: 0, scale: 1 }, 960, MAIN_TB)).toEqual({ startMs: 0, endMs: 960, windowMs: 960 });
    expect(windowRange({ startMs: 0, scale: 1 }, -5, MAIN_TB).windowMs).toBe(960);
    expect(windowRange({ startMs: 0, scale: 1 }, 10 ** 9, MAIN_TB).windowMs).toBeLessThanOrEqual(MAIN_TB.durationMs);
  });

  it('缩放保持锚点并收敛到合法视窗', () => {
    const zoomed = zoomWindow({ startMs: 0, scale: 0.5 }, 2, 5000, MAIN_TB);
    expect(zoomed.scale).toBe(1);
    expect(zoomed.startMs).toBe(2500);
    expect(zoomWindow({ startMs: 0, scale: 1 }, 100, 0, MAIN_TB).scale).toBe(8);
    expect(zoomWindow({ startMs: 0, scale: 1 }, 0.001, 0, MAIN_TB).scale).toBeCloseTo(0.001, 10);
    expect(zoomWindow({ startMs: 0, scale: 1 }, 0.000001, 0, MAIN_TB).scale).toBe(1);
    expect(zoomWindow({ startMs: 9000, scale: 1 }, 0.1, 10_000, MAIN_TB).startMs).toBeLessThanOrEqual(10_000);
    expect(zoomWindow({ startMs: 0, scale: 1 }, Number.NaN, 0, MAIN_TB).scale).toBe(1);
  });

  it('滚动被夹在 0 与末端之间', () => {
    expect(scrollWindow({ startMs: 0, scale: 1 }, -999_999, MAIN_TB).startMs).toBe(0);
    expect(scrollWindow({ startMs: 0, scale: 1 }, 1_000_000, MAIN_TB).startMs).toBe(10_000 - 960);
    expect(scrollWindow({ startMs: 100, scale: 1 }, 5, MAIN_TB).startMs).toBe(105);
    expect(scrollWindow({ startMs: 100, scale: 1 }, 1.5, MAIN_TB).startMs).toBe(100);
  });
});

describe('吸附候选只来自真实边界', () => {
  it('候选集合等于片段边界、播放头与入出点的去重结果', () => {
    const set = snapCandidates({ timeline: MAIN, playheadMs: 3000, marks: { inMs: 1000, outMs: 8000 } });
    expect(set.toleranceMs).toBe(NLE_DEFAULT_SNAP_TOLERANCE_MS);
    expect(set.truncated).toBe(false);
    expect(set.candidates.map(item => item.ms)).toEqual([0, 1000, 3000, 4000, 5000, 7000, 8000]);
    expect(set.candidates.find(item => item.ms === 1000)?.kind).toBe('MARK_IN');
    expect(set.candidates.find(item => item.ms === 3000)?.kind).toBe('PLAYHEAD');
    expect(set.candidates.find(item => item.ms === 8000)?.kind).toBe('MARK_OUT');
    expect(set.candidates.find(item => item.ms === 0)?.clipId).toBe('clip-a');
    expect(set.candidates.find(item => item.ms === 7000)?.kind).toBe('CLIP_END');
  });

  it('越界的入出点与播放头不会成为候选', () => {
    const set = snapCandidates({ timeline: MAIN, playheadMs: 99_999, marks: { inMs: -1, outMs: 99_999 } });
    expect(set.candidates.every(item => item.ms >= 0 && item.ms <= MAIN.duration_ms)).toBe(true);
    expect(set.candidates.some(item => item.kind === 'PLAYHEAD')).toBe(false);
    expect(set.candidates.some(item => item.kind === 'MARK_OUT')).toBe(false);
  });

  it('吸附只接受容差内的候选，容差非法时回落到默认值', () => {
    const set = snapCandidates({ timeline: MAIN, playheadMs: 3000, marks: { inMs: 1000, outMs: 8000 } });
    const near = snapTime(set, 3010);
    expect(near.snapped).toBe(true);
    expect(near.ms).toBe(3000);
    expect(near.candidate?.kind).toBe('PLAYHEAD');
    expect(snapTime(set, 3200).snapped).toBe(false);
    expect(snapTime(set, 3200).ms).toBe(3200);
    expect(snapCandidates({ timeline: MAIN, playheadMs: 0, marks: { inMs: null, outMs: null }, toleranceMs: 10_000 }).toleranceMs).toBe(120);
    expect(snapTime(set, 3010, 1).snapped).toBe(false);
  });

  it('吸附后的片段起点始终落在时间线内', () => {
    const set = snapCandidates({ timeline: MAIN, playheadMs: 3000, marks: { inMs: 1000, outMs: 8000 } });
    const first = clipFacts(MAIN, 'clip-a');
    expect(first).not.toBeNull();
    if (!first) return;
    expect(snapClipStart(MAIN, first.clip, 3990, set).ms).toBe(4000);
    const last = clipFacts(MAIN, 'clip-b');
    if (!last) return;
    expect(snapClipStart(MAIN, last.clip, 999_999, set).ms).toBe(7000);
    expect(snapClipStart(MAIN, last.clip, -50, set).ms).toBe(0);
  });
});

describe('入点、出点与范围校验', () => {
  it('标记与范围只接受整数毫秒', () => {
    expect(validateMarks({ inMs: 1.5, outMs: null }, MAIN_TB).ok).toBe(false);
    expect(validateMarks({ inMs: null, outMs: null }, MAIN_TB)).toEqual({ ok: true, marks: { inMs: null, outMs: null } });
    expect(validateMarks({ inMs: 0, outMs: 10_000, extra: 1 }, MAIN_TB).ok).toBe(false);
  });

  it('setInOut 拒绝与另一端点冲突的设置，而不是替用户改动它', () => {
    const first = setInOut({ inMs: null, outMs: null }, 'IN', 1000, MAIN_TB);
    expect(first).toEqual({ ok: true, marks: { inMs: 1000, outMs: null } });
    const conflict = setInOut({ inMs: 1000, outMs: null }, 'OUT', 500, MAIN_TB);
    expect(conflict.ok).toBe(false);
    if (!conflict.ok) expect(conflict.code).toBe(NLE_CODES.rangeOutBeforeIn);
    const outside = setInOut({ inMs: null, outMs: null }, 'OUT', 10_001, MAIN_TB);
    expect(outside.ok).toBe(false);
    if (!outside.ok) expect(outside.code).toBe(NLE_CODES.integerRequired);
    expect(setInOut({ inMs: null, outMs: null }, 'IN', 1.5, MAIN_TB).ok).toBe(false);
    expect(setInOut({ inMs: null, outMs: null }, 'MIDDLE', 10, MAIN_TB).ok).toBe(false);
  });

  it('validateRange 拒绝缺失端点、倒置范围、超出时间线与超出素材范围', () => {
    expect(validateRange({ inMs: null, outMs: 100 }, MAIN_TB).ok).toBe(false);
    expect(validateRange({ inMs: 100, outMs: null }, MAIN_TB).ok).toBe(false);
    const inverted = validateRange({ inMs: 100, outMs: 100 }, MAIN_TB);
    expect(inverted.ok).toBe(false);
    if (!inverted.ok) expect(inverted.code).toBe(NLE_CODES.rangeOutBeforeIn);
    const beyondTimeline = validateRange({ inMs: 9500, outMs: 12_000 }, MAIN_TB);
    expect(beyondTimeline.ok).toBe(false);
    if (!beyondTimeline.ok) expect(beyondTimeline.code).toBe(NLE_CODES.rangeOutsideTimeline);
    const beyondSource = validateRange({ inMs: 0, outMs: 500 }, MAIN_TB, { inMs: 0, outMs: 400 });
    expect(beyondSource.ok).toBe(false);
    if (!beyondSource.ok) expect(beyondSource.code).toBe(NLE_CODES.rangeOutsideSource);
    const beforeSource = validateRange({ inMs: 100, outMs: 200 }, MAIN_TB, { inMs: 500, outMs: 900 });
    expect(beforeSource.ok).toBe(false);
    if (!beforeSource.ok) expect(beforeSource.code).toBe(NLE_CODES.rangeBeforeSourceIn);
    const ok = validateRange({ inMs: 100, outMs: 200 }, MAIN_TB);
    expect(ok).toEqual({ ok: true, range: { startMs: 100, endMs: 200, durationMs: 100 }, sourceRangeChecked: false });
    const withSource = validateRange({ inMs: 0, outMs: 400 }, MAIN_TB, { inMs: 0, outMs: 400 });
    expect(withSource.ok && withSource.sourceRangeChecked).toBe(true);
  });
});

describe('轨道头状态：锁、静音与增益范围', () => {
  it('接受原 owner 的增益范围并标出仅音频可调', () => {
    const video = trackHeaderState(MAIN.tracks[0]);
    expect(video.ok).toBe(true);
    if (video.ok) {
      expect(video.header.gainAdjustable).toBe(false);
      expect(video.header.gainDb).toBe(0);
      expect(video.header.clipCount).toBe(2);
      expect(video.header.clipIds).toEqual(['clip-a', 'clip-b']);
      expect(video.header.locked).toBe(false);
      expect([video.header.gainMinDb, video.header.gainMaxDb]).toEqual([-60, 12]);
    }
    const audio = trackHeaderState({ ...MAIN.tracks[1], gain_db: -6 });
    expect(audio.ok).toBe(true);
    if (audio.ok) { expect(audio.header.gainAdjustable).toBe(true); expect(audio.header.gainDb).toBe(-6); }
  });

  it('拒绝越界增益、视频轨道非零增益与畸形轨道', () => {
    const tooLoud = trackHeaderState({ ...MAIN.tracks[1], gain_db: 13 });
    expect(tooLoud.ok).toBe(false);
    if (!tooLoud.ok) expect(tooLoud.code).toBe(NLE_CODES.trackGainOutOfRange);
    const videoGain = trackHeaderState({ ...MAIN.tracks[0], gain_db: 3 });
    expect(videoGain.ok).toBe(false);
    if (!videoGain.ok) expect(videoGain.code).toBe(NLE_CODES.trackGainVideoFixed);
    const badLock = trackHeaderState({ ...MAIN.tracks[1], locked: 'yes' });
    expect(badLock.ok).toBe(false);
    if (!badLock.ok) expect(badLock.code).toBe(NLE_CODES.trackNotFound);
    expect(trackHeaderState({ ...MAIN.tracks[1], extra: 1 }).ok).toBe(false);
    expect(trackHeaderState({ ...MAIN.tracks[1], id: '#' }).ok).toBe(false);
    expect(trackHeaderState(null).ok).toBe(false);
    expect(trackGainState('AUDIO', -60).ok).toBe(true);
    expect(trackGainState('AUDIO', 12).ok).toBe(true);
    expect(trackGainState('AUDIO', 12.5).ok).toBe(false);
    expect(trackGainState('AUDIO', Number.POSITIVE_INFINITY).ok).toBe(false);
    expect(trackGainState('VIDEO', 0).ok).toBe(true);
    expect(trackGainState('VIDEO', 1).ok).toBe(false);
  });
});

describe('编辑指令：只映射原 owner 已实现的操作', () => {
  const clock = (timeline: StudioTimeline) => ({ timeline });

  it('拆分与复制需要作者提供的新片段标识', () => {
    const split = editCommand('split', { ...clock(MAIN), clipId: 'clip-a', atMs: 2000, newClipId: 'clip-new' });
    expect(split.ok).toBe(true);
    if (split.ok) {
      expect(split.op).toBe('clip.split');
      expect(split.payload).toEqual({ op: 'clip.split', clip_id: 'clip-a', at_ms: 2000, new_clip_id: 'clip-new' });
      expect(split.batchBytes).toBeLessThanOrEqual(NLE_OWNER_LIMITS.editBatchBytes);
    }
    const missing = editCommand('split', { ...clock(MAIN), clipId: 'clip-a', atMs: 2000 });
    expect(missing.ok).toBe(false);
    if (!missing.ok) expect(missing.code).toBe(NLE_CODES.editNewIdRequired);
    const atStart = editCommand('split', { ...clock(MAIN), clipId: 'clip-a', atMs: 0, newClipId: 'clip-new' });
    expect(atStart.ok).toBe(false);
    if (!atStart.ok) expect(atStart.code).toBe(NLE_CODES.editSplitOutsideClip);
    const atEnd = editCommand('split', { ...clock(MAIN), clipId: 'clip-a', atMs: 4000, newClipId: 'clip-new' });
    expect(atEnd.ok).toBe(false);
    if (!atEnd.ok) expect(atEnd.code).toBe(NLE_CODES.editSplitOutsideClip);
  });

  it('拆分拒绝不能映射到整数素材入点的位置', () => {
    const slow = singleTimeline({ ...videoClip('clip-slow', 0, 0, 4000), speed_num: 1, speed_den: 2 });
    const fractional = editCommand('split', { timeline: slow, clipId: 'clip-slow', atMs: 1, newClipId: 'clip-new' });
    expect(fractional.ok).toBe(false);
    if (!fractional.ok) expect(fractional.code).toBe(NLE_CODES.editFractionalMs);
    const exact = editCommand('split', { timeline: slow, clipId: 'clip-slow', atMs: 2, newClipId: 'clip-new' });
    expect(exact.ok).toBe(true);
  });

  it('裁剪保留 owner 的 ripple 字段并校验渲染长度', () => {
    const plain = editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 100, outMs: 3000, ripple: false });
    expect(plain.ok).toBe(true);
    if (plain.ok) expect(plain.payload).toEqual({ op: 'clip.trim', clip_id: 'clip-a', in_ms: 100, out_ms: 3000, ripple: false });
    const rippled = editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 100, outMs: 3000, ripple: true });
    expect(rippled.ok).toBe(true);
    if (rippled.ok) expect(rippled.payload).toEqual({ op: 'clip.trim', clip_id: 'clip-a', in_ms: 100, out_ms: 3000, ripple: true });
    const empty = editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 3000, outMs: 3000 });
    expect(empty.ok).toBe(false);
    if (!empty.ok) expect(empty.code).toBe(NLE_CODES.editTrimEmpty);
    const beyond = editCommand('trim', { ...clock(MAIN), clipId: 'clip-b', inMs: 0, outMs: 10_000 });
    expect(beyond.ok).toBe(false);
    if (!beyond.ok) expect(beyond.code).toBe(NLE_CODES.rangeOutsideTimeline);
    const fast = singleTimeline({ ...videoClip('clip-fast', 0, 0, 4), speed_num: 2, speed_den: 1 });
    const fractional = editCommand('trim', { timeline: fast, clipId: 'clip-fast', inMs: 0, outMs: 1 });
    expect(fractional.ok).toBe(false);
    if (!fractional.ok) expect(fractional.code).toBe(NLE_CODES.editFractionalMs);
  });

  it('移动与复制拒绝跨类型轨道和目标越界', () => {
    const moved = editCommand('move', { ...clock(MAIN), clipId: 'clip-a', targetTrackId: 'video-1', startMs: 6000 });
    expect(moved.ok).toBe(true);
    if (moved.ok) expect(moved.payload).toEqual({ op: 'clip.move', clip_id: 'clip-a', track_id: 'video-1', start_ms: 6000 });
    const crossKind = editCommand('move', { ...clock(MAIN), clipId: 'clip-c', targetTrackId: 'video-1', startMs: 0 });
    expect(crossKind.ok).toBe(false);
    if (!crossKind.ok) expect(crossKind.code).toBe(NLE_CODES.editMoveKindInvalid);
    const overflow = editCommand('move', { ...clock(MAIN), clipId: 'clip-a', targetTrackId: 'video-1', startMs: 9000 });
    expect(overflow.ok).toBe(false);
    if (!overflow.ok) expect(overflow.code).toBe(NLE_CODES.rangeOutsideTimeline);
    const copied = editCommand('copy', { ...clock(MAIN), clipId: 'clip-c', targetTrackId: 'video-1', startMs: 7000, newClipId: 'clip-copy-a' });
    expect(copied.ok).toBe(false);
    if (!copied.ok) expect(copied.code).toBe(NLE_CODES.editMoveKindInvalid);
    const copy = editCommand('copy', { ...clock(MAIN), clipId: 'clip-b', targetTrackId: 'video-1', startMs: 7000, newClipId: 'clip-copy' });
    expect(copy.ok).toBe(true);
    if (copy.ok) expect(copy.payload).toEqual({ op: 'clip.duplicate', clip_id: 'clip-b', new_clip_id: 'clip-copy', track_id: 'video-1', start_ms: 7000 });
    const duplicate = editCommand('copy', { ...clock(MAIN), clipId: 'clip-b', targetTrackId: 'video-1', startMs: 7000, newClipId: 'clip-a' });
    expect(duplicate.ok).toBe(false);
    if (!duplicate.ok) expect(duplicate.code).toBe(NLE_CODES.editNewIdRequired);
  });

  it('滑移在静态画面上被拒绝，并遵守素材入出点范围', () => {
    const moved = editCommand('slip', { ...clock(MAIN), clipId: 'clip-a', offsetMs: 200 });
    expect(moved.ok).toBe(true);
    if (moved.ok) expect(moved.payload).toEqual({ op: 'clip.slip', clip_id: 'clip-a', offset_ms: 200 });
    const still = editCommand('slip', { ...clock(MAIN), clipId: 'clip-d', offsetMs: 200 });
    expect(still.ok).toBe(false);
    if (!still.ok) expect(still.code).toBe(NLE_CODES.editStillSlipInvalid);
    const outside = editCommand('slip', { ...clock(MAIN), clipId: 'clip-a', offsetMs: NLE_OWNER_LIMITS.sourceTrimMs });
    expect(outside.ok).toBe(false);
    if (!outside.ok) expect(outside.code).toBe(NLE_CODES.editSlipOutsideSource);
    const ranged = editCommand('slip', { ...clock(MAIN), clipId: 'clip-a', offsetMs: 200, sourceRange: { inMs: 0, outMs: 4100 } });
    expect(ranged.ok).toBe(false);
    if (!ranged.ok) expect(ranged.code).toBe(NLE_CODES.editSlipOutsideSource);
  });

  it('波纹删除必须明确闭合间隙', () => {
    const ripple = editCommand('ripple', { ...clock(MAIN), clipId: 'clip-a', ripple: true });
    expect(ripple.ok).toBe(true);
    if (ripple.ok) expect(ripple.payload).toEqual({ op: 'clip.remove', clip_id: 'clip-a', ripple: true });
    const implicit = editCommand('ripple', { ...clock(MAIN), clipId: 'clip-a' });
    expect(implicit.ok).toBe(false);
    if (!implicit.ok) expect(implicit.code).toBe(NLE_CODES.editKindUnsupported);
    const only = editCommand('ripple', { timeline: singleTimeline(videoClip('clip-only', 0, 0, 1000)), clipId: 'clip-only', ripple: true });
    expect(only.ok).toBe(false);
  });

  it('替换素材使用 owner 的 clip.update 与 source_snapshot', () => {
    const replaced = editCommand('source-replace', { ...clock(MAIN), clipId: 'clip-a',
      sourceSnapshot: { id: 'asset-video-2', kind: 'ASSET', asset_kind: 'video', version: 3, digest: DIGEST } });
    expect(replaced.ok).toBe(true);
    if (replaced.ok) {
      expect(replaced.op).toBe('clip.update');
      expect(replaced.payload).toEqual({ op: 'clip.update', clip_id: 'clip-a',
        changes: { source_snapshot: { id: 'asset-video-2', kind: 'ASSET', asset_kind: 'video', version: 3, digest: DIGEST } } });
    }
    const wrongKind = editCommand('source-replace', { ...clock(MAIN), clipId: 'clip-a',
      sourceSnapshot: { id: 'asset-audio-9', kind: 'ASSET', asset_kind: 'audio', version: 1, digest: DIGEST } });
    expect(wrongKind.ok).toBe(false);
    if (!wrongKind.ok) expect(wrongKind.code).toBe(NLE_CODES.editSourceKindInvalid);
    const badDigest = editCommand('source-replace', { ...clock(MAIN), clipId: 'clip-a',
      sourceSnapshot: { id: 'asset-video-2', kind: 'ASSET', asset_kind: 'video', version: 1, digest: 'zz' } });
    expect(badDigest.ok).toBe(false);
    if (!badDigest.ok) expect(badDigest.code).toBe(NLE_CODES.editSourceKindInvalid);
    expect(editCommand('source-replace', { ...clock(MAIN), clipId: 'clip-a' }).ok).toBe(false);
  });

  it('owner 没有的语义被明确拒绝并给出原因', () => {
    const grade = editCommand('grade', { ...clock(MAIN), clipId: 'clip-a' });
    expect(grade.ok).toBe(false);
    if (!grade.ok) {
      expect(grade.code).toBe(NLE_CODES.editKindUnsupported);
      expect(grade.message).toContain('调色');
    }
    const speed = editCommand('speed', { ...clock(MAIN), clipId: 'clip-a' });
    expect(speed.ok).toBe(false);
    if (!speed.ok) expect(speed.message).toContain('变速');
    const unknown = editCommand('explode', { ...clock(MAIN), clipId: 'clip-a' });
    expect(unknown.ok).toBe(false);
    if (!unknown.ok) expect(unknown.message).toContain('explode');
    expect(editCommand('grade', { ...clock(MAIN), clipId: 'clip-a' }).ok).toBe(false);
  });

  it('锁定轨道、缺失片段与畸形上下文都被拒绝', () => {
    const locked = build([
      track('video-1', 'VIDEO', 0, [videoClip('clip-locked', 0, 0, 1000)], { locked: true }),
      track('audio-1', 'AUDIO', 1, [audioClip('clip-c', 0, 0, 1000)]),
    ]);
    const refusal = editCommand('trim', { ...clock(locked), clipId: 'clip-locked', inMs: 0, outMs: 500 });
    expect(refusal.ok).toBe(false);
    if (!refusal.ok) expect(refusal.code).toBe(NLE_CODES.trackLocked);
    const notFound = editCommand('trim', { ...clock(MAIN), clipId: 'clip-zzz', inMs: 0, outMs: 500 });
    expect(notFound.ok).toBe(false);
    if (!notFound.ok) expect(notFound.code).toBe(NLE_CODES.editClipNotFound);
    expect(editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 0, outMs: 500, sneaky: 1 }).ok).toBe(false);
    expect(editCommand('trim', { clipId: 'clip-a' }).ok).toBe(false);
    expect(editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 0, outMs: 500, targetTrackId: 'ghost' }).ok).toBe(true);
    expect(editCommand('move', { ...clock(MAIN), clipId: 'clip-a', targetTrackId: 'ghost', startMs: 0 }).ok).toBe(false);
  });

  it('每个成功计划的 op 都在原 owner 的操作清单内，且与 payload 自洽', () => {
    const plans = [
      editCommand('split', { ...clock(MAIN), clipId: 'clip-a', atMs: 2000, newClipId: 'clip-new' }),
      editCommand('trim', { ...clock(MAIN), clipId: 'clip-a', inMs: 0, outMs: 3000, ripple: true }),
      editCommand('move', { ...clock(MAIN), clipId: 'clip-a', targetTrackId: 'video-1', startMs: 0 }),
      editCommand('copy', { ...clock(MAIN), clipId: 'clip-a', targetTrackId: 'video-1', startMs: 5000, newClipId: 'clip-copy' }),
      editCommand('slip', { ...clock(MAIN), clipId: 'clip-a', offsetMs: 10 }),
      editCommand('ripple', { ...clock(MAIN), clipId: 'clip-a', ripple: true }),
      editCommand('source-replace', { ...clock(MAIN), clipId: 'clip-a',
        sourceSnapshot: { id: 'asset-video-9', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST } }),
    ];
    expect(plans.every(plan => plan.ok)).toBe(true);
    for (const plan of plans) {
      if (!plan.ok) continue;
      expect(ownerOperationSupported(plan.op)).toBe(true);
      expect(plan.payload.op).toBe(plan.op);
      expect(Object.keys(plan.payload).length).toBeLessThanOrEqual(5);
      expect(plan.batchBytes).toBeLessThanOrEqual(NLE_OWNER_LIMITS.editBatchBytes);
    }
  });

  it('编辑批次上限与原服务一致（1..40 个操作、128000 字节）', () => {
    expect(editBatchState(1, 10).ok).toBe(true);
    expect(editBatchState(40, NLE_OWNER_LIMITS.editBatchBytes).ok).toBe(true);
    expect(editBatchState(0, 10).ok).toBe(false);
    expect(editBatchState(41, 10).ok).toBe(false);
    expect(editBatchState(1, 128_001).ok).toBe(false);
  });
});

describe('时间线读取与片段事实', () => {
  it('safeTimeline 只接受通过原契约校验的时间线，并保留原中文说明', () => {
    const ok = safeTimeline(MAIN);
    expect(ok.ok).toBe(true);
    const broken = safeTimeline({ duration_ms: 10_000, width: 1280, height: 720, fps: 25, tracks: [], captions: [] });
    expect(broken.ok).toBe(false);
    if (!broken.ok) {
      expect(broken.code).toBe(NLE_CODES.timelineInvalid);
      expect(broken.message).toContain('轨道');
    }
    expect(safeTimeline({ schema_version: 3 }).ok).toBe(false);
    expect(safeTimeline(null).ok).toBe(false);
  });

  it('片段事实与选择顺序都来自已校验的时间线', () => {
    const facts = selectedClipFacts(MAIN, ['clip-c', 'clip-a', 'ghost']);
    expect(facts.map(item => item.clip.id)).toEqual(['clip-a', 'clip-c']);
    expect(facts[0].durationMs).toBe(4000);
    expect(facts[0].endMs).toBe(4000);
    expect(facts[0].sourceKind).toBe('video');
    expect(clipFacts(MAIN, 'ghost')).toBeNull();
  });

  it('用量按时间线事实汇总', () => {
    expect(timelineUsage(MAIN)).toEqual({ tracks: 3, clips: 4, durationMs: 10_000, captions: 1, captionCharacters: 3 });
  });
});

describe('字幕轨模型与字幕指令', () => {
  const cues = [{ start_ms: 0, end_ms: 1000, text: '第一句' }, { start_ms: 1200, end_ms: 2000, text: '第二句' }];

  it('没有转录 owner 时转录不可用，手动字幕仍然可用', () => {
    const model = subtitleTrackModel(cues, { durationMs: 10_000 });
    expect(model.cueCount).toBe(2);
    expect(model.characters).toBe(6);
    expect(model.locateReady).toBe(true);
    expect(model.editReady).toBe(true);
    expect(model.manualAvailable).toBe(true);
    expect(model.transcriptionAvailable).toBe(false);
    expect(model.transcriptionCode).toBe(NLE_CODES.subtitleNoTranscriptionOwner);
    expect(model.transcriptionMessage).toContain('没有转录');
    expect(model.limits).toEqual({ captions: 500, captionCharacters: 32_000, sidecarBytes: 192_000 });
  });

  it('导入就绪度复刻原 sidecar 语义（编号、头部、换行、字节）', () => {
    const srt = '1\n00:00:00,000 --> 00:00:01,000\n第一句\n\n2\n00:00:01,200 --> 00:00:02,000\n第二句\n';
    const ready = subtitleTrackModel(cues, { importContent: srt, importFormat: 'SRT' });
    expect(ready.importReady).toBe(true);
    expect(ready.importCode).toBeNull();
    const unnumbered = subtitleTrackModel(cues, { importContent: '00:00:00,000 --> 00:00:01,000\n第一句\n', importFormat: 'SRT' });
    expect(unnumbered.importReady).toBe(false);
    expect(unnumbered.importCode).toBe(NLE_CODES.subtitleNumberedCuesRequired);
    const vtt = subtitleTrackModel(cues, { importContent: 'WEBVTT\n\n1\n00:00:00.000 --> 00:00:01.000\n第一句\n', importFormat: 'VTT' });
    expect(vtt.importReady).toBe(true);
    const noHeader = subtitleTrackModel(cues, { importContent: '1\n00:00:00.000 --> 00:00:01.000\n第一句\n', importFormat: 'VTT' });
    expect(noHeader.importCode).toBe(NLE_CODES.subtitleHeaderInvalid);
    const crlf = subtitleTrackModel(cues, { importContent: '1\n00:00:00,000 --> 00:00:01,000\n第一句\r第二句\n', importFormat: 'SRT' });
    expect(crlf.importCode).toBe(NLE_CODES.subtitleLineEndingsInvalid);
    const huge = subtitleTrackModel(cues, { importContent: 'x'.repeat(200_000), importFormat: 'SRT' });
    expect(huge.importCode).toBe(NLE_CODES.subtitleByteLimit);
    expect(subtitleTrackModel(cues, { importContent: 'x', importFormat: 'ASS' }).importCode).toBe(NLE_CODES.subtitleFormatInvalid);
    expect(subtitleTrackModel(cues).importCode).toBe(NLE_CODES.subtitleFormatInvalid);
  });

  it('导出就绪度与字节估算来自原导出语义', () => {
    const ready = subtitleTrackModel(cues, { durationMs: 10_000, exportFormat: 'SRT' });
    expect(ready.exportReady).toBe(true);
    expect(ready.exportMessage).toContain('2 条');
    expect(subtitleTrackModel(cues, { durationMs: 10_000, exportFormat: 'VTT' }).exportReady).toBe(true);
    expect(subtitleTrackModel(cues, { durationMs: 10_000 }).exportReady).toBe(false);
    const long = subtitleTrackModel([{ start_ms: 0, end_ms: 1000, text: 'x'.repeat(1001) }], { durationMs: 10_000 });
    expect(long.cues[0].problems.join(' ')).toContain('1000 字');
    const manyLines = subtitleTrackModel([{ start_ms: 0, end_ms: 1000, text: Array.from({ length: 9 }, (_, i) => `行${i}`).join('\n') }], { durationMs: 10_000 });
    expect(manyLines.cues[0].problems.join(' ')).toContain('8 行');
  });

  it('超出字幕条数与字数上限时明确标记不可编辑', () => {
    const overload = Array.from({ length: 33 }, (_, index) => ({ start_ms: index, end_ms: index + 1, text: 'x'.repeat(1000) }));
    const model = subtitleTrackModel(overload, { durationMs: 10_000, exportFormat: 'SRT' });
    expect(model.characters).toBe(33_000);
    expect(model.locateReady).toBe(false);
    expect(model.manualAvailable).toBe(false);
    expect(model.exportCode).toBe(NLE_CODES.subtitleCharacterLimit);
  });

  it('字幕指令使用 owner 的 caption.* 操作并在内容非法时拒绝', () => {
    const timeline = build([track('video-1', 'VIDEO', 0, [videoClip('clip-a', 0, 0, 4000)])], [{ start_ms: 0, end_ms: 1000, text: '第一句' }]);
    const insert = captionCommand('caption-insert', { timeline, caption: { start_ms: 2000, end_ms: 3000, text: '第二句' } });
    expect(insert.ok).toBe(true);
    if (insert.ok) {
      expect(insert.op).toBe('caption.insert');
      expect(insert.payload).toEqual({ op: 'caption.insert', caption: { start_ms: 2000, end_ms: 3000, text: '第二句' } });
    }
    const empty = captionCommand('caption-insert', { timeline, caption: { start_ms: 2000, end_ms: 3000, text: '' } });
    expect(empty.ok).toBe(false);
    if (!empty.ok) expect(empty.code).toBe(NLE_CODES.captionShapeInvalid);
    const update = captionCommand('caption-update', { timeline, index: 0, caption: { start_ms: 0, end_ms: 900, text: '改过' } });
    expect(update.ok).toBe(true);
    if (update.ok) expect(update.payload).toEqual({ op: 'caption.update', index: 0, caption: { start_ms: 0, end_ms: 900, text: '改过' } });
    const remove = captionCommand('caption-remove', { timeline, index: 0 });
    expect(remove.ok).toBe(true);
    if (remove.ok) expect(remove.payload).toEqual({ op: 'caption.remove', index: 0 });
    const badIndex = captionCommand('caption-remove', { timeline, index: 5 });
    expect(badIndex.ok).toBe(false);
    if (!badIndex.ok) expect(badIndex.code).toBe(NLE_CODES.captionIndexInvalid);
    expect(captionCommand('caption-explode', { timeline, index: 0 }).ok).toBe(false);
    const styled = captionCommand('caption-insert', { timeline, caption: { start_ms: 0, end_ms: 100, text: '<b>加粗</b>' } });
    expect(styled.ok).toBe(false);
  });
});

describe('按需缩略图与波形：绑定素材与时间线版本，不做 I/O', () => {
  const request = (extra: Record<string, unknown> = {}) => ({
    kind: 'THUMBNAIL', atMs: 1500,
    source: { id: 'asset-video', kind: 'ASSET', asset_kind: 'video', version: 1, digest: DIGEST },
    timelineId: 'timeline-1', timelineVersion: 4, timelineDigest: 'd'.repeat(64), ...extra,
  });

  it('键同时绑定素材版本摘要与时间线版本摘要', () => {
    const first = mediaPreviewRequest(request());
    expect(first.ok).toBe(true);
    if (!first.ok) return;
    expect(first.value.key).toContain('asset-video');
    expect(first.value.key).toContain(DIGEST);
    expect(first.value.key).toContain('timeline-1');
    expect(first.value.key).toContain('d'.repeat(64));
    const nextTimeline = mediaPreviewRequest(request({ timelineVersion: 5 }));
    expect(nextTimeline.ok).toBe(true);
    if (nextTimeline.ok) expect(nextTimeline.value.key).not.toBe(first.value.key);
    const nextAsset = mediaPreviewRequest(request({ source: { id: 'asset-video', kind: 'ASSET', asset_kind: 'video', version: 2, digest: 'e'.repeat(64) } }));
    expect(nextAsset.ok).toBe(true);
    if (nextAsset.ok) expect(nextAsset.value.key).not.toBe(first.value.key);
    expect(mediaPreviewRequest(request({ kind: 'WAVEFORM' })).ok).toBe(true);
  });

  it('没有有效素材或时间线绑定的请求被拒绝', () => {
    expect(mediaPreviewRequest(request({ kind: 'SPECTROGRAM' })).ok).toBe(false);
    expect(mediaPreviewRequest(request({ atMs: -1 })).ok).toBe(false);
    expect(mediaPreviewRequest(request({ source: { id: 'asset-video', kind: 'ASSET', asset_kind: 'video', version: 1, digest: 'zz' } })).ok).toBe(false);
    expect(mediaPreviewRequest(request({ timelineVersion: 0 })).ok).toBe(false);
    expect(mediaPreviewRequest(request({ timelineDigest: 'nope' })).ok).toBe(false);
    expect(mediaPreviewRequest(request({ cache: true })).ok).toBe(false);
    const refused = mediaPreviewRequest(request({ timelineId: '#' }));
    expect(refused.ok).toBe(false);
    if (!refused.ok) expect(refused.code).toBe(NLE_CODES.previewTimelineInvalid);
  });
});

describe('导出状态：预览画质与交付画质分开陈述', () => {
  const preview = (preset: string, extra: Record<string, unknown> = {}) => ({
    contract: 'studio-timeline-export-preview/1', export_profile: { preset },
    preview_digest: 'b'.repeat(64), limits: { max_output_bytes: 25 * 1024 * 1024, render_timeout_seconds: 120 },
    model_called: false, automatic_replay: false, product_acceptance: 'LOCAL_REQUIRED', ...extra,
  });

  it('没有回执时不声明任何画质', () => {
    const status = exportStatus(null);
    expect(status.stage).toBe('NONE');
    expect(status.previewQuality).toBeNull();
    expect(status.finalExportQuality).toBeNull();
    expect(status.deliveryReady).toBe(false);
    expect(status.head).toContain('尚未核对');
  });

  it('审核预览预设只给出预览画质，绝不声明交付成片', () => {
    const status = exportStatus(preview('REVIEW_MP4'));
    expect(status.stage).toBe('PREVIEW_CHECKED');
    expect(status.requestedQuality).toBe('PREVIEW');
    expect(status.previewQuality?.quality).toBe('PREVIEW');
    expect(status.previewQuality?.preset).toBe('REVIEW_MP4');
    expect(status.finalExportQuality).toBeNull();
    expect(status.deliveryReady).toBe(false);
    expect(status.head).not.toContain('成片');
    expect(status.detail).toContain('没有排队');
    expect(status.warnings.some(warning => warning.includes('交付画质'))).toBe(true);
    expect(status.limits).toEqual({ renderTimeoutSeconds: 120, maxOutputBytes: 25 * 1024 * 1024 });
  });

  it('交付预设给出交付画质，但产物仍需人工审核', () => {
    const status = exportStatus(preview('DELIVERY_H264_MP4'));
    expect(status.requestedQuality).toBe('FINAL');
    expect(status.previewQuality).toBeNull();
    expect(status.finalExportQuality?.quality).toBe('FINAL');
    expect(status.finalExportQuality?.preset).toBe('DELIVERY_H264_MP4');
    expect(status.deliveryReady).toBe(false);
    expect(status.warnings.some(warning => warning.includes('LOCAL_REQUIRED'))).toBe(true);
    expect(exportStatus(preview('DELIVERY_VP9_WEBM')).finalExportQuality?.preset).toBe('DELIVERY_VP9_WEBM');
  });

  it('结果不明时保留请求标识且不声明成功', () => {
    const status = exportStatus({ ...preview('DELIVERY_H264_MP4'), state: 'UNKNOWN', request_id: 'req-1' });
    expect(status.stage).toBe('DISPATCHED_UNKNOWN');
    expect(status.requestId).toBe('req-1');
    expect(status.head).toContain('结果不明');
    expect(status.detail).toContain('不会创建替代请求');
    const returned = exportStatus({ ...preview('REVIEW_MP4'), state: 'RETURNED' });
    expect(returned.stage).toBe('RECEIPT_RETURNED');
    expect(returned.deliveryReady).toBe(false);
  });

  it('非法回执被明确标记为不可核对', () => {
    expect(exportStatus(preview('REVIEW_MP4', { model_called: true })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { automatic_replay: true })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { product_acceptance: 'DELIVERED' })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { state: 'SUCCEEDED' })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { sneaky: 1 })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { preview_digest: 'zz' })).code).toBe(NLE_CODES.exportPreviewDigestInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { limits: { max_output_bytes: 26 * 1024 * 1024, render_timeout_seconds: 120 } })).code).toBe(NLE_CODES.exportShapeInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { limits: { max_output_bytes: 1000, render_timeout_seconds: 121 } })).code).toBe(NLE_CODES.exportShapeInvalid);
    const badPreset = exportStatus(preview('REVIEW_MP4', { export_profile: { preset: 'LOSSLEss' } }));
    expect(badPreset.code).toBe(NLE_CODES.exportPresetInvalid);
    expect(exportStatus(preview('REVIEW_MP4', { export_profile: { preset: 'REVIEW_MP4', crf: 20 } })).code).toBe(NLE_CODES.exportPresetInvalid);
    expect(exportStatus(42).code).toBe(NLE_CODES.exportShapeInvalid);
  });
});

describe('上限提示：在触界之前说明，且绝不提高上限', () => {
  it('列出原 owner 的冻结上限', () => {
    const notice = limitsNotice();
    expect(notice.rows.length).toBe(12);
    expect(notice.warnings).toEqual([]);
    expect(notice.nearAny).toBe(false);
    expect(notice.code).toBeNull();
    const owner = (key: string) => notice.rows.find(row => row.key === key)?.ownerLimit;
    expect(owner('tracks')).toBe(8);
    expect(owner('tracks_per_kind')).toBe(4);
    expect(owner('clips')).toBe(30);
    expect(owner('duration_ms')).toBe(600_000);
    expect(owner('captions')).toBe(500);
    expect(owner('caption_characters')).toBe(32_000);
    expect(owner('single_asset_bytes')).toBe(25 * 1024 * 1024);
    expect(owner('total_source_bytes')).toBe(200 * 1024 * 1024);
    expect(owner('render_timeout_seconds')).toBe(120);
    expect(owner('subtitle_sidecar_bytes')).toBe(192_000);
    expect(owner('edit_operations_per_batch')).toBe(40);
    expect(owner('edit_batch_bytes')).toBe(128_000);
    expect(notice.splitAdvice).toContain('不会提高任何上限');
  });

  it('在上限到来之前就给出警告', () => {
    const notice = limitsNotice(null, { tracks: 7, clips: 28, durationMs: 590_000 });
    expect(notice.nearAny).toBe(true);
    expect(notice.reachedAny).toBe(false);
    expect(notice.warnings.some(warning => warning.includes('轨道总数'))).toBe(true);
    expect(notice.warnings.some(warning => warning.includes('片段总数'))).toBe(true);
    expect(notice.rows.find(row => row.key === 'tracks')?.near).toBe(true);
    expect(notice.rows.find(row => row.key === 'tracks')?.reached).toBe(false);
    expect(notice.rows.find(row => row.key === 'tracks')?.remaining).toBe(1);
    expect(notice.rows.find(row => row.key === 'tracks')?.ratio).toBeCloseTo(0.875, 5);
  });

  it('达到上限时如实说明，而不是放宽限制', () => {
    const notice = limitsNotice(null, { tracks: 8, clips: 30 });
    expect(notice.reachedAny).toBe(true);
    expect(notice.rows.find(row => row.key === 'tracks')?.reached).toBe(true);
    expect(notice.warnings.some(warning => warning.includes('已达上限'))).toBe(true);
    const over = limitsNotice(null, { tracks: 12 });
    expect(over.rows.find(row => row.key === 'tracks')?.ownerLimit).toBe(8);
  });

  it('收到更高的上限值时拒绝提高并保留原值', () => {
    const raised = limitsNotice({ tracks: 99, clips: 1000 });
    expect(raised.raiseRefused).toBe(true);
    expect(raised.code).toBe(NLE_CODES.limitsRaiseRefused);
    expect(raised.refusedRaises).toEqual([{ key: 'tracks', offered: 99, ownerLimit: 8 }, { key: 'clips', offered: 1000, ownerLimit: 30 }]);
    expect(raised.rows.find(row => row.key === 'tracks')?.ownerLimit).toBe(8);
    const lower = limitsNotice({ tracks: 4 });
    expect(lower.raiseRefused).toBe(false);
    expect(lower.code).toBeNull();
    expect(lower.rows.find(row => row.key === 'tracks')?.ownerLimit).toBe(8);
  });

  it('畸形上限或用量输入被标记为不可核对', () => {
    expect(limitsNotice({ bogus: 1 }).code).toBe(NLE_CODES.limitsShapeInvalid);
    expect(limitsNotice({ duration_ms: 600_000 }, { bogus: 1 }).code).toBe(NLE_CODES.limitsShapeInvalid);
    expect(limitsNotice({ duration_ms: 600_000 }, { tracks: -1 }).rows.find(row => row.key === 'tracks')?.used).toBeNull();
  });

  it('上限常量与 owner 事实一致', () => {
    expect(NLE_OWNER_LIMITS).toEqual({
      durationMs: 600_000, tracks: 8, tracksPerKind: 4, clips: 30, captions: 500, captionCharacters: 32_000,
      width: 1920, height: 1080, fpsMin: 1, fpsMax: 60, sourceTrimMs: 36_000_000,
      singleAssetBytes: 25 * 1024 * 1024, totalSourceBytes: 200 * 1024 * 1024, renderTimeoutSeconds: 120,
      subtitleSidecarBytes: 192_000, editOperationsPerBatch: 40, editBatchBytes: 128_000, gainMinDb: -60, gainMaxDb: 12,
    });
  });
});
