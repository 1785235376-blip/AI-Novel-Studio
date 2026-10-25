/* [HERMIA-FE-20261022 REBUILD-W3] 小说左栏 — 按原型 aside.left：「作品结构」章节树 + 「小说面板」列表（带状态标签）。
   [HERMIA-FE-20261022 R1] 宽 200；状态词按原型（已接通 / 部分实现 / 仅本地交互 / 尚未接通后端）；
   「管理章节」「全部功能」不再各占一个按钮，统一收进列表末尾的「更多」。 */
import type {ReactNode} from 'react';

export type RailChapter = {id: string; number: number; title?: string; wordCount?: number; status?: string};
export type RailPanelStatus = 'ok' | 'part' | 'local' | 'off';
export type RailPanel = {id: string; label: string; status: RailPanelStatus; disabled?: boolean; title?: string};

export const RAIL_STATUS_LABEL: Record<RailPanelStatus, string> = {ok: '已接通', part: '部分实现', local: '仅本地交互', off: '尚未接通后端'};

export function NovelStructureRail({
  volumeLabel = '卷一',
  chapters,
  selectedId,
  loading,
  error,
  onSelect,
  onCreate,
  creating,
  panels,
  activePanel,
  onOpenPanel,
  more,
  pro = false,
}: {
  volumeLabel?: string;
  chapters: RailChapter[];
  selectedId?: string;
  loading?: boolean;
  error?: string | null;
  onSelect: (id: string) => void;
  onCreate?: () => void;
  creating?: boolean;
  panels: RailPanel[];
  activePanel?: string;
  onOpenPanel: (id: string) => void;
  /** 「更多」：章节管理（改名 / 排序 / 移出）+ 全部功能，默认收起。 */
  more?: ReactNode;
  /** [HERMIA-FE-20261025 DUI P0-2] Dev-progress badges only in pro; normal mode keeps only honest "暂不可用". */
  pro?: boolean;
}) {
  return (
    <div className="nv-rail" data-rebuild="novel-rail">
      <h3 className="nv-rail__h">作品结构</h3>
      <div className="nv-rail__tree" role="tree" aria-label="章节">
        <div className="nv-rail__vol">{volumeLabel}</div>
        {loading ? <p className="nv-rail__muted">正在读取章节…</p> : null}
        {error ? <p className="nv-rail__muted" role="alert">章节暂时读不到，请稍后重试。</p> : null}
        {!loading && !error && chapters.length === 0 ? <p className="nv-rail__muted">还没有章节。</p> : null}
        {chapters.map(c => (
          <button key={c.id} type="button" role="treeitem" aria-selected={c.id === selectedId} className="nv-rail__item" data-chapter-id={c.id} onClick={() => onSelect(c.id)}>
            <span className="nv-rail__ic" aria-hidden="true">¶</span>
            <span className="nv-rail__label">第 {c.number} 章 · {c.title || '未命名'}</span>
          </button>
        ))}
        {onCreate && !loading && !error ? <button type="button" className="nv-rail__new" disabled={creating} onClick={onCreate}>＋ 新建章节</button> : null}
      </div>
      <h3 className="nv-rail__h">小说面板</h3>
      <div className="nv-rail__tree" role="tree" aria-label="小说面板">
        {panels.map(p => (
          <button key={p.id} type="button" role="treeitem" aria-selected={activePanel === p.id} className="nv-rail__item" data-novel-panel={p.id} disabled={p.disabled} title={p.title} onClick={() => onOpenPanel(p.id)}>
            <span className="nv-rail__ic" aria-hidden="true">·</span>
            <span className="nv-rail__label">{p.label}</span>
            {pro ? <span className={`nv-badge nv-badge--${p.status}`}>{RAIL_STATUS_LABEL[p.status]}</span>
              : p.status === 'off' ? <span className="nv-badge nv-badge--off" data-status={p.status}>暂不可用</span> : null}
          </button>
        ))}
        {more ? (
          <details className="nv-rail__more" data-rail-more="true">
            <summary>更多（章节管理 · 全部功能）</summary>
            <div className="nv-rail__more-body">{more}</div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

/* [HERMIA-FE-20261022 R1] 原型 .novel-chapters：写作台内 168px 独立章节列（字数 + 保存状态 + 新建章节）。 */
export function NovelChapterColumn({chapters, selectedId, onSelect, onCreate, creating, volumeLabel = '卷一', loading = false, error = null}: {
  chapters: RailChapter[]; selectedId?: string; onSelect: (id: string) => void; onCreate?: () => void; creating?: boolean; volumeLabel?: string;
  /** [HERMIA-FE-20261025 DUI P0-3] Same source state as the rail: loading / error never masquerade as "no chapters". */
  loading?: boolean; error?: string | null;
}) {
  return (
    <nav className="nv-chapters" aria-label="章节树" data-rebuild="novel-chapters">
      <strong className="nv-chapters__h">章节树</strong>
      <div className="nv-chapters__vol">{volumeLabel}</div>
      {loading ? <p className="nv-rail__muted" role="status" data-chapters-state="loading">正在读取章节…</p>
        : error ? <p className="nv-rail__muted" role="alert" data-chapters-state="error">章节暂时读不到，请稍后重试。</p>
        : chapters.length === 0 ? <p className="nv-rail__muted" data-chapters-state="empty">还没有章节。</p> : null}
      {chapters.map(c => (
        <button key={c.id} type="button" className="nv-chapters__ch" aria-selected={c.id === selectedId} data-ch={c.id} onClick={() => onSelect(c.id)}>
          <span aria-hidden="true">¶</span>
          <span>第 {c.number} 章 · {c.title || '未命名'}<span className="nv-chapters__meta">{typeof c.wordCount === 'number' ? `${c.wordCount} 字` : '字数未知'}{c.status ? ` · ${c.status}` : ''}</span></span>
        </button>
      ))}
      {onCreate && !loading && !error ? <button type="button" className="nv-btn nv-chapters__new" disabled={creating} onClick={onCreate}>＋ 新建章节</button> : null}
    </nav>
  );
}
