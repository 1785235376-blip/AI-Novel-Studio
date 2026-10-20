import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { DIRECTOR_CAMERA_FIELDS, type DirectorCameraField } from './directorCameraReuseHelpers';
import { previewStoryboardDirectorCameraAdoption, STORYBOARD_CAMERA_TARGET_LIMIT } from './storyboardDirectorCameraAdoptionHelpers';
import type { CreativeInput } from './types';

type Props = { draft: CreativeInput; sceneId: string; version?: number; dirty: boolean;
  canEdit: boolean; busy: boolean; onChange: (draft: CreativeInput) => void };
const valueLabel = (value: string) => value === '' ? '（空，采用后清空此项）' : value;

export function StoryboardDirectorCameraAdoption(props: Props) {
  const [source, setSource] = useState(''), [targets, setTargets] = useState<string[]>([]), [fields, setFields] = useState<DirectorCameraField[]>([]);
  const [preview, setPreview] = useState<{ token: object; revision: number; value: ReturnType<typeof previewStoryboardDirectorCameraAdoption> }>();
  const [undo, setUndo] = useState<{ before: CreativeInput; after: CreativeInput; scene: string; version?: number }>();
  const [problem, setProblem] = useState<{ token: object; text: string }>();
  const live = useRef(props); live.current = props;
  const alive = useRef(true), revision = useRef(0), consumed = useRef<object>();
  const values = [props.draft, props.sceneId, props.version, props.dirty, props.canEdit, props.busy];
  const owner = useRef({ values, token: {} });
  if (values.some((value, index) => !Object.is(value, owner.current.values[index]))) owner.current = { values, token: {} };
  const token = owner.current.token, renderedRevision = revision.current, disabled = !props.canEdit || props.busy;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => {
    if (undo && (disabled || !props.dirty || props.draft !== undo.after || props.sceneId !== undo.scene || props.version !== undo.version)) setUndo(undefined);
  }, [props.draft, props.sceneId, props.version, props.dirty, disabled, undo]);
  const current = () => alive.current && !disabled && live.current.canEdit && !live.current.busy
    && owner.current.token === token && revision.current === renderedRevision;
  const invalidate = () => { revision.current++; setPreview(undefined); setProblem(undefined); };
  const notes = props.draft.director_notes.filter(note => note.scene_id === props.sceneId);
  const eligible = props.draft.shots.filter(shot => shot.scene_id === props.sceneId && shot.director_note_ids?.includes(source));
  const visible = !disabled && preview?.token === token && preview.revision === revision.current ? preview : undefined;
  return <details><summary>从关联导演调度采用摄影参数</summary><section aria-label="分镜采用导演摄影参数">
    <p>选择当前分镜内的一条原导演调度和 1–4 个已关联镜头，逐字段核对后写入作者草稿。调度是当前文档保留的来源快照；此处不读取或追随上游新版本。</p>
    <p>只采用所选摄影文字字段；时长、画面与视频提示、摄影几何、动作、连续性、来源、素材及审核保持原样。采用后仍需原“保存草稿”，下游版本仍需重新核对。</p>
    <label className="creative-field"><span>采用摄影参数的原导演调度</span><select disabled={disabled} value={notes.some(note => note.id === source) ? source : ''}
      onChange={event => { if (!current()) return; invalidate(); setSource(event.target.value); setTargets([]); }}>
      <option value="">请选择已关联的原调度</option>{notes.map(note => <option key={note.id} value={note.id}>调度 {note.number} · {note.id}</option>)}
    </select></label>
    <fieldset disabled={disabled}><legend>选择已关联镜头（最多四个）</legend>{eligible.map(shot => <label key={shot.id}>
      <input type="checkbox" checked={targets.includes(shot.id)} disabled={!targets.includes(shot.id) && targets.length >= STORYBOARD_CAMERA_TARGET_LIMIT}
        onChange={event => { if (!current()) return; invalidate(); setTargets(event.target.checked ? targets.length < STORYBOARD_CAMERA_TARGET_LIMIT ? [...targets, shot.id] : targets : targets.filter(id => id !== shot.id)); }} />
      采用目标镜头 {shot.number} · {shot.id}</label>)}</fieldset>
    {source && !eligible.length && <p>当前场景没有关联该调度的镜头。请先在镜头原“导演来源”中明确绑定；这里不会自动建立关联。</p>}
    {!notes.length && <p>当前分镜场景没有原导演调度。可从已保存导演建立分镜；这里不生成或复制来源。</p>}
    <fieldset disabled={disabled}><legend>明确选择采用字段</legend>{DIRECTOR_CAMERA_FIELDS.map(field => <label key={field.key}>
      <input type="checkbox" checked={fields.includes(field.key)} onChange={event => { if (!current()) return; invalidate(); setFields(event.target.checked ? [...fields, field.key] : fields.filter(key => key !== field.key)); }} />采用{field.label}</label>)}</fieldset>
    <div className="creative-actions"><Button disabled={disabled || !source || !targets.length || !fields.length} onClick={() => {
      if (!current()) return; invalidate();
      try {
        const value = previewStoryboardDirectorCameraAdoption(props.draft, props.sceneId, source, targets, fields);
        if (!value.changes.length) { setProblem({ token, text: '所选摄影参数没有变化，作者草稿保持不变。' }); return; }
        setPreview({ token, revision: revision.current, value });
      } catch (reason) { setProblem({ token, text: reason instanceof Error ? reason.message : '无法核对来源与目标。' }); }
    }}>预览采用导演摄影参数</Button>
    <Button disabled={disabled || !props.dirty || !undo || undo.after !== props.draft || undo.scene !== props.sceneId || undo.version !== props.version} onClick={() => {
      if (!current() || !props.dirty || !undo || undo.after !== live.current.draft || undo.scene !== props.sceneId || undo.version !== props.version) return;
      invalidate(); setUndo(undefined); props.onChange(undo.before);
    }}>撤销本次导演摄影采用</Button></div>
    {problem?.token === token && <StatusMessage tone="warning">{problem.text}</StatusMessage>}
    {visible && <section aria-label="分镜摄影采用差异预览"><p>原调度 {source} · {visible.value.changes.length} 项变化</p>
      <ol>{visible.value.changes.map(change => <li key={`${change.id}:${change.field}`}>镜头 {change.number} · {DIRECTOR_CAMERA_FIELDS.find(field => field.key === change.field)!.label}：{valueLabel(change.before)} → {valueLabel(change.after)}</li>)}</ol>
      <Button disabled={disabled} onClick={() => {
        if (!current() || consumed.current === visible) return;
        consumed.current = visible; invalidate(); setUndo({ before: props.draft, after: visible.value.draft, scene: props.sceneId, version: props.version });
        props.onChange(visible.value.draft);
      }}>确认采用到分镜草稿（尚未保存）</Button>
    </section>}
    <p>撤销仅在本次采用后尚未继续编辑、保存或离开当前场景时可用。</p>
  </section></details>;
}
