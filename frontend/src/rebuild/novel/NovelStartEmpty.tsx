/* [HERMIA-FE-20261022 R1] 空项目 — 按原型写作台空态：不另起大标题页，正文区显示「请先在左侧选择或新建章节」，
   附「＋ 新建章节」与少量去向链接（只导航，不自动执行任务）。 */
export type StartChoice = {id: string; title: string; desc?: string; onClick: () => void; disabled?: boolean};

export function NovelStartEmpty({choices, onCreate, creating}: {choices: StartChoice[]; onCreate?: () => void; creating?: boolean}) {
  return (
    <section className="nv-empty" aria-label="还没有章节" data-rebuild="novel-start">
      <div className="nv-empty__prose">
        <p className="nv-empty__ph">请先在左侧选择或新建章节</p>
        <p className="nv-hint">这部作品还没有章节。新建后就可以在这里写正文，内容自动保存。</p>
        {onCreate ? <button type="button" className="nv-btn nv-btn--primary" data-start="write" disabled={creating} onClick={onCreate}>＋ 新建章节</button> : null}
        <div className="nv-empty__links">
          {choices.map(c => <button key={c.id} type="button" className="nv-link" data-start={c.id} disabled={c.disabled} title={c.desc} onClick={c.onClick}>{c.title}</button>)}
        </div>
      </div>
    </section>
  );
}
