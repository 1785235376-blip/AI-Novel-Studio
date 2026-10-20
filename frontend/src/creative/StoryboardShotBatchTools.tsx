import { useLayoutEffect, useRef, useState } from 'react';
import { Button, StatusMessage } from '../ui/primitives';
import { creativeTextLength, type CreativeInput } from './types';
import { previewStoryboardShotBatch, STORYBOARD_SHOT_BATCH_FIELDS, STORYBOARD_SHOT_BATCH_LIMIT, type StoryboardShotBatchField, type StoryboardShotBatchOwner } from './storyboardShotBatch';

type Props = { draft: CreativeInput; sceneId: string; version?: number; dirty: boolean; canEdit: boolean; busy: boolean; owner?: StoryboardShotBatchOwner; onChange: (draft: CreativeInput) => void };
type Form = { token: object; selected: string[]; field: StoryboardShotBatchField; value: string };
type Preview = { token: object; revision: number; value: ReturnType<typeof previewStoryboardShotBatch> };
type Undo = { before: CreativeInput; after: CreativeInput; sceneId: string; version?: number; ownerRevision?: number };

export function StoryboardShotBatchTools(props: Props) {
  const [form, setForm] = useState<Form>(), [preview, setPreview] = useState<Preview>(), [undo, setUndo] = useState<Undo>();
  const [problem, setProblem] = useState<{ token: object; text: string }>(), [, renderRevision] = useState(0);
  const live = useRef(props); live.current = props;
  const alive = useRef(true), composing = useRef(false), revision = useRef(0), consumed = useRef<Preview>();
  const input = useRef<HTMLInputElement>(null), fieldInput = useRef<HTMLSelectElement>(null);
  const ownerRevision = props.owner?.revision();
  const values = [props.draft, props.sceneId, props.version, props.dirty, props.canEdit, props.busy, ownerRevision];
  const owner = useRef({ values, token: {}, epoch: 0 });
  if (values.some((value, index) => !Object.is(value, owner.current.values[index]))) owner.current = { values, token: {}, epoch: owner.current.epoch + 1 };
  const token = owner.current.token, renderedRevision = revision.current;
  const disabled = !props.canEdit || props.busy || props.draft.mode !== 'STORYBOARD';
  const controls: Form = form?.token === token ? form : { token, selected: [], field: 'shot_size', value: '' };
  const shots = props.draft.shots.filter(shot => shot.scene_id === props.sceneId);
  const visible = !disabled && preview?.token === token && preview.revision === revision.current ? preview : undefined;
  useLayoutEffect(() => { alive.current = true; return () => { alive.current = false; }; }, []);
  useLayoutEffect(() => { composing.current = false; }, [token]);
  useLayoutEffect(() => {
    if (undo && (disabled || !props.dirty || props.draft !== undo.after || props.sceneId !== undo.sceneId || props.version !== undo.version || ownerRevision !== undo.ownerRevision)) setUndo(undefined);
  }, [props.draft, props.sceneId, props.version, props.dirty, disabled, ownerRevision, undo]);
  const current = () => alive.current && !disabled && live.current.canEdit && !live.current.busy
    && owner.current.token === token && revision.current === renderedRevision
    && (!props.owner || props.owner.revision() === ownerRevision && props.owner.isCurrent());
  const inputsMatch = () => !composing.current && input.current?.value === controls.value && fieldInput.current?.value === controls.field;
  function invalidate() { revision.current++; renderRevision(value => value + 1); setPreview(undefined); setProblem(undefined); }
  function changeForm(patch: Partial<Omit<Form, 'token'>>) { if (!current()) return; invalidate(); setForm({ ...controls, ...patch, token }); }
  if (props.draft.mode !== 'STORYBOARD') return null;
  return <details><summary>批量设置所选镜头语言</summary><section aria-label="所选分镜镜头语言批量编辑">
    <p>在当前场景内明确选择镜头，每次只设置景别、机位角度或运镜中的一项。其他镜头及编号、时长、画面、连续性、导演来源和媒体绑定保持原样。</p>
    <fieldset disabled={disabled}><legend>选择当前场景镜头</legend>
      {shots.map(shot => <label key={shot.id}><input type="checkbox" checked={controls.selected.includes(shot.id)}
        disabled={!controls.selected.includes(shot.id) && controls.selected.length >= STORYBOARD_SHOT_BATCH_LIMIT}
        onChange={event => changeForm({ selected: event.target.checked ? [...new Set([...controls.selected, shot.id])] : controls.selected.filter(id => id !== shot.id) })} />批量选择镜头 {shot.number} · {shot.id}</label>)}
      {!shots.length && <p>当前场景没有可选择的镜头。</p>}
    </fieldset>
    <div className="creative-actions"><Button disabled={disabled || !shots.length} onClick={() => changeForm({ selected: shots.slice(0, STORYBOARD_SHOT_BATCH_LIMIT).map(shot => shot.id) })}>全选当前场景镜头</Button>
      <Button disabled={disabled || !controls.selected.length} onClick={() => changeForm({ selected: [] })}>清除批量镜头选择</Button></div>
    <p aria-live="polite">已选择 {controls.selected.length} / {shots.length} 个当前场景镜头。</p>
    <label className="creative-field"><span>批量镜头字段</span><select key={owner.current.epoch} ref={fieldInput} aria-label="批量镜头字段" disabled={disabled} value={controls.field} onChange={event => changeForm({ field: event.target.value as StoryboardShotBatchField })}>
      {STORYBOARD_SHOT_BATCH_FIELDS.map(field => <option key={field.key} value={field.key}>{field.label}</option>)}
    </select></label>
    <label className="creative-field"><span>批量镜头新值</span><input key={owner.current.epoch} ref={input} aria-label="批量镜头新值" disabled={disabled} maxLength={160} value={controls.value} aria-invalid={creativeTextLength(controls.value) > 80}
      onChange={event => changeForm({ value: event.target.value })}
      onCompositionStart={() => { if (current()) { composing.current = true; invalidate(); } }}
      onCompositionEnd={event => { if (current()) { composing.current = false; changeForm({ value: event.currentTarget.value }); } }} /></label>
    <p>{creativeTextLength(controls.value)} / 80 个 Unicode 字符；新值留空时不应用。这里设置作者文字，不生成摄影参数或调用模型。</p>
    <div className="creative-actions"><Button disabled={disabled || !controls.selected.length || !controls.value.trim() || creativeTextLength(controls.value) > 80} onClick={() => {
      if (!current() || !inputsMatch()) return; invalidate();
      try {
        const value = previewStoryboardShotBatch(props.draft, props.sceneId, controls.selected, controls.field, controls.value);
        if (!value.changedCount) { setProblem({ token, text: '所选镜头的该字段没有变化，草稿保持原样。' }); return; }
        setPreview({ token, revision: revision.current, value });
      } catch (reason) { setProblem({ token, text: reason instanceof Error ? reason.message : '无法核对当前镜头。' }); }
    }}>预览所选镜头语言</Button>
      <Button disabled={disabled || !props.dirty || !undo || undo.after !== props.draft || undo.sceneId !== props.sceneId || undo.version !== props.version} onClick={() => {
        if (!current() || !props.dirty || !undo || undo.after !== live.current.draft || undo.sceneId !== props.sceneId || undo.version !== props.version) return;
        invalidate(); setUndo(undefined); props.onChange(undo.before);
      }}>撤销本次镜头语言批量编辑</Button></div>
    {problem?.token === token && <StatusMessage tone="warning">{problem.text}</StatusMessage>}
    {visible && <section aria-label="所选镜头语言差异预览"><p>已选择 {visible.value.rows.length} 个镜头，{visible.value.changedCount} 项将变化；字段：{STORYBOARD_SHOT_BATCH_FIELDS.find(field => field.key === visible.value.field)!.label}。</p>
      <ol>{visible.value.rows.map(row => <li key={row.id}>镜头 {row.number} · {row.id}：{row.before || '（空）'} → {row.after}{row.before === row.after ? '（未变化）' : ''}</li>)}</ol>
      <Button disabled={disabled} onClick={() => {
        if (!current() || !inputsMatch() || consumed.current === visible) return;
        consumed.current = visible; invalidate();
        props.onChange(visible.value.draft);
        setUndo({ before: props.draft, after: visible.value.draft, sceneId: props.sceneId, version: props.version, ownerRevision: props.owner?.revision() });
      }}>确认批量应用到分镜草稿（尚未保存）</Button>
    </section>}
    <p>应用后仍需原“保存草稿”，再核对审核和下游版本。撤销仅在尚未继续编辑、保存或离开当前场景时可用。</p>
  </section></details>;
}
