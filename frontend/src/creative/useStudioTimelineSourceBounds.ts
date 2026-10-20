import { useEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { cloneTimeline, timelineBinding, timelineSourcesCurrent, type StudioTimelineRow } from './studioTimelineTypes';
import { checkedTimelineSourceBounds, timelineSourceBoundsRequest, type TimelineSourceBounds } from './studioTimelineSourceBounds';

export type TimelineSourceBoundsOptions = { props: StudioTimelineEditorProps; source?: StudioTimelineRow; selectedClipIds: readonly string[];
  getSelectionGeneration: () => number; getRevision: () => string; isReady: () => boolean };
type State = { epoch: number; pending?: boolean; preview?: TimelineSourceBounds; error?: string };
const messages: Record<string, string> = {
  STUDIO_WAVEFORM_PCM16_REQUIRED: '此预览仅支持单声道或双声道 PCM16 WAV；MP3、FLAC 和其他编码暂不支持。',
  STUDIO_WAVEFORM_LIMIT: '素材超过源时长预览上限（8 MiB、十分钟）；不会改用其他解码器。',
  STUDIO_WAVEFORM_PLATFORM_UNSUPPORTED: '当前平台无法安全读取源时长文件，此入口暂不支持；Windows 原生验证仍待执行。',
  STUDIO_WAVEFORM_CONTENT_UNAVAILABLE: '源文件不可用或完整性核对失败，无法提供可信时长。',
  STUDIO_WAVEFORM_REQUEST_INVALID: '源时长请求与所选已保存片段不一致，请重新核对。',
  STUDIO_WAVEFORM_INVALID: '源 WAV 文件结构无效，无法提供可信时长。',
  STUDIO_WAVEFORM_CLIP_RANGE_INVALID: '已保存片段的裁剪范围没有有效源采样，请回到原时间线核对。',
  STUDIO_TIMELINE_CHANGED: '已保存时间线版本已变化，请重新读取、核对并采用后再预览。',
  STUDIO_TIMELINE_SOURCE_CHANGED: '所选片段的素材版本已变化，请重新核对；预览不会刷新素材绑定。',
};
/** One explicit ephemeral read. No playback, mutation gate, cache, history or source adoption. */
export function useStudioTimelineSourceBounds(options: TimelineSourceBoundsOptions) {
  const latest = useRef(options); latest.current = options;
  const alive = useRef(true), deniedClient = useRef<StudioTimelineEditorProps['client']>();
  const active = useRef<{ epoch: number; abort: AbortController }>();
  const epoch = useRef(0), previous = useRef<{ client: StudioTimelineEditorProps['client']; key: string }>();
  const [state, setState] = useState<State>({ epoch: 0 });
  const revision = options.getRevision(), selectionGeneration = options.getSelectionGeneration();
  const source = options.source, clipId = options.selectedClipIds.length === 1 ? options.selectedClipIds[0] : undefined;
  let selected = '';
  try { if (source && clipId) selected = JSON.stringify(timelineSourceBoundsRequest(source, clipId)); } catch { /* Unsupported selection stays disabled. */ }
  const ready = options.isReady() && options.props.isCurrent() && options.props.canMutate && !options.props.busy && !options.props.isBusy?.()
    && deniedClient.current !== options.props.client && !!source && timelineSourcesCurrent(source.timeline, options.props.assets);
  const available = !!options.props.client.timelineSourceBounds;
  const key = JSON.stringify([revision, selectionGeneration, options.selectedClipIds, options.props.projectId, ready, available,
    source ? timelineBinding(source) : '', selected]);
  if (!previous.current || previous.current.client !== options.props.client || previous.current.key !== key) {
    epoch.current++; active.current?.abort.abort(); active.current = undefined;
    previous.current = { client: options.props.client, key };
  }
  const renderEpoch = epoch.current, client = options.props.client;
  useEffect(() => {
    setState(value => value.epoch === renderEpoch ? value : { epoch: renderEpoch });
  }, [renderEpoch]);
  useEffect(() => { alive.current = true; return () => { alive.current = false; active.current?.abort.abort(); active.current = undefined; }; }, []);
  function current() {
    const live = latest.current;
    try { return alive.current && epoch.current === renderEpoch && live.props.client === client && deniedClient.current !== client
      && live.props.isCurrent() && live.props.canMutate && !live.props.busy && !live.props.isBusy?.() && live.isReady()
      && live.getRevision() === revision && live.getSelectionGeneration() === selectionGeneration
      && JSON.stringify(live.selectedClipIds) === JSON.stringify(options.selectedClipIds)
      && !!source && !!live.source && timelineBinding(live.source) === timelineBinding(source)
      && timelineSourcesCurrent(source.timeline, live.props.assets)
      && !!clipId && JSON.stringify(timelineSourceBoundsRequest(live.source, clipId)) === selected;
    } catch { return false; }
  }
  async function request() {
    // This closure belongs to this rendered selection, not whichever selection exists later.
    if (!available || !selected || !ready || !current() || active.current || !source || !clipId) return;
    const snapshot = cloneTimeline(source), method = client.timelineSourceBounds!;
    const attempt = { epoch: renderEpoch, abort: new AbortController() }; active.current = attempt;
    const owns = () => active.current === attempt && !attempt.abort.signal.aborted && current();
    setState({ epoch: renderEpoch, pending: true });
    try {
      const raw = await latest.current.props.read(async () => {
        try {
          if (!owns()) throw new DOMException('源时长读取已取消。', 'AbortError');
          return await method(snapshot, clipId, attempt.abort.signal);
        } catch (reason) {
          // The original workspace guard must see active authorization failures,
          // but an aborted old selection must not revoke a newer workspace view.
          if (!owns()) throw new DOMException('源时长读取已取消。', 'AbortError');
          throw reason;
        }
      });
      if (!owns()) return;
      const preview = checkedTimelineSourceBounds(raw, snapshot, clipId, latest.current.props.projectId
        ? { novelId: latest.current.props.projectId } : undefined);
      setState({ epoch: renderEpoch, preview });
    } catch (reason) {
      if (!owns()) return;
      if (reason instanceof ApiError && [401, 403].includes(reason.status)) {
        deniedClient.current = client; setState({ epoch: renderEpoch }); latest.current.props.onUnavailable(); return;
      }
      const code = reason instanceof ApiError ? (Object.hasOwn(messages, reason.problem.code) ? reason.problem.code
        : Object.hasOwn(messages, reason.message) ? reason.message : '') : '';
      setState({ epoch: renderEpoch, error: code ? messages[code] : '源时长读取失败，请核对后明确重试。' });
    } finally {
      if (active.current === attempt) {
        active.current = undefined;
        if (alive.current && epoch.current === renderEpoch) setState(value => value.epoch === renderEpoch ? { ...value, pending: false } : value);
      }
    }
  }
  const visible = state.epoch === renderEpoch && ready;
  return { available, canRequest: ready && !!selected && available && !active.current, pending: visible && !!state.pending,
    preview: visible ? state.preview : undefined, error: visible ? state.error ?? '' : '', request,
    unavailable: !available ? '当前客户端未提供源时长入口。' : !selected ? '请选择一个已保存的音频片段以核对源时长。'
      : !ready ? '请先保存或核对当前时间线，并等待其他操作完成。' : '' };
}
export type StudioTimelineSourceBoundsController = ReturnType<typeof useStudioTimelineSourceBounds>;
