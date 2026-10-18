import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { apiErrorView } from '../api';
import type { StudioGraphClient } from './studioGraphClient';
import type { StudioGraphNode, StudioGraphParameters } from './studioGraphTypes';
import { graphId } from './graphDraft';
import { checkedGraphTimelineEdits, checkedGraphTimelineParameters, graphTimelinePorts, type GraphTimelineEdit, type GraphTimelinePort } from './studioGraphTimelineContract';
import { checkedTimelineExportProfile, type TimelineExportPreset } from './studioTimelineExportTypes';
import type { StudioTimelineRow } from './studioTimelineTypes';

type Form = { owner: string; operation: 'clip.trim' | 'clip.move' | 'clip.split' | 'clip.duplicate' | 'clip.slip' | 'clip.update' | 'clip.remove';
  clip_id: string; track_id: string; in_ms: string; out_ms: string; start_ms: string; at_ms: string; offset_ms: string;
  speed_num: string; speed_den: string; opacity: string; gain_db: string; fade_in_ms: string; fade_out_ms: string; muted: boolean; include_audio: boolean; ripple: boolean };
const empty = (): Form => ({ owner: '', operation: 'clip.trim', clip_id: '', track_id: '', in_ms: '0', out_ms: '1000', start_ms: '0', at_ms: '500', offset_ms: '0',
  speed_num: '1', speed_den: '1', opacity: '1', gain_db: '0', fade_in_ms: '0', fade_out_ms: '0', muted: false, include_audio: false, ripple: false });
type Props = { client: StudioGraphClient; node?: StudioGraphNode; editable: boolean; identity: string; isCurrent: () => boolean; isBusy: () => boolean;
  read: <T>(work: () => Promise<T>) => Promise<T>; update: (parameters: StudioGraphParameters) => void };

/** Explicit authoring only: no effect reads a timeline, saves edits, admits a task or renders. */
export function useStudioGraphTimelineEditor(props: Props) {
  const [rows, setRows] = useState<StudioTimelineRow[]>([]), [choice, setChoice] = useState(''), [loading, setLoading] = useState(false), [error, setError] = useState('');
  const [form, setForm] = useState<Form>(empty), latest = useRef(props); latest.current = props;
  const alive = useRef(true), epoch = useRef(0), pending = useRef<AbortController>();
  const current = () => alive.current && latest.current.isCurrent();
  const canEdit = () => current() && latest.current.editable && !latest.current.isBusy() && !pending.current;
  const chosen = rows.find(row => row.id === choice), snapshot = props.node?.parameters.timeline_snapshot;
  const bound = rows.find(row => row.id === snapshot?.id && row.version === snapshot.version && row.timeline_digest === snapshot.digest);
  const operations = props.node?.parameters.edit_operations || [], bindings = props.node?.parameters.source_bindings || [];
  const clips = bound?.timeline.tracks.flatMap(track => track.clips.map(clip => ({ clip, track }))) || [];
  const formDirty = !!form.owner;
  useEffect(() => { alive.current = true; return () => { alive.current = false; epoch.current++; pending.current?.abort(); }; }, []);
  useLayoutEffect(() => { epoch.current++; pending.current?.abort(); pending.current = undefined; setRows([]); setChoice(''); setLoading(false); setError(''); setForm(empty()); }, [props.client, props.identity]);
  async function loadRows() {
    const source = latest.current, method = source.client.graphTimelineList; if (!current() || source.isBusy() || pending.current || !method) return;
    const abort = new AbortController(), request = ++epoch.current; pending.current = abort; setLoading(true); setError('');
    try { const result = await source.read(() => method(abort.signal));
      if (current() && request === epoch.current && latest.current.client === source.client && !abort.signal.aborted) { setRows(result.items); setChoice(''); }
    } catch (reason) { if (current() && request === epoch.current && !abort.signal.aborted) setError(apiErrorView(reason, '原时间线读取失败，已有图绑定保持。').message); }
    finally { if (request === epoch.current) { pending.current = undefined; if (alive.current) setLoading(false); } }
  }
  function update(next: StudioGraphParameters) {
    if (!canEdit() || latest.current.node?.definition_id !== 'timeline_export') return;
    try { latest.current.update(checkedGraphTimelineParameters(next)); setError(''); } catch (reason) { setError(reason instanceof Error ? reason.message : '时间线参数无效。'); }
  }
  function bindChosen() {
    if (!chosen || !canEdit() || formDirty) return;
    update({ timeline_snapshot: { id: chosen.id, version: chosen.version, digest: chosen.timeline_digest }, edit_operations: [], source_bindings: [], export_profile: { preset: 'REVIEW_MP4' } });
  }
  function choose(value: string) { if (!current() || latest.current.isBusy() || pending.current) return; setChoice(value); }
  function setPreset(preset: TimelineExportPreset) { if (!canEdit() || !latest.current.node) return;
    update({ ...latest.current.node.parameters, export_profile: checkedTimelineExportProfile({ preset }) }); }
  function setProfileField(key: 'video_bitrate_kbps' | 'audio_bitrate_kbps' | 'crf', value: string) {
    if (!latest.current.node?.parameters.export_profile || value === '') return;
    update({ ...latest.current.node.parameters, export_profile: { ...latest.current.node.parameters.export_profile, [key]: Number(value) } });
  }
  function bindSource(port: GraphTimelinePort, clipId: string) {
    const node = latest.current.node; if (!node || !graphTimelinePorts.includes(port)) return;
    const next = (node.parameters.source_bindings || []).filter(row => row.port !== port);
    update({ ...node.parameters, source_bindings: [...next, ...(clipId ? [{ port, clip_id: clipId }] : [])].sort((left, right) => left.port.localeCompare(right.port)) });
  }
  function changeForm<K extends keyof Form>(key: K, value: Form[K]) {
    const node = latest.current.node; if (!canEdit() || !node || node.definition_id !== 'timeline_export' || form.owner && form.owner !== node.id || key === 'owner') return;
    setForm(row => ({ ...row, owner: node.id, [key]: value }));
  }
  function selectClip(id: string) {
    const node = latest.current.node, source = clips.find(row => row.clip.id === id); if (!canEdit() || !node || !source || form.owner && form.owner !== node.id) return;
    const clip = source.clip;
    setForm(row => ({ ...row, owner: node.id, clip_id: id, track_id: source.track.id, in_ms: String(clip.in_ms), out_ms: String(clip.out_ms), start_ms: String(clip.start_ms),
      at_ms: String(clip.start_ms + 500), speed_num: String(clip.speed_num ?? 1), speed_den: String(clip.speed_den ?? 1), opacity: String(clip.opacity ?? 1),
      gain_db: String(clip.gain_db ?? 0), muted: clip.muted === true, include_audio: clip.include_audio === true,
      fade_in_ms: String(clip.fade_in_ms ?? 0), fade_out_ms: String(clip.fade_out_ms ?? 0) }));
  }
  function resetForm() { setForm(empty()); setError(''); }
  function clearForm() { if (!current() || latest.current.isBusy() || pending.current) return; resetForm(); }
  function append() {
    const node = latest.current.node; if (!canEdit() || !node || node.id !== form.owner || !form.clip_id) return;
    try {
      const number = (key: keyof Form) => { const raw = form[key]; if (typeof raw !== 'string' || raw.trim() === '' || !Number.isFinite(Number(raw))) throw new Error('请填入准确的剪辑数值。'); return Number(raw); };
      let operation: GraphTimelineEdit;
      const op = form.operation, clip_id = form.clip_id;
      if (op === 'clip.update' && bound?.timeline.schema_version !== 2) throw new Error('速度、音量与淡入淡出需要先在原时间线编辑器明确升级为 schema2。');
      if (op === 'clip.trim') operation = { op, clip_id, in_ms: number('in_ms'), out_ms: number('out_ms'), ripple: form.ripple };
      else if (op === 'clip.move' || op === 'clip.duplicate') operation = { op, clip_id, track_id: form.track_id, start_ms: number('start_ms'), ...(op === 'clip.duplicate' ? { new_clip_id: graphId('clip') } : {}) } as GraphTimelineEdit;
      else if (op === 'clip.split') operation = { op, clip_id, at_ms: number('at_ms'), new_clip_id: graphId('clip') };
      else if (op === 'clip.slip') operation = { op, clip_id, offset_ms: number('offset_ms') };
      else if (op === 'clip.remove') operation = { op, clip_id, ripple: form.ripple };
      else { const source = clips.find(row => row.clip.id === clip_id); if (!source) throw new Error('请重新读取绑定时间线核对该片段。');
        operation = { op, clip_id, changes: { speed_num: number('speed_num'), speed_den: number('speed_den'), gain_db: number('gain_db'), muted: form.muted,
          fade_in_ms: number('fade_in_ms'), fade_out_ms: number('fade_out_ms'), ...(source.track.kind === 'VIDEO' ? { opacity: number('opacity'), include_audio: form.include_audio } : {}) } }; }
      const edits = checkedGraphTimelineEdits([...(node.parameters.edit_operations || []), operation]);
      const checked = checkedGraphTimelineParameters({ ...node.parameters, edit_operations: edits }); latest.current.update(checked); setForm(empty()); setError('');
    } catch (reason) { setError(reason instanceof Error ? reason.message : '剪辑操作未加入，原输入保持。'); }
  }
  // Index-based list controls belong to the exact rendered node/parameters. A
  // retained handler must never reorder or remove a different node's operation.
  const listOwner = useRef({ identity: props.identity, client: props.client, node: props.node, token: {} });
  if (listOwner.current.identity !== props.identity || listOwner.current.client !== props.client || listOwner.current.node !== props.node) {
    listOwner.current = { identity: props.identity, client: props.client, node: props.node, token: {} };
  }
  const listToken = listOwner.current.token;
  function listCurrent() { return canEdit() && listOwner.current.token === listToken && latest.current.node === props.node; }
  function removeOperation(index: number) {
    const node = latest.current.node, edits = node?.parameters.edit_operations || [];
    if (!listCurrent() || !node || !Number.isSafeInteger(index) || index < 0 || index >= edits.length) return;
    update({ ...node.parameters, edit_operations: edits.filter((_, position) => position !== index) });
  }
  function moveOperation(index: number, destination: number) {
    const node = latest.current.node, edits = node?.parameters.edit_operations || [];
    if (!listCurrent() || !node || !Number.isSafeInteger(index) || !Number.isSafeInteger(destination)
      || index < 0 || destination < 0 || index >= edits.length || destination >= edits.length || index === destination) return;
    const next = [...edits], [selected] = next.splice(index, 1); next.splice(destination, 0, selected);
    update({ ...node.parameters, edit_operations: next });
  }
  return { rows, choice, chosen, bound, loading, error, form, formDirty, formOwnerMatches: !form.owner || form.owner === props.node?.id,
    clips, operations, bindings, canLoad: typeof props.client.graphTimelineList === 'function' && !loading && !props.isBusy() && props.isCurrent(),
    choose, loadRows, bindChosen, setPreset, setProfileField, bindSource, changeForm, selectClip, clearForm, resetForm, append, removeOperation, moveOperation };
}
export type StudioGraphTimelineEditorController = ReturnType<typeof useStudioGraphTimelineEditor>;
