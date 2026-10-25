/* [HERMIA-FE-20261022 REBUILD-W3] 小说左栏 — 按原型 aside.left：「作品结构」章节树 + 「小说面板」列表（带状态标签）。
   [HERMIA-FE-20261022 R1] 宽 200；状态词按原型（已接通 / 部分实现 / 仅本地交互 / 尚未接通后端）；
   「管理章节」「全部功能」不再各占一个按钮，统一收进列表末尾的「更多」。 */
import type {ReactNode} from 'react';
import {useT, useTz} from '../../i18n'; // [HERMIA-FE-20261025 I18N P2] left rail strings

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
}) {
  const t = useT(), tz = useTz();
  return (
    <div className="nv-rail" data-rebuild="novel-rail">
      <h3 className="nv-rail__h">{t('rail.structure')}</h3>
      <div className="nv-rail__tree" role="tree" aria-label={t('rail.chapters')}>
        <div className="nv-rail__vol">{tz(volumeLabel)}</div>
        {loading ? <p className="nv-rail__muted">{t('rail.loading')}</p> : null}
        {error ? <p className="nv-rail__muted" role="alert">{t('rail.error')}</p> : null}
        {!loading && !error && chapters.length === 0 ? <p className="nv-rail__muted">{t('rail.noChapters')}</p> : null}
        {chapters.map(c => (
          <button key={c.id} type="button" role="treeitem" aria-selected={c.id === selectedId} className="nv-rail__item" data-chapter-id={c.id} onClick={() => onSelect(c.id)}>
            <span className="nv-rail__ic" aria-hidden="true">¶</span>
            <span className="nv-rail__label">{t('pat.chapter', {n: c.number, title: c.title || t('rail.untitled')})}</span>
          </button>
        ))}
        {onCreate ? <button type="button" className="nv-rail__new" disabled={creating} onClick={onCreate}>{t('rail.new')}</button> : null}
      </div>
      <h3 className="nv-rail__h">{t('rail.panels')}</h3>
      <div className="nv-rail__tree" role="tree" aria-label={t('rail.panels')}>
        {panels.map(p => (
          <button key={p.id} type="button" role="treeitem" aria-selected={activePanel === p.id} className="nv-rail__item" data-novel-panel={p.id} disabled={p.disabled} title={p.title ? tz(p.title) : undefined} onClick={() => onOpenPanel(p.id)}>
            <span className="nv-rail__ic" aria-hidden="true">·</span>
            <span className="nv-rail__label">{tz(p.label)}</span>
            <span className={`nv-badge nv-badge--${p.status}`}>{tz(RAIL_STATUS_LABEL[p.status])}</span>
          </button>
        ))}
        {more ? (
          <details className="nv-rail__more" data-rail-more="true">
            <summary>{t('rail.more')}</summary>
            <div className="nv-rail__more-body">{more}</div>
          </details>
        ) : null}
      </div>
    </div>
  );
}

/* [HERMIA-FE-20261022 R1] 原型 .novel-chapters：写作台内 168px 独立章节列（字数 + 保存状态 + 新建章节）。 */
export function NovelChapterColumn({chapters, selectedId, onSelect, onCreate, creating, volumeLabel = '卷一'}: {
  chapters: RailChapter[]; selectedId?: string; onSelect: (id: string) => void; onCreate?: () => void; creating?: boolean; volumeLabel?: string;
}) {
  const t = useT(), tz = useTz();
  return (
    <nav className="nv-chapters" aria-label={t('rail.tree')} data-rebuild="novel-chapters">
      <strong className="nv-chapters__h">{t('rail.tree')}</strong>
      <div className="nv-chapters__vol">{tz(volumeLabel)}</div>
      {chapters.length === 0 ? <p className="nv-rail__muted">{t('rail.noChapters')}</p> : null}
      {chapters.map(c => (
        <button key={c.id} type="button" className="nv-chapters__ch" aria-selected={c.id === selectedId} data-ch={c.id} onClick={() => onSelect(c.id)}>
          <span aria-hidden="true">¶</span>
          <span>{t('pat.chapter', {n: c.number, title: c.title || t('rail.untitled')})}<span className="nv-chapters__meta">{typeof c.wordCount === 'number' ? t('pat.chars', {n: c.wordCount}) : t('rail.wordsUnknown')}{c.status ? ` · ${tz(c.status)}` : ''}</span></span>
        </button>
      ))}
      {onCreate ? <button type="button" className="nv-btn nv-chapters__new" disabled={creating} onClick={onCreate}>{t('rail.new')}</button> : null}
    </nav>
  );
}
