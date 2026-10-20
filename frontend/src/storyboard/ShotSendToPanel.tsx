import { useState } from 'react';
import { Badge, Button, Panel, StatusMessage } from '../ui/primitives';
import { STORYBOARD_DRAFT_NOTICE } from './storyboardOps';
import {
  SEND_TARGET_LABELS, SEND_TARGETS,
  type BoundShotTargetDraft, type SendTarget, type ShotTargetDraft, type StoryboardShotRow,
} from './storyboardWorkspaceTypes';

/**
 * "送往…"面板。
 *
 * 它**只**形成一张草稿卡：列出目标模块将会引用的确切原版本（文档版本、镜头版本、
 * 镜头摘要、已绑定的正式素材版本与视频任务针），然后交给调用方。这里没有
 * `request_id`、没有队列、没有 `dispatch`，所以它不可能执行目标模块。
 */
export function ShotSendToPanel({ row, draft, locked, orderShotIds, onPrepare, onSend, onUnavailable }: {
  row: StoryboardShotRow | undefined;
  draft: BoundShotTargetDraft | ShotTargetDraft | null;
  locked: boolean;
  orderShotIds: readonly string[];
  onPrepare: (target: SendTarget) => void;
  onSend: (target: SendTarget, draft: BoundShotTargetDraft) => void;
  onUnavailable?: () => void;
}) {
  const [chosen, setChosen] = useState<SendTarget>('IMAGE');
  const bound = draft && typeof draft.document_version === 'number' ? draft as BoundShotTargetDraft : null;

  return <Panel title="送往…">
    <p className="storyboard-send__scope">
      这里只形成草稿。目标模块是否执行、何时执行，由拿到这张卡的界面与它自己的 owner 决定；本工作区永远不会替你执行。
    </p>
    {!row && <StatusMessage tone="info">先在镜头清单里选一个镜头。</StatusMessage>}
    {row && <>
      <fieldset className="storyboard-send__targets" disabled={locked}>
        <legend>目标模块</legend>
        {SEND_TARGETS.map(target => <label key={target}>
          <input type="radio" name="storyboard-send-target" checked={chosen === target}
            onChange={() => { setChosen(target); onPrepare(target); }} />
          {SEND_TARGET_LABELS[target]}（{target}）
        </label>)}
      </fieldset>
      <Button disabled={locked} onClick={() => onPrepare(chosen)}>形成 {SEND_TARGET_LABELS[chosen]} 草稿</Button>
      {bound
        ? <section aria-label="草稿将会引用的原版本">
          <h4>这张草稿会引用的确切原版本</h4>
          <dl>
            <div><dt>分镜文档</dt><dd>{bound.document_version === null ? '尚未核对' : `v${bound.document_version}`}</dd></div>
            <div><dt>镜头身份</dt><dd>{bound.shot_id}</dd></div>
            <div><dt>镜头版本</dt><dd>v{bound.shot_version}</dd></div>
            <div><dt>镜头摘要</dt><dd><code>{bound.source_digest}</code></dd></div>
            <div><dt>正式图片</dt><dd>{bound.bindings.IMAGE ? `${bound.bindings.IMAGE.asset_id} · v${bound.bindings.IMAGE.version}` : '没有绑定（目标模块会据此判断）'}</dd></div>
            <div><dt>正式视频</dt><dd>{bound.bindings.VIDEO ? `${bound.bindings.VIDEO.asset_id} · v${bound.bindings.VIDEO.version}` : '没有绑定'}</dd></div>
            <div><dt>视频任务针</dt><dd>{bound.bindings.VIDEO ? `${bound.bindings.VIDEO.job.id} · v${bound.bindings.VIDEO.job.version}` : '没有'}</dd></div>
            <div><dt>时间线顺序</dt><dd>{orderShotIds.length} 个镜头的当前显示顺序（身份列表：{orderShotIds.join('、')}）</dd></div>
          </dl>
          <Button disabled={locked} onClick={() => onSend(chosen, bound)}>交给调用方处理这张草稿（不执行）</Button>
        </section>
        : <StatusMessage tone="info">还没有形成草稿。形成后这里会逐条列出目标模块将要引用的原版本。</StatusMessage>}
      <p>{STORYBOARD_DRAFT_NOTICE}</p>
      <p>草稿不包含请求标识、任务标识或执行开关，所以它没有被派发的可能。若目标模块当前不可用，请使用原模块的界面。</p>
      <div className="storyboard-send__availability">
        <Badge tone="neutral">图片：原图片界面</Badge>
        <Badge tone="neutral">视频：原视频界面</Badge>
        <Badge tone="neutral">时间线：原时间线界面</Badge>
        {onUnavailable && <Button onClick={onUnavailable}>目标模块不可用</Button>}
      </div>
    </>}
  </Panel>;
}
