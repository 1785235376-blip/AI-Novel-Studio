/* [HERMIA-FE-20261022 R1] 原型 #orient「第一次打开」指引行 + 模块页签条 .tabs。
   指引「收起」记在 localStorage（studio-novel-orient-dismissed），只影响显示。 */
import {useState} from 'react';

const KEY = 'studio-novel-orient-dismissed';
const read = () => { try { return localStorage.getItem(KEY) === '1'; } catch { return false; } };

export function NovelOrient({what, can, effect}: {what: string; can: string; effect: string}) {
  const [hidden, setHidden] = useState(read);
  if (hidden) return null;
  return (
    <div className="nv-orient" id="orient" role="region" aria-label="当前创作指引">
      <span className="nv-orient__chip">第一次打开</span>
      <div className="nv-orient__steps">
        <span><b>在创作什么</b>：{what}</span>
        <span><b>现在能做什么</b>：{can}</span>
        <span><b>操作会影响什么</b>：{effect}</span>
      </div>
      <button type="button" className="nv-orient__dismiss" aria-label="收起指引" onClick={() => { try { localStorage.setItem(KEY, '1'); } catch { /* 存不了就只本次收起 */ } setHidden(true); }}>收起</button>
    </div>
  );
}

export type ModTab = {id: string; label: string; onClick: () => void; selected?: boolean; disabled?: boolean};
export function NovelModTabs({tabs, badge}: {tabs: ModTab[]; badge?: string}) {
  return (
    <div className="nv-tabs" role="tablist" aria-label="工作区视图">
      {tabs.map(t => <button key={t.id} type="button" role="tab" className="nv-tabs__tab" data-view={t.id} aria-selected={!!t.selected} disabled={t.disabled} onClick={t.onClick}>{t.label}</button>)}
      <span className="nv-spacer" />
      {badge ? <span className="nv-badge nv-badge--local">{badge}</span> : null}
    </div>
  );
}
