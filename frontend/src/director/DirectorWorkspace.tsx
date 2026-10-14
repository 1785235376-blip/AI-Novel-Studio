import { useEffect, useState } from 'react';

import { Badge, Button, Panel, Spinner, StatusMessage } from '../ui/primitives';
import { ContinuityPanel } from './ContinuityPanel';
import { DirectorIntentPanel } from './DirectorIntentPanel';
import { ShotCardPanel } from './ShotCardPanel';
import { cameraVocabulary } from './directorWorkspaceContract';
import { useDirectorWorkspace } from './useDirectorWorkspace';
import type { DirectorWorkspaceClient } from './directorWorkspaceTypes';

import './directorWorkspace.css';

/**
 * Phase14-A 导演工作台。
 *
 * 一块**导演决策**面板，不是一张新表单：它把原文档里已经 authoring 的导演意图、
 * 镜头卡与连续性摆在同一个视图里，并且把"测量"与"authoring"、"提示"与"修改"
 * 在界面上分开显示。
 *
 * 本组件只有一条读取通道（`DirectorWorkspaceClient`）。它不写导演文档、不写镜头、
 * 不执行任何模型或渲染：`visual_target` / `director_notes` 的 authoring 仍然发生在
 * 原文档界面。
 */
export function DirectorWorkspace({ client, documentId, active = true }: {
  client: DirectorWorkspaceClient | null;
  documentId: string | null;
  active?: boolean;
}) {
  const controller = useDirectorWorkspace(client);
  const [selectedShotId, setSelectedShotId] = useState<string | null>(null);
  /** 本地镜头语言草稿：只存在于本次会话，绝不写回原文档。 */
  const [cameraDraft, setCameraDraft] = useState<Record<string, string>>({});
  const { read, reset } = controller;

  useEffect(() => {
    if (!active || !documentId) { reset(); return; }
    void read(documentId);
  }, [active, documentId, read, reset]);

  const projection = controller.projection;
  const draftCount = Object.keys(cameraDraft).length;

  return <Panel title="导演工作台" actions={<Button disabled={!active || !documentId || controller.state === 'LOADING'}
      onClick={() => documentId && void read(documentId)}>重新读取原文档</Button>}>
    <p className="director-workspace__scope">
      只读决策台：导演意图、镜头卡与连续性都来自既有 owner 的投影。修改仍然在原文档界面完成。
    </p>

    {!documentId && <StatusMessage tone="info">
      尚未选定文档。请打开一份导演或分镜文档后再使用导演工作台。
    </StatusMessage>}
    {documentId && !active && <StatusMessage tone="info">工作台当前未激活，不会发起读取。</StatusMessage>}
    {controller.state === 'LOADING' && <p className="director-workspace__loading"><Spinner size="sm" /> 正在读取原文档…</p>}
    {controller.problem && <StatusMessage tone={controller.state === 'DENIED' ? 'warning' : 'error'}>
      [{controller.problem.code}] {controller.problem.message}
    </StatusMessage>}

    {projection && <>
      <div className="director-workspace__document">
        <strong>{projection.document.title}</strong>
        <Badge tone="neutral">{projection.document.mode}</Badge>
        <Badge tone="neutral">v{projection.document.version}</Badge>
        <Badge tone="neutral">{projection.document.status}</Badge>
        <Badge tone={projection.advisory_only ? 'info' : 'warning'}>
          {projection.advisory_only ? '仅提示 · 无执行权' : '契约异常'}
        </Badge>
      </div>

      <DirectorIntentPanel intent={projection.director_intent} projectContext={projection.project_context} />

      <section className="director-workspace__shots" aria-label="镜头卡">
        <h3>镜头卡（{projection.shot_cards.length} 张）</h3>
        {projection.shot_cards.length === 0
          ? <StatusMessage tone="info">原文档还没有镜头。镜头由原分镜界面创建，这里不会替你生成。</StatusMessage>
          : <ul>{projection.shot_cards.map(card => <ShotCardPanel
              key={card.shot_id}
              card={card}
              vocabulary={cameraVocabulary(projection.director_intent)}
              selected={card.shot_id === selectedShotId}
              onSelect={setSelectedShotId}
              onDraftCamera={(shotId, field, value) =>
                setCameraDraft(current => ({ ...current, [`${shotId}:${field}`]: value }))}
            />)}</ul>}
      </section>

      {draftCount > 0 && <StatusMessage tone="info">
        本地镜头语言草稿 {draftCount} 项（仅本次会话，未写入原文档）。
        {Object.entries(cameraDraft).map(([key, value]) => <span key={key}> {key}={value}；</span>)}
        请在原文档界面确认后再保存。
      </StatusMessage>}

      <ContinuityPanel panel={projection.continuity} />
    </>}
  </Panel>;
}
