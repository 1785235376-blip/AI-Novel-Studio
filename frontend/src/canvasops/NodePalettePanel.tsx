import { useEffect, useMemo, useRef, useState } from 'react';
import { graphCatalogForSchema } from '../creative/graphDraft';
import { Badge, Button } from '../ui/primitives';
import { canvasNodeBudget, filterNodes, nodeSearchIndex } from './canvasOps';
import {
  CANVAS_NODE_CATEGORIES, CANVAS_NODE_CATEGORY_LABELS, CANVAS_SEARCH_QUERY_MAX,
  type CanvasNodeCategory, type NodePalettePanelProps,
} from './canvasOpsTypes';
import './canvasOps.css';

/**
 * 节点面板：**只读现存目录**的检索与分类视图。
 *
 * - 节点类型只能来自 `catalog.definitions`（原服务端目录）；本面板不新增节点类型、不发请求；
 * - 是否可添加只做**显示**：真正的添加仍由原创作图控制器的 `addNode()` 完成，它会重新校验
 *   图格式、必填来源、各类数量上限与可编辑性；
 * - 节点上限原样取自目录声明，达到上限时说明并建议拆分工作流，绝不抬高上限。
 */
export function NodePalettePanel({ catalog, definition, kind, editable, onKind, onAddNode, insertion }: NodePalettePanelProps) {
  const searchRef = useRef<HTMLInputElement>(null);
  useEffect(() => {
    if (insertion) { searchRef.current?.focus(); searchRef.current?.scrollIntoView?.({ block: 'nearest' }); }
  }, [insertion?.token]);
  const [query, setQuery] = useState('');
  const [category, setCategory] = useState<CanvasNodeCategory | 'ALL'>('ALL');
  const entries = useMemo(() => nodeSearchIndex(catalog), [catalog]);
  const matches = useMemo(() => filterNodes(catalog, query, category), [catalog, query, category]);
  /** 当前图格式允许的节点类型：沿用原所有者的 `graphCatalogForSchema`。 */
  const allowed = useMemo(
    () => new Set(graphCatalogForSchema(catalog?.definitions ?? [], definition.schema_version).map(row => row.id)),
    [catalog, definition.schema_version],
  );
  const budget = canvasNodeBudget(catalog, definition);
  const selected = entries.find(entry => entry.id === kind);
  const selectedAllowed = Boolean(selected) && allowed.has(selected!.id);

  if (!catalog) {
    return <section aria-label="节点面板">
      <h3>节点面板</h3>
      <p className="canvas-ops__note">节点目录尚未读取：请先用「明确读取…节点目录」按需读取一次。目录读取由原创作图控制器发起，本面板自身不发任何请求。</p>
    </section>;
  }
  return <section aria-label="节点面板" onKeyDown={event => {
    if (insertion && event.key === 'Escape' && !event.nativeEvent.isComposing && event.keyCode !== 229) {
      event.preventDefault(); event.stopPropagation(); insertion.onCancel();
    }
  }}>
    <h3>节点面板</h3>
    {insertion && <div className="canvas-ops__note" role="status">
      <p>在画布位置 {Math.round(insertion.position.x)}, {Math.round(insertion.position.y)} 添加节点。搜索并选择类型；需要来源时，使用上方原来源控件明确读取、选择，再点击添加。仅修改草稿，需明确保存。</p>
      {insertion.issue && <p>{insertion.issue}</p>}
      <Button onClick={insertion.onCancel}>取消指定位置添加</Button>
    </div>}
    <div className="canvas-ops__row">
      <label className="canvas-ops__field"><span>搜索节点</span>
        <input ref={searchRef} type="search" aria-label="搜索节点" value={query} maxLength={CANVAS_SEARCH_QUERY_MAX}
          placeholder="按中文名、机器码或端口搜索" onChange={event => setQuery(event.target.value)} />
      </label>
      <label className="canvas-ops__field"><span>节点分类</span>
        <select aria-label="节点分类" value={category} onChange={event => setCategory(event.target.value as CanvasNodeCategory | 'ALL')}>
          <option value="ALL">全部分类</option>
          {CANVAS_NODE_CATEGORIES.map(item => <option key={item} value={item}>{CANVAS_NODE_CATEGORY_LABELS[item]}</option>)}
        </select>
      </label>
    </div>
    <p>只读现存目录：共 {entries.length} 个节点定义，当前命中 {matches.length} 个。分类与检索都只在本机内存中进行，不会因为检索而调用模型。</p>
    {matches.length === 0
      ? <p className="canvas-ops__empty" role="status">没有匹配的节点定义：请调整检索词或分类。本面板不会凭空新增节点类型。</p>
      : <ul className="canvas-ops__list">{matches.map(({ entry, match }) => {
        const usable = allowed.has(entry.id);
        return <li key={entry.id}>
          <button type="button" className="canvas-ops__item" aria-pressed={entry.id === kind} disabled={!usable}
            onClick={() => onKind(entry.id)} title={usable ? `选择 ${entry.label}` : `${entry.label}：当前图格式不可用`}>
            <span className="canvas-ops__item-head">
              <strong>{entry.label}</strong><code>{entry.id}</code>
              <Badge tone={entry.executable ? 'info' : 'neutral'}>{entry.executable ? '可执行' : '仅定义'}</Badge>
              {entry.id === kind && <Badge tone="info">已选</Badge>}
            </span>
            <span className="canvas-ops__ports">
              {!entry.inputs.length && !entry.outputs.length && <span className="canvas-ops__port">无输入输出端口</span>}
              {entry.inputs.map(port => <span key={`in-${port.id}`} className={`canvas-ops__port${port.required ? ' is-required' : ''}`}>
                输入 <b>{port.id}</b> {port.type}{port.required ? ' · 必填' : ''}
              </span>)}
              {entry.outputs.map(port => <span key={`out-${port.id}`} className="canvas-ops__port">
                输出 <b>{port.id}</b> {port.type}
              </span>)}
            </span>
            <small>命中 {match} · 定义不调用模型{entry.blockers.length ? ` · 阻塞：${entry.blockers.join('、')}` : ''}{usable ? '' : ' · 当前图格式不可用，需先在版本确认区明确升级'}</small>
          </button>
        </li>;
      })}</ul>}
    <div className="canvas-ops__actions">
      <Button variant="primary" disabled={!editable || !selectedAllowed || budget.full || !!insertion?.issue} onClick={onAddNode}>
        添加所选节点（由原控制器执行）
      </Button>
    </div>
    <p>节点预算：已用 {budget.used} / 上限 {budget.limit}（取自 {budget.source}）。{budget.message ?? '达到任一上限时，本工具会说明原因并建议拆分工作流；它不会抬高任何节点或任务上限。'}</p>
    <p className="canvas-ops__note">添加与保存仍由原创作图控制器完成：本面板只选择节点类型并调用它，不直接改图、不发请求。</p>
  </section>;
}
