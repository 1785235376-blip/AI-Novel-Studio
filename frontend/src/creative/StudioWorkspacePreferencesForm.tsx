import { Button, StatusMessage } from '../ui/primitives';
import type { WorkspacePreset } from './studioClient';
import { STUDIO_INTENTS, STUDIO_PRESETS, samePreferenceInput } from './studioWorkspacePreferences';
import type { StudioWorkspacePreferencesController } from './useStudioWorkspacePreferences';

/** View only; Opus can replace this form while preserving the controller's actions. */
export function StudioWorkspacePreferencesForm({ controller: c, locked = false }: { controller: StudioWorkspacePreferencesController; locked?: boolean }) {
  const draft = c.draft;
  if (!draft || !c.base) return null;
  return <details><summary>创作意图与推荐布局</summary>
    <p>可跳过、可多选。布局选项仅保存偏好，当前不会调整界面。偏好不限制模块和权限，也不会执行任务。</p>
    <fieldset disabled={!c.editable || locked}><legend>这次想做什么？</legend>
      {STUDIO_INTENTS.map(([id, label]) => <label key={id}><input type="checkbox" checked={draft.intents.includes(id)} onChange={event => c.change({ ...draft, intents: event.target.checked ? [...draft.intents, id] : draft.intents.filter(value => value !== id) })} />{label}</label>)}
      <label>自定义意图<input maxLength={240} value={draft.custom_intent} onChange={event => c.change({ ...draft, custom_intent: event.target.value })} /></label>
      <label>布局偏好（仅保存）<select value={draft.preset} onChange={event => c.change({ ...draft, preset: event.target.value as WorkspacePreset })}>{STUDIO_PRESETS.map(([id, label]) => <option value={id} key={id}>{label}</option>)}</select></label>
      <Button disabled={!c.dirty} onClick={() => void c.save()}>保存创作偏好</Button>
    </fieldset>
    {c.dirty && <p role="status">创作偏好未保存 · 基于 v{c.base.version}。</p>}
    {c.failure && <StatusMessage tone="warning">{c.failure === 'CONFLICT' ? '服务端版本已变化。当前输入已保留，请先核对。' : '保存请求的结果不确定。请先读取服务端版本，不会自动重复保存。'}</StatusMessage>}
    {c.error && <StatusMessage tone="error">{c.error}</StatusMessage>}{c.notice && <StatusMessage>{c.notice}</StatusMessage>}
    <Button disabled={!c.canCheck || locked} onClick={() => void c.checkServer()}>核对服务端偏好</Button>
    {c.candidate && <section role="alert" aria-label="核对服务端创作偏好">
      <p>服务端 v{c.candidate.version} · 布局 {STUDIO_PRESETS.find(([id]) => id === c.candidate!.preset)?.[1]}</p>
      <p>意图：{c.candidate.intents.map(id => STUDIO_INTENTS.find(([key]) => key === id)?.[1]).join('、') || '未选择'}；自定义：{c.candidate.custom_intent || '未填写'}</p>
      <p>{samePreferenceInput(draft, c.candidate) ? '当前输入与读取的服务端值相同；这不证明原请求由此客户端完成。' : '读取的服务端值与当前输入不同。'}</p>
      <label><input type="checkbox" disabled={!c.canCheck || locked} checked={c.confirmed} onChange={event => c.setConfirmed(event.target.checked)} />我已核对两个版本，确认以下选择</label>
      <Button disabled={!c.canAdopt || locked} onClick={() => c.adoptCandidate(false)}>采用服务端偏好</Button>
      <Button disabled={!c.canKeepDraft || locked} onClick={() => c.adoptCandidate(true)}>保留输入并基于此版本编辑</Button>
    </section>}
  </details>;
}
