import { useEffect, useRef, useState } from 'react';
import { ApiError, apiErrorView } from '../api';
import type { StudioTimelineEditorProps } from './useStudioTimelineEditor';
import { checkedTimelineRow, cloneTimeline, timelineBinding, timelineSourcesCurrent, type StudioTimelineRow } from './studioTimelineTypes';
import { applyTimelineSourceEdits, checkedTimelineSourceEffect, prepareTimelineSourceEdit, type TimelineSourceEditRequest, type TimelineSourceIntent, type TimelineSourceOperation } from './studioTimelineSourceEditContract';

type Options = { props: StudioTimelineEditorProps; source?: StudioTimelineRow; canOperate: boolean; isReady: () => boolean;
  onAdopt: (row: StudioTimelineRow) => void; onAuthorityLost: () => void; onGateChange: (locked: boolean) => void };
type Prepared = { source: StudioTimelineRow; operations: TimelineSourceOperation[]; assetKey: string; intentKey: string };
type Attempt = { source: StudioTimelineRow; body: TimelineSourceEditRequest };
const empty = (): TimelineSourceIntent => ({ mode: 'NEW_TRACK', asset_id: '', track_id: '', clip_id: '', start_ms: 0, in_ms: 0, out_ms: 1000, include_audio: false });

/** Source Inspector state only; original Timeline, Asset and request owners remain authoritative. */
export function useStudioTimelineSourceEdit(options: Options) {
  const [intent, setIntent] = useState<TimelineSourceIntent>(empty), [prepared, setPrepared] = useState<Prepared>(), [confirmed, setConfirmed] = useState(false);
  const [unknown, setUnknown] = useState<Attempt>(), [pending, setPending] = useState<'EDIT' | 'CHECK'>(), [error, setError] = useState(''), [notice, setNotice] = useState('');
  const latest = useRef(options); latest.current = options; const owner = useRef(options.props.client), alive = useRef(true), busy = useRef(false), epoch = useRef(0), reading = useRef<AbortController>();
  const form = useRef({ intent, prepared, confirmed }); form.current = { intent, prepared, confirmed }; const attempt = useRef<Attempt>();
  const current = () => alive.current && owner.current === latest.current.props.client && latest.current.props.isCurrent();
  const owns = owner.current === options.props.client && options.props.isCurrent();
  const available = typeof options.props.client.timelineEdit === 'function';
  const assetKey = () => JSON.stringify(latest.current.props.assets.filter(asset => !asset.deleted_at).map(asset => [asset.id, asset.version, asset.sha256, asset.kind]));
  const fresh = !!prepared && !!options.source && timelineBinding(prepared.source) === timelineBinding(options.source) && prepared.assetKey === assetKey() && prepared.intentKey === JSON.stringify(intent);
  const locked = !!pending || !!unknown;
  function clearPrepared() { form.current.prepared = undefined; form.current.confirmed = false; setPrepared(undefined); setConfirmed(false); }
  function reset() { epoch.current++; reading.current?.abort(); reading.current = undefined; busy.current = false; attempt.current = undefined; clearPrepared();
    latest.current.onGateChange(false); form.current.intent = empty(); setIntent(form.current.intent); setUnknown(undefined); setPending(undefined); setError(''); setNotice(''); }
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; reading.current?.abort(); latest.current.onGateChange(false); }; }, []);
  useEffect(() => { owner.current = options.props.client; reset(); }, [options.props.client]);
  useEffect(() => { if (!owns) reset(); }, [owns]);
  const binding = options.source ? timelineBinding(options.source) : '', assets = assetKey();
  useEffect(() => { if (!busy.current && !attempt.current) clearPrepared(); }, [binding, assets]);
  function change(patch: Partial<TimelineSourceIntent>) { if (!current() || busy.current || attempt.current || !available || !latest.current.canOperate) return;
    clearPrepared(); form.current.intent = { ...form.current.intent, ...patch }; setIntent(form.current.intent); setError(''); setNotice(''); }
  function prepare() { if (!current() || busy.current || attempt.current || !available || !latest.current.canOperate || !latest.current.isReady() || !latest.current.source) return;
    clearPrepared(); try { const source = cloneTimeline(latest.current.source), operations = prepareTimelineSourceEdit(source, latest.current.props.assets, form.current.intent, { track: crypto.randomUUID(), clip: crypto.randomUUID() });
      const value = { source, operations, assetKey: assetKey(), intentKey: JSON.stringify(form.current.intent) }; form.current.prepared = value; setPrepared(value); setError(''); setNotice('已核对本次正式素材操作；仍须明确确认并保存到原时间线。');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '正式素材操作无效。'); } }
  function begin(kind: 'EDIT' | 'CHECK', recovering = false) { if (!current() || busy.current || !available || !recovering && (!latest.current.canOperate || !latest.current.isReady() || attempt.current)) return;
    busy.current = true; latest.current.onGateChange(true); const token = ++epoch.current; setPending(kind); setError(''); setNotice(''); return { token, client: owner.current }; }
  function active(request: { token: number; client: typeof owner.current }) { return current() && epoch.current === request.token && request.client === owner.current; }
  function finish(request: { token: number; client: typeof owner.current }) { if (epoch.current !== request.token) return; busy.current = false; latest.current.onGateChange(!!attempt.current); if (active(request)) setPending(undefined); }
  function failed(reason: unknown) { if (reason instanceof ApiError && [401, 403].includes(reason.status)) { reset(); latest.current.onAuthorityLost(); return; }
    setError(apiErrorView(reason, '原编辑回执尚未确认，请只读取原时间线核对。').message); }
  async function execute() {
    const value = form.current.prepared, source = latest.current.source;
    if (!value || !form.current.confirmed || !source || timelineBinding(value.source) !== timelineBinding(source) || value.assetKey !== assetKey() || value.intentKey !== JSON.stringify(form.current.intent) || !timelineSourcesCurrent(source.timeline, latest.current.props.assets)) return;
    const request = begin('EDIT'); if (!request) return;
    const retained: Attempt = { source: cloneTimeline(value.source), body: { expected_version: value.source.version, reviewed_timeline_digest: value.source.timeline_digest, request_id: crypto.randomUUID(), operations: cloneTimeline(value.operations) } };
    attempt.current = retained; setUnknown(retained); form.current.confirmed = false; setConfirmed(false);
    try { const row = await latest.current.props.mutate(() => request.client.timelineEdit!(retained.source, retained.body));
      if (!active(request)) return; const checked = await checkedTimelineSourceEffect(checkedTimelineRow(row, retained.source.id), retained.source, retained.body); if (!active(request)) return;
      if (!timelineSourcesCurrent(checked.timeline, latest.current.props.assets)) throw new ApiError({ status: 409, code: 'STUDIO_SOURCE_CHANGED', message: '编辑返回时素材版本已变化，继续保留原请求核对。' });
      attempt.current = undefined; setUnknown(undefined); clearPrepared(); latest.current.onAdopt(checked); setNotice('本次正式素材已通过原编辑服务保存新版本。素材、其他片段与历史版本保留；没有渲染或自动审核。');
    } catch (reason) { if (active(request)) { if (reason instanceof ApiError && reason.status >= 400 && reason.status < 500 && ![408, 409, 425, 429].includes(reason.status)) { attempt.current = undefined; setUnknown(undefined); }
      failed(reason); } } finally { finish(request); }
  }
  async function check() { const retained = attempt.current; if (!retained) return; const request = begin('CHECK', true); if (!request) return;
    const abort = new AbortController(); reading.current = abort;
    try { const raw = await latest.current.props.mutate(() => latest.current.props.read(() => request.client.timelineGet(retained.source.id, abort.signal))); if (!active(request)) return;
      const row = await checkedTimelineSourceEffect(checkedTimelineRow(raw, retained.source.id), retained.source, retained.body); if (!active(request)) return;
      if (!timelineSourcesCurrent(row.timeline, latest.current.props.assets)) throw new ApiError({ status: 409, code: 'STUDIO_SOURCE_CHANGED', message: '原当前编辑回执的素材版本已变化，当前不能采用。' });
      attempt.current = undefined; setUnknown(undefined); clearPrepared(); latest.current.onAdopt(row); setNotice('已通过原当前编辑回执、完整请求身份与片段效果确认保存；没有重新发送。');
    } catch (reason) { if (active(request)) failed(reason); } finally { if (reading.current === abort) reading.current = undefined; finish(request); }
  }
  let preview; if (prepared && fresh) { try { preview = applyTimelineSourceEdits(prepared.source, prepared.operations); } catch { /* Incomplete authored input stays unsent. */ } }
  return { available, intent: owns ? intent : empty(), prepared: owns && fresh ? prepared : undefined, preview: owns ? preview : undefined, confirmed: owns && fresh && confirmed,
    unknown: owns ? unknown : undefined, pending: owns ? pending : undefined, error: owns ? error : '', notice: owns ? notice : '', locked,
    dirty: owns && (!!intent.asset_id || !!prepared || !!unknown || !!pending), canPrepare: owns && available && options.canOperate && !locked,
    canExecute: owns && available && options.canOperate && !locked && fresh && confirmed, change, prepare, execute, check,
    confirm: (value: boolean) => { if (current() && !busy.current && !attempt.current && latest.current.canOperate && form.current.prepared && timelineBinding(form.current.prepared.source) === binding && form.current.prepared.assetKey === assetKey()) { form.current.confirmed = value; setConfirmed(value); } },
    clear: () => { if (current() && !busy.current && !attempt.current) { clearPrepared(); form.current.intent = empty(); setIntent(form.current.intent); setError(''); setNotice(''); } },
  };
}
