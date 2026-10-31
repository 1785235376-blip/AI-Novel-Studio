import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import type { CreativeInput } from './types';
import { cameraValueLabel, DIRECTOR_CAMERA_FIELDS, previewDirectorCameraReuse, type DirectorCameraField } from './directorCameraReuseHelpers';

type Props = { draft: CreativeInput; sceneId: string; version?: number; dirty: boolean; canEdit: boolean; busy: boolean; onChange: (draft: CreativeInput) => void };
export function DirectorCameraReuse(props: Props) {
  const [source, setSource] = useState(''), [targets, setTargets] = useState<string[]>([]), [fields, setFields] = useState<DirectorCameraField[]>([]);
  const [preview, setPreview] = useState<{ token: object; revision: number; value: ReturnType<typeof previewDirectorCameraReuse> }>();
  const [undo, setUndo] = useState<{ before: CreativeInput; after: CreativeInput; sceneId: string; version?: number }>();
  const [error, setError] = useState<{ token: object; text: string }>();
  const live = useRef(props); live.current = props;
  const alive = useRef(true), revision = useRef(0), consumed = useRef<object>();
  const values = [props.draft, props.sceneId, props.version, props.dirty, props.canEdit, props.busy];
  const owner = useRef({ values, token: {} });
  if (values.some((value, index) => value !== owner.current.values[index])) owner.current = { values, token: {} };
  const token = owner.current.token, capturedRevision = revision.current;
  const disabled = !props.canEdit || props.busy;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => {
    if (undo && (disabled || props.draft !== undo.after || props.sceneId !== undo.sceneId || props.version !== undo.version)) setUndo(undefined);
  }, [disabled, props.draft, props.sceneId, props.version, props.dirty, undo]);
  const current = () => alive.current && live.current.canEdit && !live.current.busy && owner.current.token === token && revision.current === capturedRevision;
  const invalidate = () => { revision.current++; setPreview(undefined); setError(undefined); };
  const notes = props.draft.director_notes.filter(note => note.scene_id === props.sceneId);
  const visible = preview && preview.token === token && preview.revision === revision.current && !disabled ? preview : undefined;
  return <section aria-label="导演摄影参数复用"><h3>复用当前场景摄影参数</h3>
    <p>选择来源、目标和字段，核对差异后应用到当前作者草稿。空值会清空对应字段。时长、表演、故事、空间关系和来源绑定保持原样；仍需明确保存。</p>
    <label className="creative-field"><span>摄影参数来源调度</span><select disabled={disabled} value={notes.some(note => note.id === source) ? source : ''} onChange={event => { if (!current()) return; invalidate(); setSource(event.target.value); setTargets([]); }}><option value="">请选择来源</option>{notes.map(note => <option key={note.id} value={note.id}>调度 {note.number} · {note.id}</option>)}</select></label>
    <fieldset disabled={disabled}><legend>选择目标调度</legend>{notes.filter(note => note.id !== source).map(note => <label key={note.id}><input type="checkbox" checked={targets.includes(note.id)} onChange={event => { if (!current()) return; invalidate(); setTargets(event.target.checked ? [...targets, note.id] : targets.filter(id => id !== note.id)); }} />目标调度 {note.number} · {note.id}</label>)}</fieldset>
    <fieldset disabled={disabled}><legend>选择复用字段</legend>{DIRECTOR_CAMERA_FIELDS.map(field => <label key={field.key}><input type="checkbox" checked={fields.includes(field.key)} onChange={event => { if (!current()) return; invalidate(); setFields(event.target.checked ? [...fields, field.key] : fields.filter(key => key !== field.key)); }} />复用{field.label}</label>)}</fieldset>
    {notes.length < 2 && <p>当前场景至少需要两个导演调度。</p>}
    <p>撤销仅在本次应用后尚未继续编辑、保存或离开当前场景时可用；其他操作会使本次撤销失效，以保留后续修改。</p>
    <div className="creative-actions"><Button disabled={disabled || !source || !targets.length || !fields.length} onClick={() => {
      if (!current()) return;
      invalidate();
      try {
        const value = previewDirectorCameraReuse(props.draft, props.sceneId, source, targets, fields);
        if (!value.changes.length) { setError({ token, text: '所选摄影参数没有变化，草稿保持不变。' }); return; }
        setPreview({ token, revision: revision.current, value });
      } catch (reason) { setError({ token, text: reason instanceof Error ? reason.message : '无法预览摄影参数。' }); }
    }}>预览摄影参数复用</Button>
    <Button disabled={disabled || !undo || undo.after !== props.draft || undo.sceneId !== props.sceneId || undo.version !== props.version} onClick={() => {
      if (!current() || !undo || undo.after !== live.current.draft || undo.sceneId !== live.current.sceneId || undo.version !== live.current.version) return;
      invalidate(); setUndo(undefined); props.onChange(undo.before);
    }}>撤销本次摄影参数复用</Button></div>
    {error?.token === token && <StatusMessage tone="warning">{error.text}</StatusMessage>}
    {visible && <section aria-label="摄影参数复用预览"><p>来源调度 {notes.find(note => note.id === source)?.number} · {visible.value.changes.length} 项字段变化</p><ol>{visible.value.changes.map(row => <li key={`${row.id}:${row.field}`}>调度 {row.number} · {DIRECTOR_CAMERA_FIELDS.find(field => field.key === row.field)!.label}：{cameraValueLabel(row.before)} → {cameraValueLabel(row.after)}</li>)}</ol><Button disabled={disabled} onClick={() => {
      if (!current() || consumed.current === visible) return;
      consumed.current = visible; invalidate(); setUndo({ before: props.draft, after: visible.value.draft, sceneId: props.sceneId, version: props.version }); props.onChange(visible.value.draft);
    }}>确认应用摄影参数（尚未保存）</Button></section>}
  </section>;
}
