/* [HERMIA-FE-20261022 REBUILD-W3] 小说右栏 — 按原型 aside.novel-assist：当前章节 / 下一步 / 大纲 / 角色 / AI 写作。
   [HERMIA-FE-20261022 R1] 宽 312、一屏内：AI 写作只留 4 个入口（续写 / 改写所选 / 润色 / 头脑风暴），
   完整 AI 面板收进右栏抽屉（保持挂载，生成状态不丢）。入口只预选方式并打开抽屉，不自动生成。 */
import {useState, type ReactNode} from 'react';

export type AssistLink = {id: string; label: string; onClick: () => void};
export type QuickOp = 'continue' | 'rewrite' | 'polish' | 'brainstorm';
const QUICK: Array<[QuickOp, string]> = [['continue', '续写'], ['rewrite', '改写所选'], ['polish', '润色'], ['brainstorm', '头脑风暴']];

export function NovelAssist({
  chapterTitle, chapterMeta, saveLabel, saveLocation, primaryCta, links, outlineItems, onSelectOutline,
  onOpenStory, onOpenCheck, castNote, ai, aiStatus, onQuickOp, hasChapter = true, extras,
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
  /** 完整 AI 写作面板（旧 AiWritingPanel），放在抽屉里 */
  ai: ReactNode;
  /** 当前候选状态（如「有候选待你确认」），没有就不显示 */
  aiStatus?: string;
  onQuickOp?: (op: QuickOp) => void;
  hasChapter?: boolean;
  /** 写作目标、来源隐私、生成恢复等低频工具，收在抽屉「更多」里 */
  extras?: ReactNode;
}) {
  const [drawer, setDrawer] = useState(false);
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
        <button type="button" className="nv-btn nv-btn--primary nv-assist__primary" data-primary-cta="true" data-cta-kind={primaryCta.kind || undefined} disabled={primaryCta.disabled} onClick={primaryCta.onClick}>
          {primaryCta.label}
        </button>
        <div className="nv-assist__links">
          {links.map(l => <button key={l.id} type="button" className="nv-link" data-sec-cta={l.id} onClick={l.onClick}>{l.label}</button>)}
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
          {/* [HERMIA-FE-20261022 R1] 「打开故事规划」与「下一步 · 故事规划」重复，去掉以压到一屏 */}
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
          <div className="nv-ai-quick" role="group" aria-label="AI 写作方式">
            {QUICK.map(([op, label]) => (
              <button key={op} type="button" className="nv-btn" data-ai={op} disabled={!hasChapter} onClick={() => { onQuickOp?.(op); setDrawer(true); }}>{label}</button>
            ))}
          </div>
          {aiStatus ? <span className="nv-badge nv-badge--part" data-ai-status="true">{aiStatus}</span> : null}
          <p className="nv-hint">选方式后在完整面板确认才生成；结果先成候选。</p>
          <button type="button" className="nv-link" data-open-ai-drawer="true" aria-expanded={drawer} onClick={() => setDrawer(true)}>打开完整 AI 面板{extras ? '（含写作目标等）' : ''}</button>
        </div>
      </details>
      <div className={drawer ? 'nv-ai-drawer' : 'nv-ai-drawer nv-hide'} role="dialog" aria-label="AI 写作 · 完整面板" aria-hidden={!drawer}>
        <div className="nv-ai-drawer__head">
          <strong>AI 写作</strong>
          <span className="nv-spacer" />
          <button type="button" className="nv-btn" onClick={() => setDrawer(false)}>收起</button>
        </div>
        <div className="nv-ai-drawer__body">{ai}{extras ? <details className="nv-sec"><summary>更多写作工具</summary><div className="nv-sec__body">{extras}</div></details> : null}</div>
      </div>
    </div>
  );
}
