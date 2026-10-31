import { Badge, Button } from '../ui/primitives';
import { toggleCollapse } from './canvasOps';
import type { CanvasSelectionBarProps } from './canvasOpsTypes';
import './canvasOps.css';

const PREVIEW_LIMIT = 6;

/**
 * 选择与历史：多选摘要、定位、框选计数、撤销/重做入口，以及会话内折叠/分组/标注的计数。
 *
 * 所有变更都是**回调**：本栏自己不改图、不发请求、不保存任何内容。
 * 撤销/重做只回退本地草稿操作：原控制器 `travel()` 操作的是本地 past/future 栈，
 * 它不会、也不能回滚已经发生的模型调用与费用、远端任务或已提交的审核。
 */
export function CanvasSelectionBar({
  selected, marqueeCount, past, future, editable, protectedNodeIds, local, onLocal, onFocusSelected, onSelect, onTravel,
}: CanvasSelectionBarProps) {
  const preview = selected.slice(0, PREVIEW_LIMIT);
  const focusable = selected.length === 1 ? selected[0] : null;
  const collapsed = local?.collapsed ?? [];
  const folded = focusable !== null && collapsed.includes(focusable);
  return <section aria-label="选择与历史">
    <h3>选择与历史</h3>
    <ul className="canvas-ops__counts">
      <li><Badge>{selected.length}</Badge>已选节点</li>
      <li>{marqueeCount === undefined
        ? <span>框选命中：未提供（框选由原画布负责，本栏不编造数字）</span>
        : <span>框选命中 {marqueeCount} 个节点</span>}</li>
      <li>受保护节点 {protectedNodeIds.length} 个</li>
      <li>{local ? `本地折叠 ${collapsed.length} · 分组 ${local.groups.length} · 标注 ${local.annotations.length}` : '本地折叠/分组/标注：未提供'}</li>
    </ul>
    {selected.length === 0
      ? <p className="canvas-ops__empty" role="status">当前没有选中节点：可在原画布上单击或框选，或用下方受保护节点按钮。</p>
      : <div className="canvas-ops__actions">
        {preview.map(id => <Button key={id} onClick={() => onFocusSelected(id)} title={`只选择节点 ${id}`}>定位 {id}</Button>)}
        {selected.length > PREVIEW_LIMIT && <span>另有 {selected.length - PREVIEW_LIMIT} 个已选节点未逐个列出</span>}
      </div>}
    <div className="canvas-ops__actions">
      <Button disabled={!protectedNodeIds.length} onClick={() => onSelect([...protectedNodeIds])}>只选择全部受保护节点（{protectedNodeIds.length}）</Button>
      <Button disabled={!selected.length} onClick={() => onSelect([])}>清空选择</Button>
      {local && onLocal && focusable !== null && <Button disabled={!editable} onClick={() => {
        const update = toggleCollapse(local, focusable);
        onLocal(update.state);
      }}>{folded ? `展开本地折叠 ${focusable}` : `折叠 ${focusable}（仅本地）`}</Button>}
    </div>
    <div className="canvas-ops__actions">
      <Button disabled={!editable || past <= 0} onClick={() => onTravel('UNDO')}>撤销本地草稿编辑（可撤销 {past} 步）</Button>
      <Button disabled={!editable || future <= 0} onClick={() => onTravel('REDO')}>重做本地草稿编辑（可重做 {future} 步）</Button>
    </div>
    <p className="canvas-ops__note is-warning">
      撤销/重做<strong>只回退本地草稿操作</strong>；已经发生的模型调用与费用、远端任务与已提交的审核都不会被撤销或回滚。撤销也不能移除已保存的资产绑定（原控制器会拒绝并说明）。
    </p>
    {local && <p className="canvas-ops__note">折叠、分组与标注只是本页会话内的呈现状态：它们不会写入已保存的创作图，也不会随图另存。要持久化它们，需要由原图契约所有者先做一次带类型、向后兼容的扩展（见 `canvasOpsTypes.ts` 顶部说明）。</p>}
  </section>;
}
