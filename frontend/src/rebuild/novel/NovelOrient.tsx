/* [HERMIA-FE-20261022 R1] 原型 #orient「第一次打开」指引行 + 模块页签条 .tabs。
   指引「收起」记在 localStorage（studio-novel-orient-dismissed），只影响显示。 */
import {useState} from 'react';
import {useT, useTz} from '../../i18n'; // [HERMIA-FE-20261025 I18N P1] onboarding bar + tabs

const KEY = 'studio-novel-orient-dismissed';
/** [HERMIA-FE-20261025 DUI P1-9] 「不再显示」：所有模块的指引都不再出现（持久化）。 */
export const ORIENT_ALL_KEY = 'studio-orient-dismissed-all';

export function NovelOrient({what, can, effect, storageKey = KEY}: {what: string; can: string; effect: string; /** [HERMIA-FE-20261022 R2] 每个模块各自记住收起 */ storageKey?: string}) {
  const t = useT(), tz = useTz();
  const [hidden, setHidden] = useState(() => { try { return localStorage.getItem(storageKey) === '1' || localStorage.getItem(ORIENT_ALL_KEY) === '1'; } catch { return false; } });
  if (hidden) return null;
  return (
    <div className="nv-orient" id="orient" role="region" aria-label={t('orient.region')}>
      <span className="nv-orient__chip">{t('orient.chip')}</span>
      <div className="nv-orient__steps">
        <span><b>{t('orient.what')}</b>{t('context.sep')}{tz(what)}</span>
        <span><b>{t('orient.can')}</b>{t('context.sep')}{tz(can)}</span>
        <span><b>{t('orient.effect')}</b>{t('context.sep')}{tz(effect)}</span>
      </div>
      <button type="button" className="nv-orient__dismiss" aria-label={t('orient.dismissAria')} onClick={() => { try { localStorage.setItem(storageKey, '1'); } catch { /* 存不了就只本次收起 */ } setHidden(true); }}>{t('orient.dismiss')}</button>
      <button type="button" className="nv-orient__dismiss" data-orient-dismiss-all="true" onClick={() => { try { localStorage.setItem(ORIENT_ALL_KEY, '1'); } catch { /* 存不了就只本次收起 */ } setHidden(true); }}>{t('orient.dismissAll')}</button>
    </div>
  );
}

export type ModTab = {id: string; label: string; onClick: () => void; selected?: boolean; disabled?: boolean};
export function NovelModTabs({tabs, badge}: {tabs: ModTab[]; badge?: string}) {
  const t = useT(), tz = useTz();
  return (
    <div className="nv-tabs" role="tablist" aria-label={t('orient.tabs')}>
      {tabs.map(tab => <button key={tab.id} type="button" role="tab" className="nv-tabs__tab" data-view={tab.id} aria-selected={!!tab.selected} disabled={tab.disabled} onClick={tab.onClick}>{tz(tab.label)}</button>)}
      <span className="nv-spacer" />
      {badge ? <span className="nv-badge nv-badge--local">{tz(badge)}</span> : null}
    </div>
  );
}
