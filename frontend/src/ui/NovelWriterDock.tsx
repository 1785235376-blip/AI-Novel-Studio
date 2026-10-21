/**
 * [HERMIA-FE-20261022 W-P0-06] Novel right dock (LUMEN_NOVEL_IA §4.4).
 * Useful content OR collapse to 0 via AppShell inspector toggle — never empty void.
 * Editor-first: one solid primary CTA + outline / cast / AI sections (default open).
 */
import type {ReactNode} from 'react';
import './NovelWriterDock.css';

export function NovelWriterDock({
  chapterTitle,
  chapterMeta,
  saveLabel,
  primaryCta,
  secondaryLinks,
  outlineItems,
  castItems,
  onOpenStory,
  onOpenCheck,
  onOpenHistory,
  onSelectOutline,
  ai,
  extras,
}: {
  chapterTitle: string;
  chapterMeta: string;
  saveLabel?: string;
  primaryCta: {label: string; onClick: () => void; disabled?: boolean};
  secondaryLinks?: Array<{label: string; onClick: () => void}>;
  outlineItems: Array<{id: string; label: string; hint?: string}>;
  castItems: Array<{id: string; label: string; hint?: string}>;
  onOpenStory?: () => void;
  onOpenCheck?: () => void;
  onOpenHistory?: () => void;
  onSelectOutline?: (id: string) => void;
  ai: ReactNode;
  extras?: ReactNode;
}) {
  return (
    <div className="novel-writer-dock" aria-label="写作右栏">
      <section className="novel-inspector-context" aria-label="当前写作上下文">
        <span>当前章节</span>
        <strong>{chapterTitle}</strong>
        <small>{chapterMeta}{saveLabel ? ` · ${saveLabel}` : ''}</small>
      </section>

      <section className="novel-writer-dock__next" aria-label="下一步">
        <button
          type="button"
          className="novel-writer-dock__primary"
          disabled={primaryCta.disabled}
          onClick={primaryCta.onClick}
        >
          {primaryCta.label}
        </button>
        <div className="novel-writer-dock__links">
          {(secondaryLinks || []).map(link => (
            <button key={link.label} type="button" className="novel-writer-dock__link" onClick={link.onClick}>
              {link.label}
            </button>
          ))}
          {onOpenHistory && (
            <button type="button" className="novel-writer-dock__link" onClick={onOpenHistory}>版本历史</button>
          )}
        </div>
        <p className="novel-writer-dock__hint">不需要辅助时可点检视器边缘按钮将右栏收至 0，把空间还给正文（Lumen §4.4）。</p>
      </section>

      <details className="novel-writer-dock__section" open>
        <summary>大纲 / 章节脉络</summary>
        <div className="novel-writer-dock__body">
          {outlineItems.length ? (
            <ul className="novel-writer-dock__outline">
              {outlineItems.map(item => (
                <li key={item.id}>
                  {onSelectOutline ? (
                    <button type="button" onClick={() => onSelectOutline(item.id)}>{item.label}</button>
                  ) : (
                    <strong>{item.label}</strong>
                  )}
                  {item.hint && <span className="novel-writer-dock__hint">{item.hint}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="novel-writer-dock__empty">暂无大纲条目。可在故事资料库完善卷章；此处保留可读占位，禁止空白属性板。</p>
          )}
          {onOpenStory && (
            <button type="button" className="ui-button" onClick={onOpenStory}>打开故事资料库</button>
          )}
        </div>
      </details>

      <details className="novel-writer-dock__section" open>
        <summary>角色 / 登场</summary>
        <div className="novel-writer-dock__body">
          {castItems.length ? (
            <ul className="novel-writer-dock__cast">
              {castItems.map(item => (
                <li key={item.id}>
                  <strong>{item.label}</strong>
                  {item.hint && <span className="novel-writer-dock__hint">{item.hint}</span>}
                </li>
              ))}
            </ul>
          ) : (
            <p className="novel-writer-dock__empty">本章尚未挂接角色。写作右栏始终保留此区；需要时打开故事资料库。</p>
          )}
          {onOpenStory && (
            <button type="button" className="ui-button" onClick={onOpenStory}>管理角色</button>
          )}
          {onOpenCheck && (
            <button type="button" className="ui-button" onClick={onOpenCheck}>一致性检查</button>
          )}
        </div>
      </details>

      <details className="novel-writer-dock__section novel-writer-dock__section--ai" open>
        <summary>AI 写作</summary>
        <div className="novel-writer-dock__body">{ai}</div>
      </details>

      {extras ? (
        <details className="novel-writer-dock__section" open>
          <summary>更多</summary>
          <div className="novel-writer-dock__body">{extras}</div>
        </details>
      ) : null}
    </div>
  );
}
