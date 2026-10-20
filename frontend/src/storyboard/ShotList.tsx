import { Badge, Button, EmptyState, StatusMessage } from '../ui/primitives';
import { movesToOrder, STORYBOARD_DRAFT_NOTICE, type ShotMoveInput } from './storyboardOps';
import type { StoryboardShotRow, StoryboardSurfaceState } from './storyboardWorkspaceTypes';
import { ShotCard } from './ShotCard';

/**
 * 镜头清单。列表是**唯一**的镜头选择来源：卡片、详情面板、"送往"面板共用同一个
 * `selectedShotId`，不存在第二份选择状态。
 *
 * 顺序：按钮先在本地算出目标顺序，再折算成一串 canonical move 交给控制器。
 * 移动只改显示序号；`shot_id` 一直跟着同一个镜头。
 */
export function ShotList({ rows, selectedShotId, onSelect, onReorder, orderSaved, renumbered, state, problem, loading, onRead, onResetOrder, canRead }: {
  rows: StoryboardShotRow[];
  selectedShotId: string;
  onSelect: (shotId: string) => void;
  onReorder: (moves: ShotMoveInput[]) => void;
  orderSaved: boolean;
  renumbered: string[];
  state: StoryboardSurfaceState;
  problem?: { code: string; message: string };
  loading: boolean;
  onRead: () => void;
  onResetOrder: () => void;
  canRead: boolean;
}) {
  const visible = rows.map(row => row.shot.shot_id);

  const reposition = (shotId: string, target: string[]) => onReorder(movesToOrder(rows.map(row => row.shot), target));
  const swap = (index: number, offset: number) => {
    const target = [...visible];
    const other = index + offset;
    [target[index], target[other]] = [target[other], target[index]];
    reposition(visible[index], target);
  };

  return <section className="storyboard-shot-list" aria-label="分镜镜头清单">
    <header className="storyboard-shot-list__header">
      <h3>镜头清单</h3>
      <Badge tone="neutral">{rows.length} 个镜头</Badge>
      {!orderSaved && <Badge tone="warning">显示顺序草稿尚未保存</Badge>}
    </header>
    {state === 'IDLE' && <p className="storyboard-shot-list__hint">尚未读取。点击"读取已保存分镜"后这里才会显示原文档里的镜头。</p>}
    {state === 'LOADING' && <p className="storyboard-shot-list__hint" role="status">正在读取原分镜…</p>}
    {state === 'FAILED' && <>
      <StatusMessage tone="error">分镜读取失败{problem ? `（${problem.code}）` : ''}：{problem?.message ?? '请重新读取原文档。'}</StatusMessage>
      <p className="storyboard-shot-list__hint">失败不是"暂无分镜"：原文档可能有镜头，只是这次没有读到。</p>
      <Button disabled={loading} onClick={onRead}>重新读取原分镜</Button>
    </>}
    {state === 'DENIED' && <StatusMessage tone="warning">当前会话无权读取这份分镜。请核对身份与项目范围后重新打开工作区。</StatusMessage>}
    {state === 'EMPTY' && canRead && <EmptyState title="这份分镜还没有镜头" detail="原文档确实返回了 0 个镜头。请到原分镜界面添加镜头后再回到这里；本工作区不会替你创建镜头。" />}
    {rows.length > 0 && <ol className="storyboard-shot-list__items">
      {rows.map((row, index) => <li key={row.shot.shot_id} className="storyboard-shot-list__item">
        <ShotCard row={row} selected={row.shot.shot_id === selectedShotId} onSelect={onSelect} staleness={row.staleness} />
        <div className="storyboard-shot-list__move">
          <span className="storyboard-shot-list__position">位置 {index + 1}（显示序号 {row.summary.number}）</span>
          <Button disabled={index === 0} onClick={() => reposition(row.shot.shot_id, [row.shot.shot_id, ...visible.filter(id => id !== row.shot.shot_id)])}>移到最前</Button>
          <Button disabled={index === 0} onClick={() => swap(index, -1)}>上移</Button>
          <Button disabled={index === visible.length - 1} onClick={() => swap(index, 1)}>下移</Button>
          <Button disabled={index === visible.length - 1} onClick={() => reposition(row.shot.shot_id, [...visible.filter(id => id !== row.shot.shot_id), row.shot.shot_id])}>移到最后</Button>
          {renumbered.includes(row.shot.shot_id) && <Badge tone="info">显示序号已变（身份 {row.shot.shot_id} 不变）</Badge>}
        </div>
        {!orderSaved && <p className="storyboard-shot-list__identity">拖动的结果只在本页：原文档里的身份仍是 {row.summary.shot_id}，一条 move 也还没有保存。</p>}
      </li>)}
    </ol>}
    {!orderSaved && <div className="storyboard-shot-list__draft">
      <p>{STORYBOARD_DRAFT_NOTICE}</p>
      <p>原 owner 的内容摘要包含显示序号：保存这份顺序会让这些镜头的版本前进、撤销分镜批准，并丢弃与旧序号不一致的绑定。这一结论来自原文档，不是这里的判断。</p>
      <Button onClick={onResetOrder}>放弃顺序草稿，恢复原文档顺序</Button>
    </div>}
  </section>;
}
