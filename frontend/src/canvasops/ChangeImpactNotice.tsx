import { Badge } from '../ui/primitives';
import { classifyGraphChange } from './canvasOps';
import type { ChangeImpactNoticeProps } from './canvasOpsTypes';
import './canvasOps.css';

/**
 * 变更影响：用 `classifyGraphChange` 判断当前草稿差异是**只影响呈现**还是**可能影响生成**。
 *
 * 分类是保守的：只有全部差异都落在「节点位置 / 画布视口 / 无差异」之内时才会显示
 * `PRESENTATION`；参数、来源绑定、节点与连接的增删改、图格式与任何未知字段一律计入
 * `GENERATION_AFFECTING`。
 *
 * 两条必须说清的事实（也是本组件存在的理由）：
 * 1. 移动卡片（改坐标）本身永远不会重新运行模型、入队任务或产生费用；
 * 2. 这个本地判断永远不会绕过原图的版本与摘要校验：保存、预览、执行与审核仍由原所有者逐项确认。
 */
export function ChangeImpactNotice({ definition, base, dirty }: ChangeImpactNoticeProps) {
  const classification = classifyGraphChange(base, definition);
  const presentation = classification.verdict === 'PRESENTATION';
  return <section aria-label="变更影响" data-canvas-ops-verdict={classification.verdict} data-canvas-ops-dirty={dirty ? 'true' : 'false'}>
    <h3>变更影响</h3>
    <p>
      当前草稿差异分类：<Badge tone={presentation ? 'success' : 'warning'}>{presentation ? '仅呈现' : '可能影响生成'}</Badge>{' '}
      <code>{classification.verdict}</code>
    </p>
    <ul className="canvas-ops__counts">
      <li>与已保存版本比较：{base ? '已读取的已保存定义（版本号由原图记录提供，本提示不推断）' : '尚无已保存版本'}</li>
      <li>未保存修改：{dirty ? '有' : '无'}</li>
      <li>节点 {definition.nodes.length} 个 · 连接 {definition.edges.length} 条</li>
    </ul>
    {!base && <p className="canvas-ops__note is-warning" role="status">尚无已保存版本可比：未保存内容一律按 <code>GENERATION_AFFECTING</code> 保守处理，直到你明确保存并由原服务端返回版本与摘要。</p>}
    <ul>{classification.messages.map(message => <li key={message}>{message}</li>)}</ul>
    <p className="canvas-ops__codes">原因码：{classification.reasonCodes.map(code =>
      <code key={code} data-canvas-ops-reason={code}>{code}</code>)}</p>
    <p className="canvas-ops__note">
      移动卡片（只改变节点位置）<strong>不会重新运行模型</strong>：坐标不是执行输入，本工具也不会因为布局、折叠、分组或标注而调用模型、入队任务或提交审核。
      {' '}只有上面的原因码涉及参数、来源绑定、节点或连接变化时，才需要在原运行流程中重新预览并逐项确认。
    </p>
    <p className="canvas-ops__note is-warning">
      本判断只基于本地草稿，<strong>永远不会绕过原图的版本与摘要校验</strong>：保存仍按 <code>expected_version</code> 进行，执行仍需已审核的预览摘要，撤销/重做也不会回滚已发生的调用与费用。
    </p>
  </section>;
}
