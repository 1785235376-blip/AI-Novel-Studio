/**
 * [HERMIA-FE-20261025 U2-M6/M10] Context bar for the dual canvas: what is selected, which task is being viewed, how to
 * get back. Default shows only the current step; technical detail (capability, source) is behind <details>.
 * Notices always carry an actionable next step. No raw ids on screen (data-* only).
 */
import type {CanvasSelection, MultiEditSurface} from './selection';
import type {NavState} from './contextNav';
import {LAYOUT_PRESETS} from './workspaceRegistry';
import type {CapabilityState} from '../contracts';

const CANVAS_NAME = {image: '创作画布', video: '执行画布'} as const;
const SOURCE_NAME = {'task-center': '任务中心', 'production-job': '生产任务', 'graph-run': '画布运行'} as const;
export function ContextNavBar({nav, selection, multi, capabilities, canReturn, onReturn, onCompare, onClearSelection}: {
  nav: NavState; selection: CanvasSelection; multi: MultiEditSurface | null; capabilities: readonly CapabilityState[];
  canReturn: boolean; onReturn: () => void; onCompare: () => void; onClearSelection: () => void;
}) {
  const n = selection.ids.length;
  const step = nav.task ? `正在查看任务「${nav.task.title}」` : n > 1 ? `已选中 ${n} 个节点` : n === 1 ? '已选中 1 个节点' : '在创作画布选择节点开始';
  return <div className="uw-ctxbar" role="region" aria-label="当前位置" data-testid="uw-ctxbar" data-preset={nav.preset}
    data-task-id={nav.task?.id} data-sel-canvas={selection.canvas ?? undefined} style={{display: 'flex', flexWrap: 'wrap', gap: 8, alignItems: 'center', padding: '4px 8px', minWidth: 0}}>
    <strong data-testid="uw-ctx-step" style={{overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '40ch'}}>{step}</strong>
    <small>{LAYOUT_PRESETS[nav.preset].title}</small>
    <button type="button" className="uw-btn" data-action-id="nav.returnToOrigin" disabled={!canReturn} title={canReturn ? '回到跳转前的位置（Ctrl／⌘+Alt+R）' : '从任务跳转后才会记录原位置'} onClick={onReturn}>返回原位置</button>
    <button type="button" className="uw-btn" data-action-id="nav.compare" aria-pressed={nav.preset === 'compare'} onClick={onCompare} title="左右对照创作与执行画布（Ctrl／⌘+Alt+D）">对照</button>
    {n > 1 && <button type="button" className="uw-btn" onClick={onClearSelection}>取消多选</button>}
    {nav.notice && <p role={nav.notice.tone === 'warn' ? 'alert' : 'status'} data-testid="uw-ctx-notice" style={{margin: 0, flexBasis: '100%'}}>
      {nav.notice.text}{nav.notice.next && <> <span data-testid="uw-ctx-next">下一步：{nav.notice.next}</span></>}</p>}
    {multi && <div data-testid="uw-multi" style={{flexBasis: '100%'}}>
      <span>{multi.count} 个节点（{multi.typesLabel}）。{multi.note}</span>
      <ul style={{margin: '4px 0', paddingLeft: 18}}>{multi.fields.map(f => <li key={f.key} data-mode={f.mode} data-field={f.key}>{f.label}：{f.mode === 'editable' ? '可一起修改' : f.reason}</li>)}</ul>
    </div>}
    <details data-testid="uw-ctx-details" style={{flexBasis: '100%'}}>
      <summary>技术细节</summary>
      <ul style={{margin: 0, paddingLeft: 18}}>
        {selection.canvas && <li>选择所在：{CANVAS_NAME[selection.canvas]}</li>}
        {nav.task && <li>任务来源：{SOURCE_NAME[nav.task.source]}</li>}
        {capabilities.map(c => <li key={c.id} data-cap={c.id} data-available={c.available}>{c.reason}</li>)}
      </ul>
    </details>
  </div>;
}
