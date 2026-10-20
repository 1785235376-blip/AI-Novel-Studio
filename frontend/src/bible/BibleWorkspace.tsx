import { useEffect } from 'react';

import { Badge, Button, Panel, Spinner, StatusMessage } from '../ui/primitives';
import { CharacterBiblePanel } from './CharacterBiblePanel';
import { SceneBiblePanel } from './SceneBiblePanel';
import { useBible } from './useBible';
import type { BibleClient } from './bibleTypes';

import './bibleWorkspace.css';

/**
 * Round2-B 角色与场景圣经工作区。
 *
 * **纯只读工作面**：本项目里唯一一个连"本地草稿"都没有的 Studio 面板 —— 没有编辑、
 * 没有保存、没有修改入口，因为 authoring 仍然走既有 `WorldService` 记录路径。
 *
 * 它只渲染 `GET /api/projects/{nid}/studio/bible` 的 projection：不复制数据、不推导、
 * 不猜测。未 authoring 的维度显示 `UNKNOWN`，DRAFT 记录标注非 canon，资产引用逐个标注
 * RESOLVED / UNRESOLVED。
 */
export function BibleWorkspace({ client, active = true }: {
  client: BibleClient | null;
  active?: boolean;
}) {
  const controller = useBible(client);
  const { read, reset } = controller;

  useEffect(() => {
    if (!active) { reset(); return; }
    void read();
  }, [active, read, reset]);

  const projection = controller.projection;
  const gapCount = projection
    ? projection.gaps.characters.length + projection.gaps.scenes.length
    : 0;

  return <Panel title="角色与场景圣经" actions={
      <Button disabled={!active || controller.state === 'LOADING'}
              onClick={() => void read()}>重新读取</Button>}>
    <p className="bible-workspace__scope">
      只读设定参考：所有事实来自既有 owner 的投影。这里没有编辑入口，
      修改角色与场景设定请回到原记录界面完成。
    </p>

    {!active && <StatusMessage tone="info">工作区当前未激活，不会发起读取。</StatusMessage>}
    {controller.state === 'LOADING' && <p className="bible-workspace__loading"><Spinner size="sm" /> 正在读取原记录…</p>}
    {controller.problem && <StatusMessage tone={controller.state === 'DENIED' ? 'warning' : 'error'}>
      [{controller.problem.code}] {controller.problem.message}
    </StatusMessage>}

    {projection && <>
      <div className="bible-workspace__context">
        <strong>{projection.project_context.title || projection.project_id}</strong>
        <Badge tone="neutral">题材 {projection.project_context.genre || '未提供'}</Badge>
        <Badge tone="info">仅提示 · 无执行权</Badge>
        {!projection.world_owner_available &&
          <Badge tone="warning">世界记录 owner 不可用，外形/行为/关系维度必然为 UNKNOWN</Badge>}
      </div>

      <div className="bible-workspace__summary">
        <Badge tone="neutral">角色 {projection.character_bible.character_count}</Badge>
        <Badge tone="neutral">场景 {projection.scene_bible.location_count}</Badge>
        <Badge tone={gapCount > 0 ? 'warning' : 'success'}>
          {gapCount > 0 ? `未 authoring 维度 ${gapCount} 项` : '所有维度都已 authoring'}
        </Badge>
      </div>

      <section className="bible-workspace__section" aria-label="角色圣经">
        <h3>角色圣经（{projection.character_bible.character_count}）</h3>
        {projection.character_bible.entries.length === 0
          ? <StatusMessage tone="info">
              这个项目还没有角色记录。角色由原记录界面创建，这里不会替你生成。
            </StatusMessage>
          : projection.character_bible.entries.map(entry =>
              <CharacterBiblePanel key={entry.character_id} entry={entry} />)}
      </section>

      <section className="bible-workspace__section" aria-label="场景圣经">
        <h3>场景圣经（{projection.scene_bible.location_count}）</h3>
        {projection.scene_bible.entries.length === 0
          ? <StatusMessage tone="info">
              这个项目还没有地点记录。地点由原记录界面创建，这里不会替你生成。
            </StatusMessage>
          : projection.scene_bible.entries.map(entry =>
              <SceneBiblePanel key={entry.location_id} entry={entry} />)}
      </section>
    </>}
  </Panel>;
}
