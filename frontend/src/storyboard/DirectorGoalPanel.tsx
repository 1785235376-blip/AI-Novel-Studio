import { useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { directorGoalDraft } from './storyboardWorkspaceContract';
import { directorVsShotOverride, DIRECTOR_FIELD_TABLE } from './storyboardOps';
import type {
  DirectorGoal, DirectorGoalDraft, DirectorVisualTargetValue, StoryboardShot,
} from './storyboardWorkspaceTypes';
import type { StoryboardProposalView } from './useStoryboardWorkspace';

/**
 * 导演目标面板。
 *
 * 这里是最容易被误解的一块，所以规则写死：
 *  - "已采用内容"只读展示原 DIRECTOR 文档里已经确定的值。
 *  - "待审建议"是 `GET /director-proposals` 的另一份记录，**必须**分区显示，
 *    并且永远不能直接变成镜头内容。
 *  - 编辑框在本地，`onCommit` 只是把草稿交回调用方；本工作区不写导演文档，
 *    也不会因为改了目标就自动覆盖已经批准的下游结果。
 */
export function DirectorGoalPanel({ goals, selectedGoal, shot, visualTarget, proposals, locked, notice, onCommit, onDiscard, onReadAdvice }: {
  goals: DirectorGoal[];
  selectedGoal: DirectorGoal | undefined;
  shot: StoryboardShot | undefined;
  visualTarget: DirectorVisualTargetValue | null;
  proposals: StoryboardProposalView[];
  locked: boolean;
  notice: string;
  onCommit: (draft: DirectorGoalDraft) => void;
  onDiscard: () => void;
  onReadAdvice: () => void;
}) {
  const [draft, setDraft] = useState<DirectorGoalDraft | null>(null);
  const resolution = selectedGoal && shot ? directorVsShotOverride(selectedGoal, shot) : null;
  const editing = draft ?? (selectedGoal ? {
    scene_id: selectedGoal.scene_id, note_id: selectedGoal.note_id,
    shot_size: selectedGoal.adopted.shot_size, camera_angle: selectedGoal.adopted.camera_angle,
    camera_motion: selectedGoal.adopted.camera_motion,
    duration_seconds: String(selectedGoal.adopted.duration_seconds),
    emotion: selectedGoal.adopted.emotion, pacing: selectedGoal.adopted.pacing,
    performance: selectedGoal.adopted.performance,
  } : null);

  const commit = () => {
    if (!editing) return;
    try {
      const checked = directorGoalDraft(editing);
      onCommit(checked);
      setDraft(null);
    } catch { /* 校验失败：保持编辑状态，界面显示下面的提示。 */ }
  };

  return <Panel title="导演目标">
    <p className="storyboard-director__scope">
      导演是可选的创作节点，不是其它模块的"核心权威"：这里不改写镜头、不撤销批准，也不会因为改目标就覆盖已经批准的下游结果。
    </p>
    {visualTarget && <section aria-label="视觉目标（已采用）">
      <h4>视觉目标（原文档已采用）</h4>
      <ul>
        <li>风格：{visualTarget.style || '原文档未提供'}</li>
        <li>氛围：{visualTarget.atmosphere || '原文档未提供'}</li>
        <li>色彩：{visualTarget.color || '原文档未提供'}</li>
        <li>节奏：{visualTarget.rhythm || '原文档未提供'}</li>
        <li>参考作品：{visualTarget.reference_works.join('、') || '原文档未提供'}</li>
      </ul>
    </section>}

    {goals.length === 0
      ? <StatusMessage tone="info">还没有读到导演目标。这里不会编造目标；请先读取导演文档，或使用原导演界面创建。</StatusMessage>
      : <section aria-label="导演目标列表">
        <h4>目标（{goals.length} 条，来自原文档）</h4>
        <ol>{goals.map(goal => <li key={goal.note_id}>
          <Badge tone={goal.note_id === selectedGoal?.note_id ? 'info' : 'neutral'}>{goal.note_id}</Badge>
          <span>场景 {goal.scene_id || '原文档未提供'} · 序号 {goal.number || '原文档未提供'}</span>
          <span>{goal.adopted.note || '原文档未提供说明'}</span>
          <Button disabled={locked} onClick={() => setDraft({
            scene_id: goal.scene_id, note_id: goal.note_id, shot_size: goal.adopted.shot_size,
            camera_angle: goal.adopted.camera_angle, camera_motion: goal.adopted.camera_motion,
            duration_seconds: String(goal.adopted.duration_seconds), emotion: goal.adopted.emotion,
            pacing: goal.adopted.pacing, performance: goal.adopted.performance,
          })}>编辑这条目标（本地草稿）</Button>
        </li>)}</ol>
      </section>}

    {editing && <fieldset className="storyboard-director__editor" disabled={locked}>
      <legend>目标草稿（仅本地）</legend>
      <label>景别<input value={editing.shot_size} onChange={event => setDraft({ ...editing, shot_size: event.target.value })} /></label>
      <label>机位角度<input value={editing.camera_angle} onChange={event => setDraft({ ...editing, camera_angle: event.target.value })} /></label>
      <label>摄影机运动<input value={editing.camera_motion} onChange={event => setDraft({ ...editing, camera_motion: event.target.value })} /></label>
      <label>时长（秒，1–600）<input inputMode="numeric" value={editing.duration_seconds} onChange={event => setDraft({ ...editing, duration_seconds: event.target.value })} /></label>
      <label>情绪<textarea value={editing.emotion} onChange={event => setDraft({ ...editing, emotion: event.target.value })} /></label>
      <label>节奏<textarea value={editing.pacing} onChange={event => setDraft({ ...editing, pacing: event.target.value })} /></label>
      <label>表演<textarea value={editing.performance} onChange={event => setDraft({ ...editing, performance: event.target.value })} /></label>
      <div className="storyboard-director__actions">
        <Button disabled={locked} onClick={commit}>采用为本地草稿（不写原文档）</Button>
        <Button onClick={() => { setDraft(null); onDiscard(); }}>放弃编辑</Button>
      </div>
      <p>草稿不会被自动应用：原文档的写入、版本前进与批准撤销都发生在原界面。</p>
    </fieldset>}

    {notice && <StatusMessage tone="info">{notice}</StatusMessage>}

    <section aria-label="AI 建议（待审）">
      <h4>AI 建议（待审，与原文档已采用内容分开）</h4>
      <p>这些是原 owner 的 `director-proposals` 记录，状态不是"已批准"；它们**没有**生效，也不能被这里直接采用。</p>
      {proposals.length === 0
        ? <p>没有读到待审建议（或本工作区没有提供读取入口）。</p>
        : <ul>{proposals.map(proposal => <li key={proposal.id}>
          <Badge tone={proposal.status === 'APPROVED' ? 'success' : 'warning'}>{proposal.status}</Badge>
          <span>{proposal.id} · 建议 {proposal.note_count} 条</span>
          <span>模型调用：{proposal.model_called ? '已记录调用' : '未调用模型'}</span>
          {proposal.quality_verification && <span>质量核验：{proposal.quality_verification}</span>}
          {proposal.output_digest && <code>{proposal.output_digest}</code>}
        </li>)}</ul>}
      <Button disabled={locked} onClick={onReadAdvice}>只读读取导演调度建议</Button>
    </section>

    {resolution && <section aria-label="继承与覆写">
      <h4>继承与覆写（只读对比）</h4>
      <p>继承来源：{resolution.inherited_from_note_ids.join('、') || '没有继承依据'}</p>
      <ul>{DIRECTOR_FIELD_TABLE.map(field => {
        const row = resolution.fields.find(item => item.field === field);
        if (!row) return null;
        return <li key={field}>{field}：生效 {row.effective}{row.overridden && '（镜头级覆写赢了）'}</li>;
      })}</ul>
      <p>{resolution.downstream === 'DIRECTOR_GOAL_EDIT_DOES_NOT_OVERWRITE_APPROVED_RESULTS'
        ? '结论：修改导演目标不会自动覆盖已经批准的下游结果。'
        : '结论：原文档没有声明这条保证。'}</p>
    </section>}
  </Panel>;
}
