import { Badge } from '../ui/primitives';
import {
  GUIDE_HINTS, GUIDE_HINT_OWNER_LABELS, type GuideHint,
} from './projectGuideTypes';
import { citeSources } from './projectGuideOps';

/** 单条提示：标签 + 严重度 + 精确到字段的 owner 来源。 */
export function HintRow({ hint }: { hint: GuideHint }) {
  const definition = GUIDE_HINTS[hint.code];
  const sources = citeSources(hint);
  return <li className="project-guide-hint" data-guide-code={hint.code} data-guide-sources={sources.join('|')}>
    <header>
      <Badge tone={hint.severity === 'CRITICAL' || hint.severity === 'BLOCKING' ? 'error'
        : hint.severity === 'ATTENTION' ? 'warning' : 'info'}>{hint.severity}</Badge>
      <strong>{hint.label || definition.label}</strong>
      <span className="project-guide-hint__owner">{GUIDE_HINT_OWNER_LABELS[hint.owner] ?? hint.owner}</span>
    </header>
    <p>{hint.message}</p>
    {/* 每一条提示都必须显示它引用的原 owner 字段；没有来源的提示根本不会被渲染。 */}
    <p className="project-guide-hint__sources">
      {sources.length
        ? <>来源：{sources.map(source => <code key={source}>{source}</code>)}</>
        : <>来源：（无）—— 这条提示不应被显示。</>}
    </p>
    <p className="project-guide-hint__action">下一步：{hint.next_action}</p>
  </li>;
}

/** 有序、去重的提示列表。每一条都带自己的来源，便于逐条核对。 */
export function HintList({ hints }: { hints: readonly GuideHint[] }) {
  return <section className="project-guide__list" aria-label="项目提示列表">
    <h3>下一步建议（{hints.length}）</h3>
    <ol>
      {hints.map(hint => <HintRow key={`${hint.code}:${citeSources(hint).join(',')}`} hint={hint}/>)}
    </ol>
    <p className="project-guide__hint-scope">顺序按严重度与依赖顺序固定；同一输入永远给同一顺序，不会每次刷新都变。</p>
  </section>;
}
