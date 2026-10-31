/**
 * [HERMIA-FE-20261022] H-P1-03 · 双画布空白处「加节点」最小菜单。
 * 只选类型；真正添加仍走原控制器 addNode / 指定位置插入。拖素材＝引用（见 GraphCanvas drop）。
 */
import { useEffect, useMemo, useRef, useState } from 'react';
import { Badge, Button } from '../ui/primitives';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphDefinitionId } from '../creative/studioGraphTypes';
import {
  ADD_NODE_NEEDS_SOURCE, type AddNodeCanvasRole, filterAddNodeTypes,
} from './addNodeMenu';
import { CANVAS_SEARCH_QUERY_MAX } from './canvasOpsTypes';
import './canvasOps.css';

export type GraphAddNodeMenuProps = {
  open: boolean;
  /** 视口内近似锚点（CSS px），菜单在附近浮出。 */
  anchor?: { left: number; top: number };
  catalog?: StudioGraphCatalog;
  definition: StudioGraphDefinition;
  role?: AddNodeCanvasRole;
  editable: boolean;
  issue?: string;
  onRoleChange?: (role: AddNodeCanvasRole) => void;
  onPick: (kind: StudioGraphDefinitionId) => void;
  onCancel: () => void;
};

export function GraphAddNodeMenu({
  open, anchor, catalog, definition, role = 'creation', editable, issue, onRoleChange, onPick, onCancel,
}: GraphAddNodeMenuProps) {
  const searchRef = useRef<HTMLInputElement>(null);
  const [query, setQuery] = useState('');
  useEffect(() => {
    if (!open) { setQuery(''); return; }
    searchRef.current?.focus();
  }, [open, anchor?.left, anchor?.top]);
  const matches = useMemo(
    () => filterAddNodeTypes(catalog, definition, role, query),
    [catalog, definition, role, query],
  );
  if (!open) return null;
  const left = Math.max(8, anchor?.left ?? 24);
  const top = Math.max(8, anchor?.top ?? 24);
  return <div
    className="canvas-ops__add-menu"
    role="dialog"
    aria-label="加节点最小菜单"
    data-add-node-menu="true"
    data-canvas-role={role}
    style={{ left, top }}
    onKeyDown={event => {
      if (event.key === 'Escape' && !event.nativeEvent.isComposing && event.keyCode !== 229) {
        event.preventDefault(); event.stopPropagation(); onCancel();
      }
    }}
  >
    <header className="canvas-ops__add-menu-head">
      <strong>添加节点</strong>
      <span className="canvas-ops__note" style={{ padding: 0, border: 0, background: 'transparent' }}>
        {role === 'creation' ? '创作过滤' : role === 'execution' ? '执行过滤' : '全部类型'} · 仅草稿
      </span>
      <Button type="button" variant="ghost" onClick={onCancel}>取消</Button>
    </header>
    <p className="canvas-ops__note">
      空白处右键 / A / Shift+F10 打开。拖入素材＝<strong>引用</strong>（不复制文件、不自动开任务）。需来源的类型只会选中，仍须在原控件明确读取后再添加。
    </p>
    {issue && <p className="canvas-ops__note is-warning" role="status">{issue}</p>}
    <div className="canvas-ops__row" role="group" aria-label="画布类型过滤">
      {([['creation', '创作'], ['execution', '执行'], ['all', '全部']] as const).map(([value, label]) =>
        <Button key={value} type="button" variant="ghost" aria-pressed={role === value} disabled={!onRoleChange}
          onClick={() => onRoleChange?.(value)}>{label}</Button>)}
    </div>
    <label className="canvas-ops__field"><span>搜索节点类型</span>
      <input ref={searchRef} type="search" aria-label="搜索加节点类型" value={query} maxLength={CANVAS_SEARCH_QUERY_MAX}
        placeholder="例如：引用、文本、分镜" onChange={event => setQuery(event.target.value)} />
    </label>
    {!catalog
      ? <p className="canvas-ops__empty" role="status">节点目录尚未读取：请先明确读取目录。本菜单不发请求。</p>
      : matches.length === 0
        ? <p className="canvas-ops__empty" role="status">当前过滤下没有可用类型。可切换「全部」或调整搜索；不会凭空新增类型。</p>
        : <ul className="canvas-ops__list" aria-label="可加节点类型">{matches.map(({ entry }) => {
          const needsSource = ADD_NODE_NEEDS_SOURCE.has(entry.id);
          return <li key={entry.id}>
            <button type="button" className="canvas-ops__item" disabled={!editable}
              data-node-kind={entry.id}
              onClick={() => { if (editable) onPick(entry.id); }}
              title={needsSource ? `${entry.label}：需先明确选择来源` : `添加 ${entry.label}`}>
              <span className="canvas-ops__item-head">
                <strong>{entry.label}</strong>
                <code>{entry.id}</code>
                <Badge tone={entry.executable ? 'info' : 'neutral'}>{entry.executable ? '可执行' : '展示/引用'}</Badge>
                {needsSource && <Badge tone="warning">需来源</Badge>}
              </span>
              <small>{needsSource ? '选中后请在原添加区明确读取来源，再点添加' : '点击即按落点加入草稿（仍需保存）'}</small>
            </button>
          </li>;
        })}</ul>}
  </div>;
}


/** 宿主：在非组件 view 函数里挂载最小菜单（持有创作/执行过滤态）。 */
export function StudioGraphAddNodeHost(props: Omit<GraphAddNodeMenuProps, 'role' | 'onRoleChange'> & { role?: AddNodeCanvasRole }) {
  const [role, setRole] = useState<AddNodeCanvasRole>(props.role ?? 'creation');
  return <GraphAddNodeMenu {...props} role={role} onRoleChange={setRole} />;
}
