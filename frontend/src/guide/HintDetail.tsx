import { Badge, Button } from '../ui/primitives';
import { GUIDE_HINTS, GUIDE_HINT_OWNER_LABELS, type GuideHint } from './projectGuideTypes';
import { citeSources, explainBlocker, noFabrication } from './projectGuideOps';
import type { GuideViewName } from './projectGuideTypes';

/** 详情展示哪一条由调用方决定（默认第一条）；这里不自己保存选择状态。 */
export function HintDetail({ hints, onNavigate }: {
  hints: readonly GuideHint[];
  onNavigate?: (target: GuideViewName) => boolean;
}) {
  const hint = hints[0];
  if (!hint) return <section className="project-guide-detail" aria-label="提示详情"><p>当前没有可展示的提示。</p></section>;
  const refusal = noFabrication(hint);
  // 没有引用来源的提示被拒绝显示：这里只呈现拒绝原因，绝不补一个来源。
  if (refusal) {
    return <section className="project-guide-detail" aria-label="提示详情" data-guide-refused={refusal.code}>
      <h3>提示被拒绝显示</h3>
      <p>{refusal.message}</p>
      <p className="project-guide-detail__reason">原因：{refusal.reason}</p>
    </section>;
  }
  const blocker = explainBlocker(hint);
  const sources = citeSources(hint);
  const definition = GUIDE_HINTS[hint.code];
  const target = hint.navigate;
  return <section className="project-guide-detail" aria-label="提示详情" data-guide-code={hint.code}>
    <header>
      <h3>{hint.label || definition.label}</h3>
      <Badge tone="neutral">{GUIDE_HINT_OWNER_LABELS[hint.owner] ?? hint.owner}</Badge>
      <Badge tone="info">{hint.code}</Badge>
    </header>
    <p className="project-guide-detail__claim">{hint.message}</p>
    <section>
      <h4>引用的原 owner 字段（{sources.length}）</h4>
      <ul className="project-guide-detail__sources">
        {sources.map(source => <li key={source}><code>{source}</code></li>)}
      </ul>
      <ul className="project-guide-detail__facts">
        {hint.sources.map(citation => <li key={`${citation.source}=${citation.detail}`}>
          <code>{citation.source}</code> = <code>{citation.detail}</code>
        </li>)}
      </ul>
    </section>
    <section>
      <h4>精确的下一步</h4>
      <p>{hint.next_action}</p>
      {blocker?.refusal && <p className="project-guide-detail__reason">未核实：{blocker.refusal.reason}</p>}
      {target && onNavigate && <Button variant="secondary" onClick={() => onNavigate(target)}>
        {`前往既有视图：${target}`}
      </Button>}
      {!target && <p className="project-guide-detail__reason">这条提示没有导航目标：它只描述状态，不跳转到别处。</p>}
    </section>
  </section>;
}
