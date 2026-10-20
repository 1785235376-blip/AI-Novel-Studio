import { useLayoutEffect, useRef, useState } from 'react';
import { ApiError } from '../api';
import { Button, StatusMessage } from '../ui/primitives';
import { Details, Field } from '../experimental/shared';
import type { StoryboardReceipt } from './studioStoryboardContract';
import type { StoryboardProductionProps } from './useStoryboardProductionController';
import { useStudioProductionLeaveRisk } from './studioProductionLeaveRisk';
import type { VideoTimelineClip, VideoTimelineCreate, VideoTimelineCreation, VideoTimelineInput, VideoTimelinePreview } from './storyboardVideoTimelineClient';
type Props = { owner: StoryboardProductionProps; receipt: StoryboardReceipt; blocked: boolean; onDirty: (value: boolean) => void };
type Reviewed = { shown: VideoTimelinePreview; body: VideoTimelineInput; receipt: StoryboardReceipt; ticket: object; lease: object };
type Attempt = { reviewed: Reviewed; body: VideoTimelineCreate };
export function StoryboardVideoTimeline({ owner: props, receipt, blocked, onDirty }: Props) {
  const live = useRef({ props, receipt, blocked }); live.current = { props, receipt, blocked };
  const identity = JSON.stringify([props.document.id, props.document.version, receipt, props.active, props.editable, props.isCurrent()]);
  const fence = useRef({ client: props.client, identity, token: {} });
  const changed = fence.current.client !== props.client || fence.current.identity !== identity;
  if (changed) fence.current = { client: props.client, identity, token: {} };
  const editRef = useRef({}), edit = editRef.current;
  const token = fence.current.token, flight = useRef<object>(), alive = useRef(true);
  const externalBusy = !flight.current && (blocked || props.busy || props.isBusy());
  const action = useRef({ token, busy: externalBusy, lease: {} });
  if (action.current.token !== token || action.current.busy !== externalBusy) action.current = { token, busy: externalBusy, lease: {} };
  const lease = action.current.lease;
  const [clips, updateClips] = useState<VideoTimelineClip[]>([]), clipsRef = useRef(clips);
  const [title, setTitle] = useState(`${props.document.title.slice(0, 210)} · 视频剪辑底稿`);
  const [reviewed, updateReviewed] = useState<Reviewed>(), reviewedRef = useRef<Reviewed>();
  const [consent, updateConsent] = useState<object>(), consentRef = useRef<object>();
  const [attempt, updateAttempt] = useState<Attempt>(), attemptRef = useRef<Attempt>();
  const [created, setCreated] = useState<{ owner: object; value: VideoTimelineCreation; intent: Attempt }>();
  const [busy, setBusy] = useState(false), [unknown, setUnknown] = useState(false), unknownRef = useRef(false), [error, setError] = useState('');
  const leave = useStudioProductionLeaveRisk(undefined, () => ({ unknown: !!attemptRef.current && (unknownRef.current || !!flight.current),
    requests: attemptRef.current ? [{ requestId: attemptRef.current.body.request_id, owner: 'timeline', operationId: 'storyboard.video.timeline.create' }] : [] }));
  if (changed && attemptRef.current) leave?.capture();
  const current = () => alive.current && fence.current.token === token && live.current.props.active && live.current.props.editable && live.current.props.isCurrent()
    && live.current.receipt.approved && live.current.receipt.document_snapshot.id === live.current.props.document.id
    && live.current.receipt.document_snapshot.version === live.current.props.document.version;
  const canChange = () => current() && !live.current.blocked && !live.current.props.busy && !live.current.props.isBusy() && !flight.current && !attemptRef.current;
  const canEdit = () => canChange() && editRef.current === edit;
  const setReviewed = (value?: Reviewed) => { reviewedRef.current = value; updateReviewed(value); consentRef.current = undefined; updateConsent(undefined); };
  const setClips = (value: VideoTimelineClip[]) => { editRef.current = {}; clipsRef.current = value; updateClips(value); setReviewed(); };
  const setAttempt = (value?: Attempt) => { attemptRef.current = value; updateAttempt(value); };
  const setUncertain = (value: boolean) => { unknownRef.current = value; setUnknown(value); };
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; onDirty(false); }; }, []);
  useLayoutEffect(() => { flight.current = undefined; setClips([]); setAttempt(); setCreated(undefined); setBusy(false); setUncertain(false); setError('');
    setTitle(`${props.document.title.slice(0, 210)} · 视频剪辑底稿`); }, [token]);
  useLayoutEffect(() => { onDirty(clips.length > 0 || !!attempt || busy); }, [clips, attempt, busy, onDirty]);
  function failure(reason: unknown) {
    setError(reason instanceof ApiError ? reason.message : '未能确认原时间线结果，请保留请求并核对。');
    if (reason instanceof ApiError && [401, 403].includes(reason.status)) { leave?.capture(); props.onDenied(); }
  }
  async function inspect() {
    if (!canEdit() || !clipsRef.current.length || clipsRef.current.length > 4 || !title.trim()) return;
    const operation = {}; flight.current = operation; setBusy(true); setReviewed(); setError('');
    const body: VideoTimelineInput = { expected_version: receipt.document_snapshot.version, reviewed_content_digest: receipt.content_digest,
      title, clips: structuredClone(clipsRef.current), width: 1280, height: 720, fps: 24 };
    try {
      const shown = await props.perform(() => { if (!current() || flight.current !== operation) throw new Error('retired'); return props.client.storyboardVideoTimelinePreview(receipt, body); });
      if (current() && action.current.lease === lease && flight.current === operation) setReviewed({ shown, body, receipt: structuredClone(receipt), ticket: {}, lease });
    } catch (reason) { if (current() && flight.current === operation) failure(reason); }
    finally { if (current() && flight.current === operation) { flight.current = undefined; setBusy(false); } }
  }
  async function create(box: Reviewed, grant: object | undefined) {
    if (!canChange() || box !== reviewedRef.current || box.lease !== action.current.lease || !grant || consentRef.current !== grant) return;
    const intent = { reviewed: box, body: { ...structuredClone(box.body), request_id: crypto.randomUUID(), preview_digest: box.shown.preview_digest } };
    setAttempt(intent); await submit(intent, false);
  }
  async function submit(intent: Attempt, recovery: boolean, retry = false) {
    if (!current() || flight.current || live.current.blocked || live.current.props.busy || live.current.props.isBusy() || attemptRef.current !== intent
      || (retry && lease !== action.current.lease)) return;
    const operation = {}; flight.current = operation; setBusy(true); setError('');
    try {
      const value = await props.perform(() => {
        if (!current() || flight.current !== operation || attemptRef.current !== intent) throw new Error('retired');
        return recovery ? props.client.storyboardVideoTimelineCreation(intent.reviewed.receipt, intent.body, intent.reviewed.shown)
          : props.client.storyboardVideoTimelineCreate(intent.reviewed.receipt, intent.body, intent.reviewed.shown);
      });
      if (current() && flight.current === operation) { setCreated({ owner: token, value, intent }); setAttempt(); setUncertain(false); setClips([]); }
    } catch (reason) {
      if (current() && flight.current === operation) {
        if (!recovery && reason instanceof ApiError && [409, 422].includes(reason.status)) { setAttempt(); setReviewed(); setUncertain(false); }
        else setUncertain(true);
        failure(reason);
      }
    } finally { if (current() && flight.current === operation) { flight.current = undefined; setBusy(false); } }
  }
  const visible = reviewed?.lease === lease ? reviewed : undefined, result = created?.owner === token ? created.value : undefined;
  const disabled = busy || externalBusy || !current() || !!attempt || !receipt.approved;
  const eligible = receipt.shots.filter(shot => !!shot.video_result);
  return <section className="experimental-section" aria-label="已审核视频建立分镜时间线">
    <h3>已审核视频 → 分镜剪辑底稿</h3><p>明确选择同一分镜的 1–4 个正式视频，无需图片。选择顺序即剪辑顺序；留空出点使用真实解码的完整时长。默认不带原音轨。创建只保存原 Timeline，不渲染、不执行模型。</p>
    {error && <StatusMessage tone="error">{error}</StatusMessage>}
    <Field label="视频底稿标题"><input value={title} maxLength={240} disabled={disabled} onChange={event => { if (canEdit()) { editRef.current = {}; setTitle(event.target.value); setReviewed(); } }} /></Field>
    {eligible.map(shot => <label key={shot.shot_id}><input type="checkbox" disabled={disabled || clips.length >= 4 && !clips.some(clip => clip.shot_id === shot.shot_id)} checked={clips.some(clip => clip.shot_id === shot.shot_id)} onChange={event => {
      if (!canEdit()) return; const old = clipsRef.current;
      if (event.target.checked) { if (old.length >= 4 || old.some(clip => clip.shot_id === shot.shot_id)) return;
        setClips([...old, { shot_id: shot.shot_id, shot_version: shot.shot_version, shot_digest: shot.shot_digest, in_ms: 0, out_ms: null, include_audio: false }]); }
      else setClips(old.filter(clip => clip.shot_id !== shot.shot_id));
    }} />选择正式视频 SHOT {shot.shot.number} · {shot.shot_id}</label>)}
    {!eligible.length && <p>当前回执没有正式已审核且已绑定的视频。</p>}
    {clips.map((clip, index) => <fieldset key={clip.shot_id} disabled={disabled}><legend>顺序 {index + 1} · {clip.shot_id}</legend>
      <Button disabled={disabled || index === 0} onClick={() => { if (canEdit()) { const next = [...clipsRef.current]; [next[index-1],next[index]]=[next[index],next[index-1]]; setClips(next); } }}>上移 {clip.shot_id}</Button>
      <Field label={`入点毫秒 ${clip.shot_id}`}><input type="number" min={0} value={clip.in_ms} onChange={event => { if (canEdit() && event.target.value !== '') setClips(clipsRef.current.map(value => value.shot_id === clip.shot_id ? { ...value, in_ms: Number(event.target.value) } : value)); }} /></Field>
      <Field label={`出点毫秒 ${clip.shot_id}`}><input type="number" min={1} placeholder="留空使用完整视频" value={clip.out_ms ?? ''} onChange={event => { if (canEdit()) setClips(clipsRef.current.map(value => value.shot_id === clip.shot_id ? { ...value, out_ms: event.target.value === '' ? null : Number(event.target.value) } : value)); }} /></Field>
    </fieldset>)}
    <Button disabled={disabled || !clips.length || !title.trim()} onClick={() => void inspect()}>解码并预览视频底稿</Button>
    {visible && !attempt && <section aria-label="视频底稿顺序裁切与来源预览"><Details label="分镜版本与摘要" value={visible.shown.document_snapshot} open />
      {visible.shown.clips.map((clip, index) => <article key={clip.clip_id}><p>{index+1} · {clip.shot_id} v{clip.shot_version} · {clip.in_ms}–{clip.out_ms} ms → 时间线 {clip.start_ms} ms；{clip.measured.width}×{clip.measured.height} · {clip.measured.extension} · 原长 {clip.measured.duration_ms} ms</p><Details label={`来源 pin ${clip.shot_id}`} value={{ shot_digest: clip.shot_digest, ...clip.video_result }} /></article>)}
      <label><input type="checkbox" disabled={disabled} checked={!!consent} onChange={event => { if (canChange() && reviewedRef.current === visible) { const next = event.target.checked ? {} : undefined; consentRef.current = next; updateConsent(next); } }} />已核对顺序、裁切及来源，确认只创建原 Timeline</label>
      <Button disabled={disabled || !consent} onClick={() => void create(visible, consent)}>确认保存视频剪辑底稿</Button>
    </section>}
    {attempt && <section aria-label="视频底稿原请求恢复"><p>原请求 {attempt.body.request_id}。{unknown ? '结果不确定，保留同一请求键；不自动重复创建。' : '正在核对原保存请求。'}</p>
      <Button disabled={busy || externalBusy} onClick={() => void submit(attempt, true)}>读取原请求创建回执</Button>
      {unknown && <Button disabled={busy || externalBusy} onClick={() => void submit(attempt, false, true)}>用原请求键明确重试创建</Button>}
    </section>}
    {result && <section aria-label="已保存的视频分镜底稿"><p>原 Timeline {result.timeline.id} · v{result.timeline.version} · {result.timeline.timeline.duration_ms} ms；请求 {result.request_id}。可在原制作工作区重新打开，尚未渲染。</p>
      <Button disabled={busy || externalBusy} onClick={() => { if (current() && created?.owner === token && !flight.current) { setAttempt(created.intent); void submit(created.intent, true); } }}>重新读取这份原 Timeline</Button>
    </section>}
  </section>;
}
