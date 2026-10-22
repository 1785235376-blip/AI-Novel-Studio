/* [HERMIA-FE-20261022 REBUILD-W3] 小说右栏 — 按原型 aside.novel-assist：当前章节 / 下一步 / 大纲 / 角色 / AI 写作。
   只放原型里有的简洁内容，不出现内部编号与开发说明。 */
import type {ReactNode} from 'react';

export type AssistLink = {id: string; label: string; onClick: () => void};

export function NovelAssist({
  chapterTitle,
  chapterMeta,
  saveLabel,
  saveLocation,
  primaryCta,
  links,
  outlineItems,
  onSelectOutline,
  onOpenStory,
  onOpenCheck,
  castNote,
  ai,
  extras,
}: {
  chapterTitle: string;
  chapterMeta: string;
  saveLabel?: string;
  saveLocation?: string;
  primaryCta: {label: string; onClick: () => void; disabled?: boolean; kind?: string};
  links: AssistLink[];
  outlineItems: Array<{id: string; label: string; hint?: string}>;
  onSelectOutline?: (id: string) => void;
  onOpenStory?: () => void;
  onOpenCheck?: () => void;
  castNote?: string;
  ai: ReactNode;
  extras?: ReactNode;
}) {
  return (
    <div className="nv-assist" aria-label="写作右栏" data-rebuild="novel-assist">
      <section className="nv-assist__ctx" aria-label="当前写作上下文">
        <span>当前章节</span>
        <strong>{chapterTitle}</strong>
        <small>{chapterMeta}{saveLabel ? ` · ${saveLabel}` : ''}</small>
        {saveLocation ? <div className="nv-assist__badges"><span className="nv-badge nv-badge--local">{saveLocation}</span></div> : null}
      </section>
      <section className="nv-assist__next" aria-label="下一步">
        <h4>下一步</h4>
        <button
          type="button"
          className="nv-btn nv-btn--primary nv-assist__primary"
          data-primary-cta="true"
          data-cta-kind={primaryCta.kind || undefined}
          disabled={primaryCta.disabled}
          onClick={primaryCta.onClick}
        >
          {primaryCta.label}
        </button>
        <div className="nv-assist__links">
          {links.map(l => (
            <button key={l.id} type="button" className="nv-link" data-sec-cta={l.id} onClick={l.onClick}>{l.label}</button>
          ))}
        </div>
      </section>
      <details className="nv-sec" open>
        <summary>大纲 / 章节脉络</summary>
        <div className="nv-sec__body">
          {outlineItems.length ? (
            <ul className="nv-outline">
              {outlineItems.map(item => (
                <li key={item.id}>
                  <button type="button" className="nv-outline__btn" onClick={() => onSelectOutline?.(item.id)}>{item.label}</button>
                  {item.hint ? <span className="nv-hint">{item.hint}</span> : null}
                </li>
              ))}
            </ul>
          ) : <p className="nv-hint">还没有大纲条目，可以在故事规划里补充。</p>}
          {onOpenStory ? <button type="button" className="nv-btn" onClick={onOpenStory} data-open="story-planning">打开故事规划</button> : null}
        </div>
      </details>
      <details className="nv-sec" open>
        <summary>角色 / 登场</summary>
        <div className="nv-sec__body">
          <p className="nv-hint">{castNote || '本章还没有关联角色。'}</p>
          <div className="nv-row">
            {onOpenStory ? <button type="button" className="nv-btn" onClick={onOpenStory} data-open="story-characters">管理角色</button> : null}
            {onOpenCheck ? <button type="button" className="nv-btn" onClick={onOpenCheck}>一致性检查</button> : null}
          </div>
        </div>
      </details>
      <details className="nv-sec nv-sec--ai novel-writer-dock__section--ai" open>
        <summary>AI 写作</summary>
        <div className="nv-sec__body">
          <p className="nv-hint">生成的内容先作为候选，需要你确认采用才会写进正文。</p>
          {ai}
        </div>
      </details>
      {extras ? (
        <details className="nv-sec">
          <summary>更多</summary>
          <div className="nv-sec__body">{extras}</div>
        </details>
      ) : null}
    </div>
  );
}
