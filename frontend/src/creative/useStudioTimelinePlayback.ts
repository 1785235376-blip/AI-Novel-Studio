import { useStudioProductionLeaveRisk } from './studioProductionLeaveRisk';
import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import type { ProductionJob } from './studioProductionClient';
import { timelinePlaybackMediaType, playbackJobMatches, type TimelinePlayback } from './studioTimelinePlaybackTypes';
import { AUDIO_TIMELINE_MAX_WAV_DURATION_MS } from './studioTimelineExportTypes';
import { timelineBinding, timelineSourcesCurrent, type StudioTimelineRow } from './studioTimelineTypes';

type Options = { props: StudioTimelineEditorProps; source?: StudioTimelineRow; isReady: () => boolean;
  onGateChange: (value: boolean) => void; onAuthorityLost: () => void };
type Entry = { mediaType?: 'audio/wav' | 'video/mp4'; key: string; url: string; bytes: number; digest: string; jobVersion: number; source: StudioTimelineRow; durationMs: number };
type Attempt = { source: StudioTimelineRow; preview: TimelinePlayback };
/** Private two-entry/50MiB encoded-file cache. Original exports remain their owner. */
export function useStudioTimelinePlayback(options: Options) {
  const [preview, setPreview] = useState<TimelinePlayback>(), [confirmed, setConfirmed] = useState(false);
  const [pending, setPending] = useState<'PREVIEW' | 'BUILD' | 'READ' | 'BLOB'>(), [unknown, setUnknown] = useState<Attempt>();
  const [visible, setVisible] = useState<Entry>(), [positionMs, setPositionMs] = useState(0);
  const [error, setError] = useState(''), [notice, setNotice] = useState('');
  const [auxiliary, setAuxiliary] = useState<'READ' | 'CANCEL'>();
  const latest = useRef(options); latest.current = options;
  const owner = useRef(options.props.client), alive = useRef(true), epoch = useRef(0), busy = useRef(false);
  const attempt = useRef<Attempt>(), consent = useRef(''), view = useRef<Entry>(), proof = useRef<TimelinePlayback>();
  const cache = useRef(new Map<string, Entry>()), reading = useRef<AbortController>();
  const auxiliaryBusy = useRef(false), versions = useRef(new Map<string, number>());
  const current = () => alive.current && owner.current === latest.current.props.client && latest.current.props.isCurrent();
  const owns = owner.current === options.props.client && options.props.isCurrent();
  const leaveGuard = useStudioProductionLeaveRisk(options.props.leaveGuard, () => ({ unknown: !!attempt.current || proof.current?.job?.status === 'UNKNOWN',
    requests: !!attempt.current || proof.current?.job?.status === 'UNKNOWN' ? [{ requestId: attempt.current?.preview.request_id ?? proof.current!.request_id, owner: 'timeline', operationId: 'm9.timeline.multitrack' }] : [] }));
  const available = !!options.props.client.timelinePlaybackPreview && !!options.props.client.timelinePlaybackBuild && !!options.props.client.timelinePlaybackAttestation;
  function clearVisible() { view.current = undefined; setVisible(undefined); setPositionMs(0); }
  function dropCache() { cache.current.forEach(entry => URL.revokeObjectURL(entry.url)); cache.current.clear(); clearVisible(); }
  function reset() { epoch.current++; reading.current?.abort(); reading.current = undefined; busy.current = false;
    attempt.current = undefined; consent.current = ''; proof.current = undefined; dropCache(); setPending(undefined); setUnknown(undefined);
    versions.current.clear(); auxiliaryBusy.current = false; setAuxiliary(undefined);
    setPreview(undefined); setConfirmed(false); setError(''); setNotice(''); latest.current.onGateChange(false); }
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; reading.current?.abort();
    cache.current.forEach(entry => URL.revokeObjectURL(entry.url)); cache.current.clear(); latest.current.onGateChange(false); }; }, []);
  useEffect(() => { owner.current = options.props.client; reset(); }, [options.props.client]);
  useEffect(() => { if (!owns) reset(); }, [owns]);
  const binding = options.source ? timelineBinding(options.source) : '';
  useEffect(() => { clearVisible(); consent.current = ''; proof.current = undefined; setConfirmed(false); setPreview(undefined);
    if (busy.current || auxiliaryBusy.current || attempt.current) return;
    epoch.current++; reading.current?.abort(); }, [binding]);
  useEffect(() => {
    for (const [key, entry] of cache.current) if (!timelineSourcesCurrent(entry.source.timeline, options.props.assets)) {
      URL.revokeObjectURL(entry.url); cache.current.delete(key); if (view.current?.key === key) clearVisible();
    }
    if (!options.props.canMutate || !owns) { epoch.current++; reading.current?.abort(); busy.current = false; setPending(undefined);
      auxiliaryBusy.current = false; setAuxiliary(undefined);
      latest.current.onGateChange(!!attempt.current); dropCache(); consent.current = ''; proof.current = undefined; setPreview(undefined); setConfirmed(false); }
  }, [options.props.assets, options.props.canMutate, owns]);
  function begin(kind: NonNullable<typeof pending>, recovering = false) {
    if (!current() || busy.current || auxiliaryBusy.current || !available || !recovering && (!latest.current.isReady() || attempt.current)) return;
    busy.current = true; latest.current.onGateChange(true); setPending(kind); setError(''); setNotice('');
    return { token: ++epoch.current, client: owner.current };
  }
  const active = (request: { token: number; client: typeof owner.current }) => current() && request.token === epoch.current && request.client === owner.current;
  function sourceCurrent(source: StudioTimelineRow) { return current() && latest.current.props.canMutate && !!latest.current.source
    && timelineBinding(latest.current.source) === timelineBinding(source) && timelineSourcesCurrent(source.timeline, latest.current.props.assets); }
  function finish(request: { token: number; client: typeof owner.current }) { if (request.token !== epoch.current) return;
    busy.current = false; latest.current.onGateChange(auxiliaryBusy.current || !!attempt.current); if (active(request)) setPending(undefined); }
  function fail(reason: unknown) { if (reason instanceof ApiError && [401, 403].includes(reason.status)) { leaveGuard?.capture(); reset(); latest.current.onAuthorityLost(); return; }
    // A failed source/candidate check cannot leave previously readable bytes
    // on screen. Keep the original in-flight identity and UNKNOWN for recovery.
    dropCache(); consent.current = ''; proof.current = undefined; setPreview(undefined); setConfirmed(false);
    setError(apiErrorView(reason, '播放缓存操作失败，请读取原任务核对，勿重复生成。').message);
    if (reason instanceof ApiError && [404, 410, 501].includes(reason.status)) latest.current.props.onUnavailable(); }
  function adoptProof(value: TimelinePlayback) {
    if (value.job) { const prior = versions.current.get(value.job.id) ?? 0;
      if (value.job.version < prior) throw new Error('晚到回执低于已观察的原任务版本，请重新读取。');
      versions.current.set(value.job.id, value.job.version); }
    proof.current = value; setPreview(value); consent.current = ''; setConfirmed(false);
  }
  async function previewPlayback() {
    const source = latest.current.source, method = latest.current.props.client.timelinePlaybackPreview;
    if (!source || !method) return;
    if (source.timeline.schema_version === 3 && source.timeline.duration_ms > AUDIO_TIMELINE_MAX_WAV_DURATION_MS) { setError('当前音频时间线超出固定 WAV 的 25 MiB 上限，请缩短至 136533 毫秒以内并保存。'); return; }
    const request = begin('PREVIEW'); if (!request) return;
    const abort = new AbortController(); reading.current = abort; clearVisible();
    try { const value = await latest.current.props.mutate(() => latest.current.props.read(() => method(source, abort.signal)));
      if (!active(request) || !sourceCurrent(source)) return; adoptProof(value);
      setNotice(value.job ? '已读取同一原缓存任务；不会重新编码。核对后可载入已存在的候选。' : value.export_preview.export_profile.preset === 'AUDIO_WAV_PCM16' ? '尚无原缓存任务。确认后才执行一次本地 PCM16 WAV 渲染。' : '尚无原缓存任务。确认后才执行一次本地 H.264/AAC 渲染。');
    } catch (reason) { if (active(request)) fail(reason); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  async function buildPlayback() {
    const source = latest.current.source, value = proof.current, method = latest.current.props.client.timelinePlaybackBuild;
    if (!source || !value || !method || value.job || consent.current !== value.playback_digest) return;
    const request = begin('BUILD'); if (!request) return;
    const saved = { source, preview: value }; attempt.current = saved; setUnknown(saved); clearVisible();
    try { const result = await latest.current.props.mutate(() => method(source, value));
      if (!active(request) || !sourceCurrent(source)) return;
      adoptProof(result); attempt.current = undefined; setUnknown(undefined); if (result.job) latest.current.props.onJob(result.job);
      setNotice('原渲染回执已读取。请核对状态并明确载入候选；没有自动播放或审核。');
    } catch (reason) { if (active(request)) fail(reason); }
    finally { finish(request); }
  }
  async function readOriginal() {
    const saved = attempt.current, source = saved?.source ?? latest.current.source;
    const method = latest.current.props.client.timelinePlaybackPreview; if (!source || !method) return;
    if (saved) {
      if (!current() || auxiliaryBusy.current) return;
      auxiliaryBusy.current = true; latest.current.onGateChange(true); setAuxiliary('READ'); const client = owner.current, token = epoch.current;
      try { const job = await client.get('timeline', saved.preview.job_id);
        if (!current() || owner.current !== client || epoch.current !== token) return;
        if (!playbackJobMatches(job, saved.preview)) throw new Error('读取未证明本次请求的原任务，继续保留 UNKNOWN。');
        const observed = { ...saved.preview, job, cache_state: 'RECORDED' as const };
        if (sourceCurrent(source)) adoptProof(observed);
        else { proof.current = undefined; setPreview(undefined); consent.current = ''; setConfirmed(false); }
        attempt.current = undefined; setUnknown(undefined); latest.current.props.onJob(job);
        setNotice('已核对本次请求的原任务。状态以原 owner 为准；来源改变时不会采用旧播放结果。');
      } catch (reason) { if (current() && owner.current === client && epoch.current === token) fail(reason); }
      finally { if (owner.current === client && epoch.current === token) { auxiliaryBusy.current = false; setAuxiliary(undefined);
        latest.current.onGateChange(busy.current || !!attempt.current); } }
      return;
    }
    const request = begin('READ', true); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try { const result = await latest.current.props.read(() => method(source, abort.signal));
      if (!active(request) || !sourceCurrent(source)) return;
      if (result.job) { attempt.current = undefined; setUnknown(undefined); latest.current.props.onJob(result.job); }
      adoptProof(result); setNotice('只读取原任务，没有编码、重试或自动核对候选。');
    } catch (reason) { if (active(request)) fail(reason); }
    finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  async function loadPlayback() {
    const source = latest.current.source, value = proof.current, job = value?.job;
    const attest = latest.current.props.client.timelinePlaybackAttestation;
    if (!source || !value || !attest || !job?.output_candidate || !['SUCCEEDED', 'AWAITING_REVIEW', 'APPROVED'].includes(job.status)
      || consent.current !== value.playback_digest) return;
    const request = begin('BLOB'); if (!request) return;
    clearVisible();
    try { await latest.current.props.mutate(async () => {
      // Re-read the original receipt before reusing private browser bytes.
      const latestJob = await request.client.get('timeline', value.job_id);
      if (!playbackJobMatches(latestJob, value) || latestJob.version !== job.version || !latestJob.output_candidate
        || latestJob.output_candidate.digest !== job.output_candidate!.digest
        || !['SUCCEEDED', 'AWAITING_REVIEW', 'APPROVED'].includes(latestJob.status)) throw new Error('原缓存任务已经变化，请重新读取。');
      // Every reuse crosses the original candidate source/byte/permission fence,
      // not merely a task GET. The server does not encode or send cached bytes.
      const attestation = await attest(source, value);
      if (attestation.sha256 !== latestJob.output_candidate.digest || attestation.byte_count !== latestJob.media_measurement?.byte_count)
        throw new Error('原候选读取证明已经变化，请重新核对。');
      if (!active(request) || !sourceCurrent(source)) return;
      let entry = cache.current.get(value.cache_key);
      if (entry && (entry.digest !== latestJob.output_candidate.digest || entry.jobVersion !== latestJob.version)) {
        URL.revokeObjectURL(entry.url); cache.current.delete(value.cache_key); entry = undefined;
      }
      if (!entry) {
        const blob = await request.client.candidate(latestJob);
        if (blob.type !== timelinePlaybackMediaType(value) || !blob.size || blob.size > 25 * 1024 * 1024
          || blob.size !== latestJob.media_measurement?.byte_count) throw new Error('缓存候选的类型或容量证明不完整。');
        const hash = Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256', await blob.arrayBuffer())), byte => byte.toString(16).padStart(2, '0')).join('');
        if (hash !== latestJob.output_candidate.digest) throw new Error('缓存候选的实际摘要不一致。');
        if (!active(request) || !sourceCurrent(source)) return;
        entry = { mediaType: timelinePlaybackMediaType(value), key: value.cache_key, url: URL.createObjectURL(blob), bytes: blob.size, digest: hash,
          jobVersion: latestJob.version, source, durationMs: source.timeline.duration_ms };
      }
      cache.current.delete(entry.key); cache.current.set(entry.key, entry);
      while (cache.current.size > 2 || Array.from(cache.current.values()).reduce((sum, row) => sum + row.bytes, 0) > 50 * 1024 * 1024) {
        const oldest = cache.current.entries().next().value as [string, Entry] | undefined; if (!oldest) break;
        URL.revokeObjectURL(oldest[1].url); cache.current.delete(oldest[0]);
      }
      if (!active(request) || !sourceCurrent(source)) return;
      view.current = entry; setVisible(entry); setPositionMs(0); setNotice('实际字节与原候选摘要已核对。可手动播放、暂停和拖动定位；尚未审核。');
    }); } catch (reason) { if (active(request)) fail(reason); }
    finally { finish(request); }
  }
  async function cancelOriginal() {
    const value = proof.current ?? attempt.current?.preview;
    if (!value || !current() || !latest.current.props.canMutate || auxiliaryBusy.current) return;
    auxiliaryBusy.current = true; latest.current.onGateChange(true); setAuxiliary('CANCEL'); const client = owner.current, token = epoch.current;
    try { const job = await client.get('timeline', value.job_id);
      if (!current() || client !== owner.current || epoch.current !== token) return;
      if (!playbackJobMatches(job, value) || !['QUEUED', 'RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(job.status))
        throw new Error('原任务状态已改变，不能按旧状态取消。');
      const cancelled = await client.cancel(job);
      if (!current() || client !== owner.current || epoch.current !== token) return;
      if (!playbackJobMatches(cancelled, value) || cancelled.status !== 'CANCELLED' || cancelled.version <= job.version)
        throw new Error('取消回执未证明原任务已进入取消状态，请读取核对。');
      const source = attempt.current?.source ?? latest.current.source;
      if (source && sourceCurrent(source)) adoptProof({ ...value, job: cancelled, cache_state: 'RECORDED' });
      attempt.current = undefined; setUnknown(undefined);
      clearVisible(); latest.current.props.onJob(cancelled); setNotice('原 owner 已记录 CANCELLED；执行围栏会停止本地进程，原候选与证据保留。');
    } catch (reason) { if (current() && owner.current === client && epoch.current === token) fail(reason); }
    finally { if (owner.current === client && epoch.current === token) { auxiliaryBusy.current = false; setAuxiliary(undefined);
      latest.current.onGateChange(busy.current || !!attempt.current); } }
  }
  const visibleCurrent = owns && options.props.canMutate && visible && sourceCurrent(visible.source) ? visible : undefined;
  return { available, preview: owns && options.props.canMutate ? preview : undefined, visible: visibleCurrent, positionMs: visibleCurrent ? positionMs : 0,
    pending, unknown: owns ? unknown : undefined, error: owns ? error : '', notice: owns ? notice : '',
    locked: busy.current || auxiliaryBusy.current || !!unknown, dirty: owns && (!!pending || !!unknown || !!auxiliary || confirmed),
    canOperate: owns && available && !busy.current && !auxiliaryBusy.current && !unknown && options.isReady(), confirmed,
    previewPlayback, buildPlayback, readOriginal, loadPlayback, cancelOriginal, auxiliary,
    canReadDuringBuild: owns && !!unknown && !auxiliaryBusy.current,
    canCancel: owns && options.props.canMutate && !auxiliaryBusy.current && !!(proof.current ?? attempt.current?.preview)
      && (!preview?.job || ['QUEUED', 'RUNNING', 'UNKNOWN', 'SUCCEEDED', 'AWAITING_REVIEW'].includes(preview.job.status)),
    setConfirmed: (value: boolean) => { if (!current() || busy.current || auxiliaryBusy.current || attempt.current || !proof.current) return;
      consent.current = value ? proof.current.playback_digest : ''; setConfirmed(value); },
    reportPosition: (key: string, seconds: number) => { if (!current() || view.current?.key !== key || !sourceCurrent(view.current.source)
      || !Number.isFinite(seconds)) return; setPositionMs(Math.min(view.current.durationMs, Math.max(0, Math.round(seconds * 1000)))); },
    reportMediaError: (key: string) => { if (!current() || view.current?.key !== key) return; dropCache(); setError('本地播放解码失败，已撤销播放缓存；原任务和证据保留。'); },
    clear: () => { if (current() && !busy.current && !auxiliaryBusy.current && !attempt.current) reset(); } };
}
export type StudioTimelinePlaybackController = ReturnType<typeof useStudioTimelinePlayback>;
