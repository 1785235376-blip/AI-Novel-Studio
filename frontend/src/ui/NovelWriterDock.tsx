/**
 * [HERMIA-FE-20261022 W-P0-06 / N-UX-03 / N-UX-01 / N-UX-02 / N-UX-05 / X-UX-05 / N-UX-08 / N-UX-09 / N-UX-10 / N-UX-11] Novel right dock (LUMEN_NOVEL_IA §4.4).
 * Useful content OR collapse to 0 via AppShell inspector toggle — never empty void.
 * Editor-first: one solid primary CTA + outline / cast / AI sections (default open).
 * N-UX-02: AI bypass vs workflow dual-entry tightened — no new FL ids.
 * N-UX-05: first-tier panel quick links (story/check/creation/overview/history).
 * N-UX-08: CTA state machine kinds (continue/adopt/continuity) via data-cta-kind.
 * N-UX-10: 设定/世界观入口 → FL story / World*；文案明确 ≠ 分镜 Bible.
 * N-UX-11: 次入口 StoryPlanning / Continuity / PendingCanon（命令+次 CTA；不抢主 CTA；无新 FL id）。
 */
import type {ReactNode} from 'react';
import {CapabilityBadge} from './CapabilityBadge';
import type {CapabilityStatus} from '../workbench/panels';
import {NOVEL_SECONDARY_ENTRIES, type NovelSecondaryEntryId} from '../workbench/novelSecondaryEntries';
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
  onOpenCreation,
  onOpenOverview,
  onOpenWorkflow,
  onOpenSecondaryEntry,
  onSelectOutline,
  capabilityStatus = 'undetermined',
  ai,
  extras,
}: {
  chapterTitle: string;
  chapterMeta: string;
  saveLabel?: string;
  primaryCta: {label: string; onClick: () => void; disabled?: boolean; kind?: string};
  secondaryLinks?: Array<{label: string; onClick: () => void}>;
  outlineItems: Array<{id: string; label: string; hint?: string}>;
  castItems: Array<{id: string; label: string; hint?: string}>;
  onOpenStory?: () => void;
  onOpenCheck?: () => void;
  onOpenHistory?: () => void;
  onOpenCreation?: () => void;
  onOpenOverview?: () => void;
  /** Opens FL workflow surface — clearly ≠ AI writing bypass. */
  onOpenWorkflow?: () => void;
  /** N-UX-11: open StoryPlanning / Continuity / PendingCanon via existing story|check. */
  onOpenSecondaryEntry?: (id: NovelSecondaryEntryId) => void;
  onSelectOutline?: (id: string) => void;
  capabilityStatus?: CapabilityStatus;
  ai: ReactNode;
  extras?: ReactNode;
}) {
  const openSec = (id: NovelSecondaryEntryId) => {
    if (onOpenSecondaryEntry) {
      onOpenSecondaryEntry(id);
      return;
    }
    // Fallback: map to story/check without inventing FL ids
    if (id === 'story-planning') onOpenStory?.();
    else onOpenCheck?.();
  };

  return (
    <div className="novel-writer-dock" aria-label="写作右栏" data-a11y-novel-dock="true">
      <section
        className="novel-inspector-context"
        aria-label="当前写作上下文"
        data-honest-kind={(!chapterTitle || chapterTitle === '未选择章节') ? 'no_chapter' : undefined}
      >
        <span>当前章节</span>
        <strong>{chapterTitle}</strong>
        <small>{chapterMeta}{saveLabel ? ` · ${saveLabel}` : ''}</small>
        <div className="novel-writer-dock__badge-row">
          <CapabilityBadge status={capabilityStatus} />
        </div>
      </section>

      <section className="novel-writer-dock__next" aria-label="下一步">
        <button
          type="button"
          className="novel-writer-dock__primary"
          data-primary-cta="true"
          data-cta-kind={primaryCta.kind || undefined}
          aria-keyshortcuts="Enter"
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
          {onOpenStory && (
            <button type="button" className="novel-writer-dock__link" onClick={onOpenStory} data-open="story-planning">故事规划</button>
          )}
          {onOpenStory && (
            <button type="button" className="novel-writer-dock__link" onClick={onOpenStory} data-open="story-world">世界观 / 设定</button>
          )}
          {onOpenHistory && (
            <button type="button" className="novel-writer-dock__link" onClick={onOpenHistory}>版本历史</button>
          )}
        </div>
        <p className="novel-writer-dock__hint">不需要辅助时可点边缘按钮将右栏收至 0（宽屏默认展开；&lt;1280 默认折、&lt;1100 强制抽屉；折叠态会记住）。收起后主按钮沉到顶栏写作条（N-UX-09 / Lumen §4.4）。</p>
      </section>

      {/* [HERMIA-FE-20261022 N-UX-11] Secondary discoverability — does not replace primary CTA */}
      <section className="novel-writer-dock__sec" aria-label="小说次入口" data-novel-sec-entries="true">
        <span className="novel-writer-dock__sec-label">次入口 · 命令亦可搜</span>
        <div className="novel-writer-dock__sec-links">
          {NOVEL_SECONDARY_ENTRIES.map(entry => (
            <button
              key={entry.id}
              type="button"
              className="novel-writer-dock__sec-btn"
              data-sec-cta={entry.id}
              data-fl-panel={entry.panel}
              title={`${entry.label}（FL ${entry.panel} · ${entry.actionId}）`}
              onClick={() => openSec(entry.id)}
            >
              {entry.label}
            </button>
          ))}
        </div>
        <p className="novel-writer-dock__hint">
          StoryPlanning → FL <strong>story</strong>；Continuity / PendingCanon → FL <strong>check</strong> 同屏（无新 FL id）。主按钮仍是写作态机（继续写 / 采用草稿 / 看一致性）。
        </p>
      </section>

      {/* [HERMIA-FE-20261022 N-UX-05] First-tier same-screen reach — existing FL ids only */}
      <section className="novel-writer-dock__tier1" aria-label="第一梯队面板">
        <span className="novel-writer-dock__tier1-label">第一梯队 · 同屏可达</span>
        <div className="novel-writer-dock__tier1-links">
          {onOpenStory && (
            <button type="button" className="novel-writer-dock__tier1-btn" onClick={onOpenStory} data-tier1="story" data-novel-path="story-world" title="小说设定与世界观（story / World*），不是分镜 Bible">故事资料 · 设定</button>
          )}
          {onOpenCheck && (
            <button type="button" className="novel-writer-dock__tier1-btn" onClick={onOpenCheck} data-tier1="check">一致性 · Canon</button>
          )}
          {onOpenCreation && (
            <button type="button" className="novel-writer-dock__tier1-btn" onClick={onOpenCreation} data-tier1="creation">创作方案</button>
          )}
          {onOpenOverview && (
            <button type="button" className="novel-writer-dock__tier1-btn" onClick={onOpenOverview} data-tier1="overview">概览</button>
          )}
          {onOpenHistory && (
            <button type="button" className="novel-writer-dock__tier1-btn" onClick={onOpenHistory} data-tier1="history">版本历史</button>
          )}
        </div>
        <p className="novel-writer-dock__hint">「故事资料 · 设定」打开 FL <strong>story</strong>（规划 / World* / 角色），小说设定主路径；分镜侧 Bible 不在此入口（N-UX-10 · 无新 FL id）。</p>
        <p className="novel-writer-dock__hint">「一致性 · Canon」打开 FL check：Continuity 与 PendingCanon 同屏（无新 FL id）。</p>
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
            <p className="novel-writer-dock__empty" data-honest-kind="empty_selection">暂无大纲条目。可在故事资料库完善卷章；此处保留可读占位，禁止空白属性板（X-UX-01 诚实空态）。</p>
          )}
          {onOpenStory && (
            <button type="button" className="ui-button" onClick={onOpenStory} data-open="story-database">打开故事资料库 / 设定（World*）</button>
          )}
          <button type="button" className="ui-button" data-sec-cta="story-planning" data-fl-panel="story" onClick={() => openSec('story-planning')}>打开 StoryPlanning（经 story）</button>
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
            <button type="button" className="ui-button" onClick={onOpenStory} data-open="story-characters">管理角色</button>
          )}
          {onOpenStory && (
            <button type="button" className="ui-button" onClick={onOpenStory} data-open="story-world">打开世界观设定（≠ 分镜 Bible）</button>
          )}
          <button type="button" className="ui-button" data-sec-cta="continuity" data-fl-panel="check" onClick={() => openSec('continuity')}>打开 Continuity（经 check）</button>
          <button type="button" className="ui-button" data-sec-cta="pending-canon" data-fl-panel="check" onClick={() => openSec('pending-canon')}>打开 PendingCanon（经 check）</button>
        </div>
      </details>

      <details className="novel-writer-dock__section novel-writer-dock__section--ai" open>
        <summary>AI 写作旁路</summary>
        <div className="novel-writer-dock__body">
          <p className="novel-writer-dock__hint novel-writer-dock__dual-entry" role="note" data-dual-entry="ai-vs-workflow">
            <strong>生成候选</strong>走本旁路（生成 / 预览 / 采用）。
            {' '}功能导航里的 <strong>工作流编排</strong> 是另一套编排面，二者并存、不混成一面。
            {onOpenWorkflow ? (
              <>
                {' '}
                <button type="button" className="novel-writer-dock__link" onClick={onOpenWorkflow} data-open="workflow">打开工作流编排（非旁路）</button>
              </>
            ) : null}
          </p>
          {ai}
        </div>
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
