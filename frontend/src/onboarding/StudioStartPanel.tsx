import { useState } from 'react';
import { Button, EmptyState, StatusMessage } from '../ui/primitives';
import { IntentPicker } from './IntentPicker';
import { InterfaceModeSwitch } from './InterfaceModeSwitch';
import { SuggestionPlan } from './SuggestionPlan';
import { STUDIO_ENTRY_CONTRACT, type StudioInterfaceMode } from './studioEntryTypes';
import type { StudioEntryController } from './useStudioEntry';
import './studioEntry.css';

export type StudioStartPanelProps = {
  controller: StudioEntryController;
  onOpenProject: (projectId: string) => void;
  /** Presentation only; the mounting workspace owns and persists the value. */
  mode: StudioInterfaceMode;
  onModeChange: (mode: StudioInterfaceMode) => void;
};

/**
 * The three explicit entries into the studio: continue a project, start blank, or start
 * from a creative intent. Every intent entry stays skippable, no entry needs a model or a
 * network connection, and a resume target that cannot be read is reported as invalid
 * instead of being replaced by a new project.
 */
export function StudioStartPanel({ controller, onOpenProject, mode, onModeChange }: StudioStartPanelProps) {
  const [projectId, setProjectId] = useState('');
  const [idProblem, setIdProblem] = useState('');
  const busy = controller.creating || controller.saving;
  const resumeByHand = () => {
    const wanted = projectId.trim();
    if (!wanted) { setIdProblem('请输入要重新打开的项目编号。'); return; }
    if (!/^[A-Za-z0-9][A-Za-z0-9._-]*$/.test(wanted)) { setIdProblem('项目编号只能包含字母、数字、点、下划线和连字符。'); return; }
    setIdProblem(''); controller.selectProject(wanted);
  };
  return <section className="studio-entry" aria-label="项目入口">
    <header className="studio-entry__header">
      <h2>进入创作工作区</h2>
      <p>三个入口都可以直接使用；创作意图可选、可跳过，也可以稍后再设置。</p>
    </header>

    <InterfaceModeSwitch mode={mode} onChange={onModeChange} />

    {controller.state === 'denied' && <StatusMessage tone="error">{controller.problem?.message ?? STUDIO_ENTRY_CONTRACT.messages.denied}</StatusMessage>}
    {controller.state === 'failed' && <StatusMessage tone="error">
      {controller.problem?.message ?? STUDIO_ENTRY_CONTRACT.messages.read_failed}
      <Button onClick={() => void controller.reload()}>重新读取</Button>
    </StatusMessage>}
    {controller.state === 'missing' && <StatusMessage tone="error">
      {controller.problem?.message ?? STUDIO_ENTRY_CONTRACT.messages.project_missing}
      <Button onClick={() => void controller.reload()}>重新读取项目列表</Button>
    </StatusMessage>}

    <section className="studio-entry__continue" aria-label="继续项目">
      <header><h3>继续项目</h3><Button disabled={controller.state === 'loading'} onClick={() => void controller.reload()}>刷新列表</Button></header>
      {controller.state === 'loading' && <p role="status" className="studio-entry__loading">正在读取项目列表与已保存的创作意图…</p>}
      {controller.state === 'empty' && <EmptyState title="还没有项目" detail={`${STUDIO_ENTRY_CONTRACT.messages.empty}${STUDIO_ENTRY_CONTRACT.notices.manual_scope}`} />}
      {controller.projects.length > 0 && <ul className="studio-entry__projects">
        {controller.projects.map(project => <li key={project.id}>
          <button
            type="button" className={`studio-entry__project${controller.selectedId === project.id ? ' is-selected' : ''}`}
            aria-pressed={controller.selectedId === project.id} disabled={busy}
            onClick={() => controller.selectProject(project.id)}
          >
            <strong>{project.title}</strong>
            <span>{project.id}{project.updated_at ? ` · 更新于 ${project.updated_at}` : ''}{project.entry_kind ? ` · ${project.entry_kind}` : ''}</span>
          </button>
        </li>)}
      </ul>}
      {controller.selectedId && controller.intent && <div className="studio-entry__resume">
        <p>已读取「{controller.selectedId}」的创作意图（v{controller.intent.version}）。继续会打开同一个项目，不会新建或复制任何内容。</p>
        <Button variant="primary" disabled={!controller.canOpen} onClick={() => { controller.openProject(); onOpenProject(controller.selectedId); }}>继续这个项目</Button>
      </div>}
      {controller.selectedId && !controller.intent && controller.state !== 'missing' && controller.state !== 'loading' && controller.state !== 'denied' && <p className="studio-entry__resume-hint">正在确认「{controller.selectedId}」是否可用…</p>}
      <label className="studio-entry__field">
        <span>按编号重新打开</span>
        <input value={projectId} maxLength={STUDIO_ENTRY_CONTRACT.bounds.project_id} disabled={busy} onChange={event => { setProjectId(event.target.value); setIdProblem(''); }} />
      </label>
      <Button disabled={busy || !projectId.trim()} onClick={resumeByHand}>重新打开</Button>
      {idProblem && <StatusMessage tone="error">{idProblem}</StatusMessage>}
    </section>

    <section className="studio-entry__blank" aria-label="空白开始">
      <header><h3>空白开始</h3></header>
      <p>新建一个中性项目，不预设任何创作意图；手动编辑、导入与素材管理始终可用。</p>
      <label className="studio-entry__field">
        <span>项目名称</span>
        <input value={controller.title} maxLength={STUDIO_ENTRY_CONTRACT.bounds.title} disabled={busy} onChange={event => controller.setTitle(event.target.value)} />
      </label>
      <Button variant="primary" loading={controller.creating} disabled={!controller.canCreate} onClick={() => void controller.create('blank')}>空白开始</Button>
      {!controller.title.trim() && <p className="studio-entry__hint">请先填写项目名称（1–200 个字符）。</p>}    </section>

    <section className="studio-entry__intent-start" aria-label="按创作意图开始">
      <header><h3>按创作意图开始</h3></header>
      <p>{STUDIO_ENTRY_CONTRACT.notices.manual_scope}选择意图只会影响推荐布局，不会限制模块或权限，也不会生成任何内容。</p>
      <IntentPicker controller={controller} />
      <div className="studio-entry__intent-actions">
        <Button
          variant="primary" loading={controller.creating}
          disabled={!controller.canCreate || !controller.savable}
          onClick={() => void controller.create('intent')}
        >按创作意图开始</Button>
        <Button disabled={busy} onClick={() => controller.skipIntent()}>跳过创作意图，之后再说</Button>
      </div>
      {!controller.savable && <p className="studio-entry__hint">请先选择至少一个创作意图（自定义意图还需要填写名称），或直接跳过。</p>}
      <SuggestionPlan controller={controller} onAdopt={() => { /* adoption is written by the controller; navigation stays with the Lead. */ }} />
    </section>
  </section>;
}
