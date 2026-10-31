/**
 * UX-08 内置项目提示助手 —— 纯函数操作层。
 *
 * 本文件**没有 I/O、没有模型调用、没有定时器**：输入是已经解码好的项目事实，
 * 输出是有序、去重、逐条引用原 owner 字段的提示。三条硬规则：
 *
 * 1. **只从真实项目状态推导**：每条提示的触发条件与引用都指向一个具体 owner 字段。
 * 2. **没有 owner 事实就不说**：来源不可读时 `nextSteps()` 直接返回
 *    `FACTS_UNREADABLE`，绝不退化成一个看起来正常的建议列表。
 * 3. **阻塞必须点名**：`explainBlocker()` 给出具体 owner 事实；
 *    它永远不会返回"请稍后重试"这类通用文案。
 */
import {
  GUIDE_BOUNDS, GUIDE_CODES, GUIDE_FACT_PREFIX, GUIDE_HINTS, GUIDE_HINT_CODES, GUIDE_HINT_SEVERITIES,
  GUIDE_SOURCE_IDS, type GuideBlockerExplanation, type GuideFact, type GuideHint,
  type GuideHintCode, type GuideHintSeverity, type GuideProblem, type GuideProjection, type GuideRefusal,
  type GuideSourceId, type GuideViewName,
} from './projectGuideTypes';

/** 本地拒绝（不是网络错误）：带着码与原因，调用方可以原样呈现。 */
class GuideOperationError extends Error {
  readonly code: string;
  readonly reason: string;
  constructor(code: string, reason: string) {
    super(`${code}:${reason}`);
    this.name = 'GuideOperationError';
    this.code = code;
    this.reason = reason;
  }
}

const refuse = (code: string, message: string, reason: string): GuideRefusal => ({ ok: false, code, message, reason });

/** 事实引用是 `fact:<source>`；`citeSources()` 只接受这个前缀。 */
const fact = (source: string, detail: string): GuideFact => ({ source, detail });
export const guideFactKey = (citation: GuideFact): string => `${GUIDE_FACT_PREFIX}${citation.source}`;

export const sourceReadable = (projection: GuideProjection, source: GuideSourceId): boolean =>
  projection.sources_readable[source] === true;

/** 读一个已声明可读的来源；不可读时抛错，绝不返回 `null` 让提示悄悄消失。 */
function readable<T>(projection: GuideProjection, source: GuideSourceId, value: T | null): T {
  if (!sourceReadable(projection, source) || value === null) {
    throw new GuideOperationError(GUIDE_CODES.factsUnreadable, `${source} 未声明为可读，不能据此产生提示`);
  }
  return value;
}

const hint = (
  code: GuideHintCode, sources: readonly GuideFact[], nextAction: string, override?: { label?: string; message?: string; owner?: string },
): GuideHint => {
  const definition = GUIDE_HINTS[code];
  return Object.freeze({
    code,
    severity: definition.severity,
    label: override?.label ?? definition.label,
    message: override?.message ?? definition.message,
    owner: override?.owner ?? definition.owner,
    sources: Object.freeze(sources.map(citation => Object.freeze({ ...citation }))),
    next_action: nextAction,
    navigate: definition.navigate,
  });
};

const byCode = Object.fromEntries(GUIDE_HINT_CODES.map((code, index) => [code, index])) as Record<GuideHintCode, number>;
const bySeverity = Object.fromEntries(GUIDE_HINT_SEVERITIES.map((severity, index) => [severity, index])) as Record<GuideHintSeverity, number>;

/** 稳定且确定的排序：严重度优先，其次依赖顺序（同一输入永远同一顺序）。 */
export const orderHints = (hints: readonly GuideHint[]): GuideHint[] => [...hints]
  .sort((left, right) => bySeverity[left.severity] - bySeverity[right.severity] || byCode[left.code] - byCode[right.code]);

/** 去重：同一个提示码 + 同一组引用只保留第一条。 */
export const dedupeHints = (hints: readonly GuideHint[]): GuideHint[] => {
  const seen = new Set<string>();
  const kept: GuideHint[] = [];
  for (const entry of hints) {
    const key = `${entry.code}|${citeSources(entry).join(',')}`;
    if (seen.has(key)) continue;
    seen.add(key);
    kept.push(entry);
  }
  return kept;
};

/** 一条提示引用的原 owner 事实（去重、保持首次出现顺序；未引用的提示返回空数组）。 */
export function citeSources(hint: GuideHint): string[] {
  if (!hint || !Array.isArray(hint.sources)) return [];
  const seen = new Set<string>();
  for (const citation of hint.sources) {
    if (!citation || typeof citation.source !== 'string' || !citation.source.trim()) continue;
    const key = guideFactKey(citation);
    if (key.length > GUIDE_BOUNDS.detail + GUIDE_FACT_PREFIX.length) continue;
    seen.add(key);
  }
  return [...seen];
}

/**
 * 拒绝一条 claim 没有引用来源的提示。这里**不修补**提示：没有来源就是没有来源，
 * 返回拒绝让上层什么都不显示，而不是补一个看起来合理的来源。
 */
export function noFabrication(hint: GuideHint | null | undefined): GuideRefusal | null {
  if (!hint || typeof hint !== 'object' || typeof hint.code !== 'string'
    || !(hint.code in GUIDE_HINTS)) {
    return refuse(GUIDE_CODES.uncitedHint, '这条提示没有可核实的提示码，已拒绝显示。',
      'hint.code 不是本模块声明的提示码');
  }
  if (!Array.isArray(hint.sources) || hint.sources.length === 0 || citeSources(hint).length === 0) {
    return refuse(GUIDE_CODES.uncitedHint, '这条提示没有引用任何原 owner 字段，因此被拒绝显示。',
      'hint.sources 为空或没有任何可核实的来源标识');
  }
  if (typeof hint.message !== 'string' || !hint.message.trim()
    || typeof hint.next_action !== 'string' || !hint.next_action.trim()
    || typeof hint.label !== 'string' || !hint.label.trim()) {
    return refuse(GUIDE_CODES.uncitedHint, '这条提示缺少说明或下一步动作，因此被拒绝显示。',
      '提示的 label/message/next_action 不完整');
  }
  return null;
}

/** 只保留通过 `noFabrication()` 的提示；被拒绝的一条会被静默丢弃（并在此返回计数）。 */
export function acceptedHints(hints: readonly GuideHint[]): { accepted: GuideHint[]; refused: number } {
  const accepted: GuideHint[] = [];
  let refused = 0;
  for (const entry of hints) {
    if (noFabrication(entry)) refused += 1; else accepted.push(entry);
  }
  return { accepted, refused };
}

/* --------------------------------------------------------- 不可读来源与拒绝 */

/** 声明过、但一个字段都没读到的来源（既没有投影，也没有形状）。 */
export function unreadableSources(projection: GuideProjection): GuideSourceId[] {
  return GUIDE_SOURCE_IDS.filter(source => !sourceReadable(projection, source));
}

/** 事实完全读不到时的唯一表达：说明"事实不可读"，而不是给建议。 */
export function unreadableFactsRefusal(projection: GuideProjection): GuideRefusal {
  const problems: readonly GuideProblem[] = projection.problems ?? [];
  if (problems.length) {
    const names = [...new Set(problems.map(problem => problem.source))].join('、');
    return refuse(GUIDE_CODES.factsInvalid,
      '传入的项目事实形状不合法，已按失败处理（绝不按"空项目"处理）。',
      `不合法输入：${names}`);
  }
  return refuse(GUIDE_CODES.factsUnreadable,
    '没有读到任何原 owner 的项目事实（项目状态、素材、任务、图谱或时间线），因此不给建议。',
    '全部来源都不可读');
}

/* --------------------------------------------------------------- 提示生成 */

/** 未验证的进度结论：绝不写成"可以交付/可以渲染"。 */
export const VERIFICATION_REFUSAL: GuideRefusal = refuse(GUIDE_CODES.notVerifiedByGuide,
  '提示助手只复述原 owner 的字段，不给出"可以交付"或"可以渲染"这类未验证结论。',
  '交付与渲染结论只能由原 owner 给出');

function partialUnreadable(projection: GuideProjection): GuideHint | null {
  const unreadable = unreadableSources(projection);
  if (!unreadable.length || projection.sources_read_count === 0) return null;
  return hint('FACTS_PARTIALLY_UNREADABLE', [
    fact('sources.unreadable', unreadable.join('、')),
    fact('sources.read', String(projection.sources_read_count)),
  ], `先重新读取这些阅读面：${unreadable.join('、')}；在它们变成可读之前，下面的提示只覆盖已读到的部分。`,
  { message: `有 ${unreadable.length} 个原 owner 阅读面不可读：${unreadable.join('、')}。缺失的部分按"未核实"处理，不会当作"没有问题"。` });
}

function factsUnreadable(projection: GuideProjection): GuideHint | null {
  if (projection.sources_read_count > 0) return null;
  const refusal = unreadableFactsRefusal(projection);
  return hint('FACTS_UNREADABLE', [fact('sources.read', '0'), fact('sources.requested', String(projection.problems.length))],
    '重新读取项目状态、素材、任务、图谱与时间线；在此之前没有可执行的下一步。',
  { message: refusal.message });
}

function intentNotSet(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'CREATIVE_INTENT')) return null;
  const intent = readable(projection, 'CREATIVE_INTENT', projection.facts.intent);
  if (intent.selected_count > 0) return null;
  return hint('INTENT_NOT_SET', [
    fact('creative_intent.version', String(intent.version)),
    fact('creative_intent.values.selected', '0'),
  ], '打开项目入口，按创作意图开始（采用推荐方案只写入创作偏好，不执行任何生成）。');
}

function intentUnreadable(projection: GuideProjection): GuideHint | null {
  if (sourceReadable(projection, 'CREATIVE_INTENT') && projection.facts.intent) return null;
  return hint('INTENT_UNREADABLE', [fact('sources.CREATIVE_INTENT', 'unreadable')],
    '重新读取项目入口或偏好投影；在读到版本与取值之前，不判断"是否已设置意图"。');
}

function reviewItemsUnresolved(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'REVIEW_INBOX_PROJECTION')) return null;
  const inbox = readable(projection, 'REVIEW_INBOX_PROJECTION', projection.facts.review_inbox);
  const unresolved = inbox.unresolved + inbox.unavailable;
  if (unresolved === 0) return null;
  return hint('REVIEW_ITEMS_UNRESOLVED', [
    fact('review_inbox.total', String(inbox.total)),
    fact('review_inbox.unresolved', String(inbox.unresolved)),
    fact('review_inbox.unavailable', String(inbox.unavailable)),
  ], '打开统一任务中心的审核收件箱，逐项核对后把决定转交原领域审核服务；这里不代替批准或驳回。');
}

function assetsLibraryEmpty(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'ASSET_OVERVIEW')) return null;
  const overview = readable(projection, 'ASSET_OVERVIEW', projection.facts.asset_overview);
  const library = projection.facts.asset_library;
  if (library && sourceReadable(projection, 'ASSET_BROWSER_PROJECTION') && library.total > 0) return null;
  if (overview.total > 0) return null;
  return hint('ASSETS_LIBRARY_EMPTY', [
    fact('asset_overview.total', String(overview.total)),
    fact('asset_overview.by_kind.image', String(overview.by_kind_image)),
    fact('asset_overview.by_kind.audio', String(overview.by_kind_audio)),
    fact('asset_overview.by_kind.video', String(overview.by_kind_video)),
  ], '打开素材浏览器导入本地素材，或手动创建内容：两者都不需要模型或网络。');
}

function tasksNoneRead(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'TASK_PROJECTION')) return null;
  const tasks = readable(projection, 'TASK_PROJECTION', projection.facts.tasks);
  if (tasks.total > 0 && tasks.unavailable === 0) return null;
  return hint('TASKS_NONE_READ', [
    fact('tasks.total', String(tasks.total)),
    fact('tasks.unavailable', String(tasks.unavailable)),
    fact('tasks.truncated', String(tasks.truncated)),
  ], '在统一任务中心重新读取当前队列；原 owner 声明没有执行器与自动重试，因此不会自动重跑。');
}

function blockedSourceReference(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'GRAPH_REFERENCE_STATES')) return null;
  const graph = readable(projection, 'GRAPH_REFERENCE_STATES', projection.facts.graph);
  const blocked = graph.reference_states.filter(state => state.state === 'STALE' || state.state === 'UNAVAILABLE');
  if (!blocked.length) return null;
  return hint('BLOCKED_SOURCE_REFERENCE', blocked.slice(0, GUIDE_BOUNDS.citations).map(state =>
    fact(`graph.reference_states.node:${state.node_id}`, state.state)),
  '在无限画布上逐条核对被标为过期或不可读的节点来源；重连与重跑只能由原图谱 owner 执行，这里不会自动处理。',
  { message: `有 ${blocked.length} 个已保存节点引用了过期或不可读的来源（${blocked.map(state => `${state.node_id}=${state.state}`).join('、')}）。解除阻塞必须由原图谱 owner 核对来源版本后完成。` });
}

function unreadyGraphPreflight(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'GRAPH_REFERENCE_STATES')) return null;
  const graph = readable(projection, 'GRAPH_REFERENCE_STATES', projection.facts.graph);
  const reasons: string[] = [];
  if (graph.disabled_nodes > 0) reasons.push(`启用状态为 false 的节点 ${graph.disabled_nodes} 个`);
  if (graph.nodes > 0 && graph.edges === 0) reasons.push('已有节点但没有任何连接');
  if (!reasons.length) return null;
  return hint('UNREADY_GRAPH_PREFLIGHT', [
    fact('graph.nodes', String(graph.nodes)),
    fact('graph.edges', String(graph.edges)),
    fact('graph.disabled_nodes', String(graph.disabled_nodes)),
  ], '在无限画布上补全被禁用的节点与缺失的连接，然后由原图谱预检重新判断；这里不接受改动、也不派发执行。',
  { message: `已保存图存在未就绪的本地结构：${reasons.join('；')}。原预检因此不会通过。` });
}

function requirementUnmet(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'PRODUCTION_MODULES')) return null;
  const modules = readable(projection, 'PRODUCTION_MODULES', projection.facts.modules);
  const blocked = modules.filter(module => module.blocked_reasons.length > 0);
  const candidates = ['图像', '视频', '音频', '时间线', '资产'];
  const dependent = blocked.filter(module => candidates.includes(module.owner));
  if (!dependent.length) return null;
  const libraryReadable = sourceReadable(projection, 'ASSET_BROWSER_PROJECTION')
    && projection.facts.asset_library !== null;
  if (libraryReadable) return null;
  return hint('REQUIREMENT_UNMET_ASSET_DEPENDENCY', [
    fact('sources.ASSET_BROWSER_PROJECTION', 'unreadable'),
    fact('production_modules.dependents', dependent.map(module => `${module.id}=${module.owner}`).join('、')),
    fact('production_modules.blocked_reasons', dependent.map(module => module.blocked_reasons[0]).join('、')),
  ], '先重新读取素材库；在它可读之前，这些模块的前置条件只能是"未核实"，不能当作已满足。',
  { message: `${dependent.map(module => module.owner).join('、')} 依赖素材库，而素材库阅读面当前不可读：它们的前置条件未核实，不能算满足（原模块自己声明的阻塞原因：${dependent.map(module => module.blocked_reasons[0]).join('、')}）。` });
}

function timelineUnrendered(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'TIMELINE_TRACKS')) return null;
  const timeline = readable(projection, 'TIMELINE_TRACKS', projection.facts.timeline);
  if (timeline.clip_count > 0 && timeline.track_count > 0) return null;
  return hint('TIMELINE_UNRENDERED', [
    fact('timeline.track_count', String(timeline.track_count)),
    fact('timeline.clip_count', String(timeline.clip_count)),
  ], '在制作模块里先把片段放进轨道；渲染与导出仍由原时间线服务决定，产物是私有候选，需要人工审核。');
}

function storyboardNotApproved(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'STORYBOARD_RECEIPT')) return null;
  const storyboard = readable(projection, 'STORYBOARD_RECEIPT', projection.facts.storyboard);
  if (storyboard.approved !== false) return null;
  return hint('STORYBOARD_NOT_APPROVED', [
    fact('storyboard.approved', 'false'),
    fact('storyboard.shots', String(storyboard.shot_count)),
  ], '打开分镜工作区核对当前文档版本；批准只能由原分镜 owner 执行，这里不代替批准。');
}

function noFactsRead(projection: GuideProjection): GuideHint | null {
  if (projection.sources_read_count > 0) return null;
  return hint('NO_FACTS_READ', [fact('sources.read', '0'), fact('sources.declared', String(projection.problems.length))],
    '重新读取项目状态、素材、任务、图谱与时间线；在此之前没有可执行的下一步。');
}

/**
 * 兜底复述：只有**确实还有未审核模块**时才说"没有可核实的下一步"。
 * 全部模块都已是 `REVIEWED` 时它不产生提示 —— 那时正确的状态是"没有需要处理的
 * 条目"（`EMPTY`），而不是一句未验证的"看起来没问题"。
 */
function noNextStepVerified(projection: GuideProjection): GuideHint | null {
  if (!sourceReadable(projection, 'PRODUCTION_MODULES')) return null;
  const modules = readable(projection, 'PRODUCTION_MODULES', projection.facts.modules);
  const pending = modules.filter(module => module.status !== 'REVIEWED');
  if (!pending.length) return null;
  return hint('NO_NEXT_STEP_VERIFIED', [
    fact('production_modules.total', String(modules.length)),
    fact('production_modules.not_reviewed', String(pending.length)),
  ], '在原模块里继续下一步；这一步只是复述模块状态，不是验收结论，也不代表可以交付。');
}

const GENERATORS: Readonly<Record<GuideHintCode, (projection: GuideProjection) => GuideHint | null>> = Object.freeze({
  FACTS_UNREADABLE: factsUnreadable,
  FACTS_PARTIALLY_UNREADABLE: partialUnreadable,
  NO_FACTS_READ: noFactsRead,
  BLOCKED_SOURCE_REFERENCE: blockedSourceReference,
  UNREADY_GRAPH_PREFLIGHT: unreadyGraphPreflight,
  REQUIREMENT_UNMET_ASSET_DEPENDENCY: requirementUnmet,
  INTENT_NOT_SET: intentNotSet,
  INTENT_UNREADABLE: intentUnreadable,
  REVIEW_ITEMS_UNRESOLVED: reviewItemsUnresolved,
  TASKS_NONE_READ: tasksNoneRead,
  ASSETS_LIBRARY_EMPTY: assetsLibraryEmpty,
  TIMELINE_UNRENDERED: timelineUnrendered,
  STORYBOARD_NOT_APPROVED: storyboardNotApproved,
  NO_NEXT_STEP_VERIFIED: noNextStepVerified,
});

/**
 * 有序、去重的下一步建议。
 *
 * 只根据 `GuideFacts`/可读性推导；**没有任何可读事实时**返回唯一一条
 * `FACTS_UNREADABLE`（说明事实不可读），而不是一份看起来正常的建议列表。
 */
export function nextSteps(projection: GuideProjection): GuideHint[] {
  if (!projection || typeof projection !== 'object' || !projection.facts || !projection.sources_readable) {
    throw new GuideOperationError(GUIDE_CODES.factsInvalid, 'nextSteps 需要一个解码后的 GuideProjection');
  }
  if (projection.sources_read_count === 0) return [GENERATORS.FACTS_UNREADABLE(projection) as GuideHint];
  const generated: GuideHint[] = [];
  for (const code of GUIDE_HINT_CODES) {
    let produced: GuideHint | null;
    try {
      produced = GENERATORS[code](projection);
    } catch (reason) {
      // 生成器只在"它需要的来源不可读"时抛错；那种情况下正确地不产生提示，
      // 但绝不因此返回一份不完整的建议列表。
      if (reason instanceof GuideOperationError) continue;
      throw reason;
    }
    if (produced) generated.push(produced);
  }
  const { accepted } = acceptedHints(generated);
  return orderHints(dedupeHints(accepted));
}

/** `nextSteps` 的常用入口：事实不可读（或形状不合法）时直接给出拒绝。 */
export function nextStepsOrRefusal(projection: GuideProjection): GuideHint[] | GuideRefusal {
  if (!projection || typeof projection !== 'object' || !projection.facts) {
    return refuse(GUIDE_CODES.factsInvalid, '项目事实形状不合法，已按失败处理。', 'projection 缺失或不是对象');
  }
  if (projection.sources_read_count === 0) return unreadableFactsRefusal(projection);
  return nextSteps(projection);
}

/* --------------------------------------------------------------- 阻塞解释 */

/**
 * 点名阻塞进度的**具体 owner 事实**。
 *
 * 未知提示码、或该提示当前并不成立时返回 `null`：宁可什么都不说，
 * 也不给"请稍后重试"这类通用文案。
 */
export function explainBlocker(fact: GuideHint | null | undefined, projection?: GuideProjection): GuideBlockerExplanation | null {
  if (!fact || typeof fact !== 'object' || typeof fact.code !== 'string' || !(fact.code in GUIDE_HINTS)) return null;
  const hint = fact as GuideHint;

  // 事实不可读时，阻塞就是"读不到"本身：这一点必须点名，而不是让用户重试。
  if (hint.code === 'FACTS_UNREADABLE') {
    const refusal = projection ? unreadableFactsRefusal(projection) : refuse(GUIDE_CODES.factsUnreadable,
      '项目事实不可读时不给建议：阻塞点是"读不到原 owner 字段"。', '没有任何可读来源');
    return Object.freeze({
      code: hint.code, severity: hint.severity, claim: refusal.message,
      next_action: hint.next_action, navigate: hint.navigate, sources: hint.sources ?? [], refusal,
    });
  }

  const cited = hint.sources ?? [];
  const unverified = cited.filter(citation => /unreadable|^sources\./.test(citation.source));
  const refusal = cited.length === 0
    ? refuse(GUIDE_CODES.blockerOwnerOnly, '这条阻塞没有引用任何 owner 事实，因此不能作为阻塞解释。', 'sources 为空')
    : unverified.length
      ? refuse(GUIDE_CODES.blockerUnverified,
        '这条阻塞的依据是未读到的 owner 阅读面；在它可读之前不判断具体原因。',
        `未读到的来源：${unverified.map(citation => citation.source).join('、')}`)
      : null;

  return Object.freeze({
    code: hint.code,
    severity: hint.severity,
    claim: hint.message,
    next_action: hint.next_action,
    navigate: hint.navigate,
    sources: Object.freeze(cited.map(citation => Object.freeze({ ...citation }))),
    refusal,
  });
}

/* ------------------------------------------------------------- 兜底与工具 */

/** 一条项目事实都读不到时的固定回答：事实不可读 ≠ 没有问题。 */
export function staticFallback(): GuideRefusal {
  return refuse(GUIDE_CODES.noFactsAvailable,
    '这个项目没有可读的原 owner 事实，因此提示助手不提供任何建议。',
    '没有项目状态、素材、任务、图谱或时间线投影可读；事实不可读，不是"项目没有问题"');
}

/** 呈现辅助：把一条提示渲染成 `标签 · 来源` 的可核实文本（不改变内容）。 */
export function describeHint(hint: GuideHint): string {
  const sources = citeSources(hint);
  return `${hint.label} · 来源 ${sources.length ? sources.join('、') : '（无）'}`;
}

export const guideViewOf = (hint: GuideHint): GuideViewName | null => hint.navigate;
