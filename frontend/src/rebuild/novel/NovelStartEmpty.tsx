/* [HERMIA-FE-20261022 R1] 空项目 — 按原型写作台空态：不另起大标题页，正文区显示「请先在左侧选择或新建章节」，
   附「＋ 新建章节」与少量去向链接（只导航，不自动执行任务）。 */
import {useT, useTz} from '../../i18n'; // [HERMIA-FE-20261025 I18N P2]
export type StartChoice = {id: string; title: string; desc?: string; onClick: () => void; disabled?: boolean};

export function NovelStartEmpty({choices, onCreate, creating}: {choices: StartChoice[]; onCreate?: () => void; creating?: boolean}) {
  const t = useT(), tz = useTz();
  return (
    <section className="nv-empty" aria-label={t('empty.region')} data-rebuild="novel-start">
      <div className="nv-empty__prose">
        <p className="nv-empty__ph">{t('empty.ph')}</p>
        <p className="nv-hint">{t('empty.hint')}</p>
        {onCreate ? <button type="button" className="nv-btn nv-btn--primary" data-start="write" disabled={creating} onClick={onCreate}>{t('rail.new')}</button> : null}
        <div className="nv-empty__links">
          {choices.map(c => <button key={c.id} type="button" className="nv-link" data-start={c.id} disabled={c.disabled} title={c.desc ? tz(c.desc) : undefined} onClick={c.onClick}>{tz(c.title)}</button>)}
        </div>
      </div>
    </section>
  );
}
