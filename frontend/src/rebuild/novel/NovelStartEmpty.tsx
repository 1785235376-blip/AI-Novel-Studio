/* [HERMIA-FE-20261022 REBUILD-W3] 空项目起步 — 原型「你想从哪里开始？」。只做导航，不自动执行任务。 */
export type StartChoice = {id: string; title: string; desc: string; onClick: () => void; disabled?: boolean};

export function NovelStartEmpty({choices, onOpenSample, sampleLabel}: {choices: StartChoice[]; onOpenSample?: () => void; sampleLabel?: string}) {
  return (
    <section className="nv-start" aria-label="你想从哪里开始？" data-rebuild="novel-start">
      <h2>你想从哪里开始？</h2>
      <p>选择只影响打开哪个工作区，不会删除内容，也不会自动执行任何任务。</p>
      <div className="nv-start__grid">
        {choices.map(c => (
          <button key={c.id} type="button" className="nv-start__card" data-start={c.id} disabled={c.disabled} onClick={c.onClick}>
            <b>{c.title}</b>
            <small>{c.desc}</small>
          </button>
        ))}
      </div>
      {onOpenSample ? <button type="button" className="nv-link nv-start__sample" onClick={onOpenSample}>{sampleLabel || '直接打开示例作品'}</button> : null}
    </section>
  );
}
