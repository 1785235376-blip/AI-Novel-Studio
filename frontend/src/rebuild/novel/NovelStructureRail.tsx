/* [HERMIA-FE-20261022 REBUILD-W3] 小说左栏 — 按原型 aside.left：「作品结构」章节树 + 「小说面板」列表（带状态标签）。
   新组件，不复用旧 sidebar 样式；章节管理（改名 / 排序 / 移出 / 恢复）仍由原 ChapterTree 提供，收在「管理章节」里。 */
import type {ReactNode} from 'react';

export type RailChapter = {id: string; number: number; title?: string; wordCount?: number; status?: string};
export type RailPanelStatus = 'ok' | 'part' | 'local';
export type RailPanel = {id: string; label: string; status: RailPanelStatus; disabled?: boolean; title?: string};

const STATUS_LABEL: Record<RailPanelStatus, string> = {ok: '可用', part: '部分可用', local: '仅本地'};

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
  manage,
  more,
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
  /** 原章节管理（改名 / 排序 / 移出 / 恢复），默认收起。 */
  manage?: ReactNode;
  /** 全部功能（原功能导航），默认收起。 */
  more?: ReactNode;
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
          <button
            key={c.id}
            type="button"
            role="treeitem"
            aria-selected={c.id === selectedId}
            className="nv-rail__item"
            data-chapter-id={c.id}
            onClick={() => onSelect(c.id)}
          >
            <span className="nv-rail__ic" aria-hidden="true">¶</span>
            <span className="nv-rail__label">第 {c.number} 章 · {c.title || '未命名'}</span>
            {c.id === selectedId && c.status ? <span className="nv-badge nv-badge--local">{c.status}</span> : null}
          </button>
        ))}
        {onCreate ? (
          <button type="button" className="nv-rail__new" disabled={creating} onClick={onCreate}>＋ 新建章节</button>
        ) : null}
        {manage ? (
          <details className="nv-rail__more">
            <summary>管理章节（改名 · 排序 · 移出）</summary>
            <div className="nv-rail__more-body">{manage}</div>
          </details>
        ) : null}
      </div>
      <h3 className="nv-rail__h">小说面板</h3>
      <div className="nv-rail__tree" role="tree" aria-label="小说面板">
        {panels.map(p => (
          <button
            key={p.id}
            type="button"
            role="treeitem"
            aria-selected={activePanel === p.id}
            className="nv-rail__item"
            data-novel-panel={p.id}
            disabled={p.disabled}
            title={p.title}
            onClick={() => onOpenPanel(p.id)}
          >
            <span className="nv-rail__ic" aria-hidden="true">·</span>
            <span className="nv-rail__label">{p.label}</span>
            <span className={`nv-badge nv-badge--${p.status}`}>{STATUS_LABEL[p.status]}</span>
          </button>
        ))}
      </div>
      {more ? (
        <details className="nv-rail__more">
          <summary>全部功能</summary>
          <div className="nv-rail__more-body">{more}</div>
        </details>
      ) : null}
    </div>
  );
}
