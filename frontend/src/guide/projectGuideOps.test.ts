import { describe, expect, it } from 'vitest';
import { decodeGuideInput, type GuideInput } from './projectGuideFacts';
import {
  acceptedHints, citeSources, dedupeHints, describeHint, explainBlocker, guideFactKey, noFabrication,
  nextSteps, nextStepsOrRefusal, orderHints, sourceReadable, staticFallback, unreadableFactsRefusal,
  unreadableSources,
} from './projectGuideOps';
import {
  GUIDE_CODES, GUIDE_HINTS, GUIDE_HINT_CODES, GUIDE_HINT_SEVERITIES, GUIDE_SOURCE_IDS, GUIDE_NOTICES,
  guideSourceDescription,
  type GuideFact, type GuideFacts, type GuideHint, type GuideProjection, type GuideSourceId,
} from './projectGuideTypes';
import { QINGJIAN_EXTENSION } from './qingjianExtension';
import {
  IDENTITY, PROJECT, assetRows, graphFacts, inboxProjection, projection, storyboardReceipt,
  tasksProjection, timelineFacts,
} from './projectGuideFixtures';

/** 只读夹具入口：项目身份固定，其余由用例声明。 */
const guideInput = (override: Partial<GuideInput> = {}): GuideProjection =>
  decodeGuideInput({ projectId: PROJECT, identity: IDENTITY, documentId: IDENTITY, ...override });

/**
 * 一个**完全可读**的空项目：七个模块都在、意图未选、素材为空、任务/收件箱为空、
 * 图与时间线都读到了。只有真实的 DECLARED 来源才参与推导。
 */
const emptyProject = (): GuideProjection => guideInput({
  workflow: projection(), tasks: tasksProjection(), inbox: inboxProjection(),
  assets: assetRows([]), graph: graphFacts(), timeline: timelineFacts(0, 0),
});

/** 全部十个来源都可读（含分镜回执），用于"这条提示确实不该出现"的用例。 */
const fullProject = (override: Partial<GuideInput> = {}): GuideProjection => guideInput({
  workflow: projection({ selected: ['novel_writing'] }), tasks: tasksProjection(),
  inbox: inboxProjection(), assets: assetRows([{ id: 'asset-1', media_kind: 'image' }]),
  graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'CURRENT' }]),
  timeline: timelineFacts(1, 1), storyboard: storyboardReceipt(1, true),
  ...override,
});

const codesOf = (hints: readonly GuideHint[]): string[] => hints.map(entry => entry.code);
const hintOf = (hints: readonly GuideHint[], code: string): GuideHint => {
  const found = hints.find(entry => entry.code === code);
  if (!found) throw new Error(`missing hint ${code} in ${codesOf(hints).join(',') || '(none)'}`);
  return found;
};

describe('GUIDE_CODES / GUIDE_HINTS：每一码都必须可解析、有主、有文案', () => {
  it('声明了稳定机器码与中文文案', () => {
    expect(GUIDE_HINT_CODES.length).toBeGreaterThanOrEqual(14);
    for (const code of GUIDE_HINT_CODES) {
      const definition = GUIDE_HINTS[code];
      expect(definition.label.length).toBeGreaterThan(0);
      expect(definition.message.length).toBeGreaterThan(0);
      expect(GUIDE_HINT_SEVERITIES).toContain(definition.severity);
      expect(definition.owner.length).toBeGreaterThan(0);
    }
    expect(GUIDE_SOURCE_IDS.length).toBe(10);
    // 提示助手绝不承诺当前不具备的能力（Windows 安装 / GPU / 重型渲染）。
    expect(GUIDE_NOTICES.capabilityBoundary).toContain('不包含 Windows 安装、GPU 或重型渲染');
  });

  it('每个稳定机器码都是大写、可追踪的', () => {
    for (const value of Object.values(GUIDE_CODES)) expect(value).toMatch(/^PROJECT_GUIDE_[A-Z_]+$/);
  });

  it('guideSourceDescription 覆盖全部来源', () => {
    for (const source of GUIDE_SOURCE_IDS) {
      expect(guideSourceDescription(source as GuideSourceId).length).toBeGreaterThan(0);
    }
  });
});

describe('nextSteps：只从真实项目状态推导', () => {
  it('空项目给出一组具体、可核实的提示（不是一句通用建议）', () => {
    const hints = nextSteps(emptyProject());
    expect(codesOf(hints)).toContain('INTENT_NOT_SET');
    expect(codesOf(hints)).toContain('ASSETS_LIBRARY_EMPTY');
    expect(codesOf(hints)).toContain('TIMELINE_UNRENDERED');
    expect(codesOf(hints)).toContain('TASKS_NONE_READ');
    expect(codesOf(hints)).toContain('NO_NEXT_STEP_VERIFIED');
    // 被引用的 owner 事实必须是真的（意图版本来自 owner 的 creative_intent.version）。
    const intent = hintOf(hints, 'INTENT_NOT_SET');
    expect(intent.sources.map(entry => entry.source)).toEqual(['creative_intent.version', 'creative_intent.values.selected']);
    expect(intent.sources[0].detail).toBe('1');
    expect(intent.sources[1].detail).toBe('0');
    expect(intent.navigate).toBe('START');
  });

  it('顺序固定：严重度优先，其次依赖顺序（同一输入永远同一顺序）', () => {
    const hints = nextSteps(emptyProject());
    const again = nextSteps(emptyProject());
    expect(hints.map(entry => entry.code)).toEqual(again.map(entry => entry.code));
    expect(codesOf(hints)).toEqual([
      'FACTS_PARTIALLY_UNREADABLE', 'TIMELINE_UNRENDERED', 'INTENT_NOT_SET', 'TASKS_NONE_READ',
      'ASSETS_LIBRARY_EMPTY', 'NO_NEXT_STEP_VERIFIED',
    ]);
    const ranks = hints.map(entry => GUIDE_HINT_SEVERITIES.indexOf(entry.severity));
    expect([...ranks].sort((left, right) => left - right)).toEqual(ranks);
    expect(hints[hints.length - 1].severity).toBe('INFO');
  });

  it('去重：同一码 + 同一来源只保留一次', () => {
    const base = nextSteps(emptyProject());
    const duplicated = dedupeHints([...base, ...base]);
    expect(duplicated.map(entry => entry.code)).toEqual(base.map(entry => entry.code));
    expect(new Set(duplicated.map(entry => entry.code)).size).toBe(duplicated.length);
  });

  it('orderHints 不改变集合，只改变次序', () => {
    const base = nextSteps(emptyProject());
    const reversed = [...base].reverse();
    expect(orderHints(reversed).map(entry => entry.code)).toEqual(base.map(entry => entry.code));
  });

  it('创作意图已选时不再提示缺意图', () => {
    const selected = fullProject();
    expect(codesOf(nextSteps(selected))).not.toContain('INTENT_NOT_SET');
    expect(sourceReadable(selected, 'CREATIVE_INTENT')).toBe(true);
    expect(selected.facts.intent?.selected_count).toBe(1);
  });

  it('未处理的审核候选与不可读领域都算"未处理"', () => {
    const inbox = guideInput({
      workflow: projection({ selected: ['novel_writing'] }),
      inbox: inboxProjection([{ id: 'item-1', status: 'PENDING' }, { id: 'item-2', status: 'APPROVED' }],
        [{ domain: 'visual_identity', reason: 'ORIGINAL_DOMAIN_ACCESS_REQUIRED' }]),
    });
    const hint = hintOf(nextSteps(inbox), 'REVIEW_ITEMS_UNRESOLVED');
    expect(hint.sources.map(entry => entry.source)).toContain('review_inbox.unavailable');
    expect(hint.sources.find(entry => entry.source === 'review_inbox.unavailable')?.detail).toBe('1');
    expect(hint.sources.find(entry => entry.source === 'review_inbox.total')?.detail).toBe('3');
    expect(hint.navigate).toBe('TASKS');
    expect(hint.next_action).toContain('原领域审核服务');
  });

  it('收件箱为空时不再提示审核', () => {
    expect(codesOf(nextSteps(fullProject()))).not.toContain('REVIEW_ITEMS_UNRESOLVED');
  });

  it('素材库非空时不再提示空素材', () => {
    expect(codesOf(nextSteps(fullProject()))).not.toContain('ASSETS_LIBRARY_EMPTY');
  });

  it('时间线有片段时不再提示未成片', () => {
    expect(codesOf(nextSteps(fullProject()))).not.toContain('TIMELINE_UNRENDERED');
  });

  it('素材库阅读面不可读时，前置条件算"未核实"而不是"已满足"', () => {
    const unmet = guideInput({
      workflow: projection({ selected: ['novel_writing'], override: { image: { blocked_reasons: ['缺少来源素材'] } } }),
      // 故意**不**传 assets：素材库阅读面不可读。
    });
    const hint = hintOf(nextSteps(unmet), 'REQUIREMENT_UNMET_ASSET_DEPENDENCY');
    expect(hint.sources.map(entry => entry.source)).toContain('sources.ASSET_BROWSER_PROJECTION');
    expect(hint.sources.map(entry => entry.source)).toContain('production_modules.blocked_reasons');
    expect(hint.sources.find(entry => entry.source === 'production_modules.blocked_reasons')?.detail).toBe('缺少来源素材');
    expect(hint.message).toContain('未核实');
    expect(hint.message).toContain('图像');
    expect(hint.navigate).toBe('ASSETS');
  });

  it('素材库可读时，需求前置条件不再报警', () => {
    const satisfied = fullProject({
      workflow: projection({ selected: ['novel_writing'], override: { image: { blocked_reasons: ['缺少来源素材'] } } }),
    });
    expect(codesOf(nextSteps(satisfied))).not.toContain('REQUIREMENT_UNMET_ASSET_DEPENDENCY');
  });
});

describe('nextSteps：图谱与时间线的阻塞必须点名', () => {
  it('过期 / 不可读的来源绑定逐条列出节点与状态', () => {
    const blocked = fullProject({
      graph: graphFacts([{ id: 'node-1' }, { id: 'node-2' }], [{ id: 'edge-1' }],
        [{ node_id: 'node-1', state: 'STALE' }, { node_id: 'node-2', state: 'UNAVAILABLE' }, { node_id: 'node-1', state: 'CURRENT' }]),
    });
    const hint = hintOf(nextSteps(blocked), 'BLOCKED_SOURCE_REFERENCE');
    expect(hint.severity).toBe('BLOCKING');
    expect(hint.navigate).toBe('GRAPH');
    expect(hint.sources.map(entry => entry.source)).toEqual([
      'graph.reference_states.node:node-1', 'graph.reference_states.node:node-2',
    ]);
    expect(hint.sources.map(entry => entry.detail)).toEqual(['STALE', 'UNAVAILABLE']);
    expect(hint.message).toContain('node-1=STALE');
    expect(hint.next_action).toContain('原图谱 owner');
  });

  it('被禁用的节点与空连接都会阻止预检通过', () => {
    const unready = fullProject({ graph: graphFacts([{ id: 'node-1', enabled: false }, { id: 'node-2' }], []) });
    const hint = hintOf(nextSteps(unready), 'UNREADY_GRAPH_PREFLIGHT');
    expect(hint.severity).toBe('ATTENTION');
    expect(hint.sources.map(entry => entry.source)).toEqual(['graph.nodes', 'graph.edges', 'graph.disabled_nodes']);
    expect(hint.message).toContain('启用状态为 false 的节点 1 个');
    expect(hint.message).toContain('没有任何连接');
  });

  it('图与时间线都健康时不再产生这两条提示', () => {
    const codes = codesOf(nextSteps(fullProject()));
    expect(codes).not.toContain('BLOCKED_SOURCE_REFERENCE');
    expect(codes).not.toContain('UNREADY_GRAPH_PREFLIGHT');
    expect(codes).not.toContain('TIMELINE_UNRENDERED');
  });
});

describe('explainBlocker：点名具体 owner 事实，绝不给通用文案', () => {
  it('每条阻塞都引用一个真实字段，且没有"请稍后重试"', () => {
    const blocked = guideInput({
      workflow: projection({ selected: ['novel_writing'], override: { image: { blocked_reasons: ['缺少来源素材'] } } }),
      graph: graphFacts([{ id: 'node-1' }], [{ id: 'edge-1' }], [{ node_id: 'node-1', state: 'UNAVAILABLE' }]),
      timeline: timelineFacts(0, 0),
    });
    const hints = nextSteps(blocked);
    expect(hints.length).toBeGreaterThan(3);
    for (const hint of hints) {
      const explanation = explainBlocker(hint, blocked);
      expect(explanation).not.toBeNull();
      expect(explanation?.code).toBe(hint.code);
      expect(explanation?.sources.length).toBeGreaterThan(0);
      expect(explanation?.next_action).not.toContain('请稍后重试');
      expect(explanation?.claim).not.toContain('请稍后重试');
      for (const citation of explanation?.sources ?? []) {
        expect(citation.source).toMatch(/^[a-z_][A-Za-z0-9_.:-]*$/);
        expect(citation.detail.length).toBeGreaterThan(0);
      }
    }
  });

  it('未读到的来源会被标为未核实，而不是给出确定原因', () => {
    const unmet = guideInput({
      workflow: projection({ selected: ['novel_writing'], override: { image: { blocked_reasons: ['缺少来源素材'] } } }),
    });
    const explanation = explainBlocker(hintOf(nextSteps(unmet), 'REQUIREMENT_UNMET_ASSET_DEPENDENCY'), unmet);
    expect(explanation?.refusal?.code).toBe(GUIDE_CODES.blockerUnverified);
    expect(explanation?.refusal?.reason).toContain('sources.ASSET_BROWSER_PROJECTION');
  });

  it('事实不可读时，阻塞点就是"读不到"本身', () => {
    const nothingRead = guideInput();
    const hint = hintOf(nextSteps(nothingRead), 'FACTS_UNREADABLE');
    const explanation = explainBlocker(hint, nothingRead);
    expect(explanation?.refusal?.code).toBe(GUIDE_CODES.factsUnreadable);
    expect(explanation?.next_action).toContain('重新读取');
  });

  it('未知提示码或空提示一律拒绝解释', () => {
    expect(explainBlocker(null)).toBeNull();
    expect(explainBlocker(undefined)).toBeNull();
    expect(explainBlocker({ code: 'NOT_A_REAL_CODE' } as unknown as GuideHint)).toBeNull();
  });
});

describe('citeSources / noFabrication：没有来源的 claim 被拒绝', () => {
  it('干净提示的引用就是它的 sources（去重、带前缀）', () => {
    const hint = hintOf(nextSteps(emptyProject()), 'ASSETS_LIBRARY_EMPTY');
    const sources = citeSources(hint);
    expect(sources).toEqual(hint.sources.map(guideFactKey));
    expect(sources.every(source => source.startsWith('fact:'))).toBe(true);
    expect(new Set(sources).size).toBe(sources.length);
    expect(noFabrication(hint)).toBeNull();
  });

  it('没有来源的提示被拒绝，且拒绝原因点名"没有来源"', () => {
    const fabricated = { ...hintOf(nextSteps(emptyProject()), 'TIMELINE_UNRENDERED'), sources: [] } as GuideHint;
    const refusal = noFabrication(fabricated);
    expect(refusal?.code).toBe(GUIDE_CODES.uncitedHint);
    expect(refusal?.reason).toContain('hint.sources 为空');
    expect(citeSources(fabricated)).toEqual([]);
  });

  it('来源标识是空白串时同样被拒绝（不把空串当成来源）', () => {
    const fabricated = {
      ...hintOf(nextSteps(emptyProject()), 'TASKS_NONE_READ'),
      sources: [{ source: '   ', detail: '1' }] as GuideFact[],
    } as GuideHint;
    expect(noFabrication(fabricated)?.code).toBe(GUIDE_CODES.uncitedHint);
    expect(citeSources(fabricated)).toEqual([]);
  });

  it('缺说明或缺下一步的提示也被拒绝', () => {
    const base = hintOf(nextSteps(emptyProject()), 'INTENT_NOT_SET');
    expect(noFabrication({ ...base, message: '' } as GuideHint)?.code).toBe(GUIDE_CODES.uncitedHint);
    expect(noFabrication({ ...base, next_action: '  ' } as GuideHint)?.code).toBe(GUIDE_CODES.uncitedHint);
    expect(noFabrication({ ...base, code: 'MADE_UP' } as unknown as GuideHint)?.code).toBe(GUIDE_CODES.uncitedHint);
  });

  it('acceptedHints 只统计通过校验的提示', () => {
    const hints = nextSteps(emptyProject());
    const { accepted, refused } = acceptedHints([...hints, { ...hints[0], sources: [] } as GuideHint]);
    expect(accepted.length).toBe(hints.length);
    expect(refused).toBe(1);
  });

  it('describeHint 同时给出标签与来源，缺来源时明说"（无）"', () => {
    const hint = hintOf(nextSteps(emptyProject()), 'INTENT_NOT_SET');
    expect(describeHint(hint)).toContain('来源 fact:creative_intent.version');
    expect(describeHint({ ...hint, sources: [] } as GuideHint)).toContain('（无）');
  });
});

describe('staticFallback / 事实不可读：说"不可读"，不说"没问题"', () => {
  it('没有任何事实时返回固定的"事实不可读"拒绝', () => {
    const fallback = staticFallback();
    expect(fallback.ok).toBe(false);
    expect(fallback.code).toBe(GUIDE_CODES.noFactsAvailable);
    expect(fallback.message).toContain('没有可读的原 owner 事实');
    expect(fallback.reason).toContain('事实不可读');
    expect(fallback.message).not.toContain('没有问题');
  });

  it('一个来源都没有时 nextSteps 只有 FACTS_UNREADABLE', () => {
    const nothingRead = guideInput();
    expect(nothingRead.sources_read_count).toBe(0);
    expect(codesOf(nextSteps(nothingRead))).toEqual(['FACTS_UNREADABLE']);
    expect(unreadableSources(nothingRead)).toEqual([...GUIDE_SOURCE_IDS]);
  });

  it('nextStepsOrRefusal 在事实不可读时给拒绝，在可读时给提示', () => {
    const refusal = nextStepsOrRefusal(guideInput());
    expect(Array.isArray(refusal)).toBe(false);
    expect((refusal as { code: string }).code).toBe(GUIDE_CODES.factsUnreadable);
    expect(Array.isArray(nextStepsOrRefusal(emptyProject()))).toBe(true);
  });

  it('形状不合法直接判 FAILED 级别的拒绝，而不是"空项目"', () => {
    const broken = guideInput({ workflow: { contract: 'nope' } });
    expect(broken.sources_read_count).toBe(0);
    expect(broken.problems.length).toBeGreaterThan(0);
    expect(broken.problems[0].code).toBe(GUIDE_CODES.factsInvalid);
    expect(broken.problems[0].source).toBe('PRODUCTION_WORKFLOW_PROJECTION');
    expect(sourceReadable(broken, 'PRODUCTION_WORKFLOW_PROJECTION')).toBe(false);
    expect(unreadableFactsRefusal(broken).code).toBe(GUIDE_CODES.factsInvalid);
  });

  it('部分不可读时必须显式说明缺了哪些阅读面', () => {
    const partial = fullProject({ tasks: undefined, assets: undefined });
    const hint = hintOf(nextSteps(partial), 'FACTS_PARTIALLY_UNREADABLE');
    expect(hint.severity).toBe('ATTENTION');
    expect(hint.sources[0].source).toBe('sources.unreadable');
    expect(hint.sources[0].detail).toContain('TASK_PROJECTION');
    expect(hint.sources[0].detail).toContain('ASSET_BROWSER_PROJECTION');
    expect(hint.message).toContain('未核实');
  });

  it('每条提示的 owner 都是已知来源，且 navigate 只在既有视图里', () => {
    const hints = nextSteps(emptyProject());
    const views = ['START', 'ASSETS', 'GRAPH', 'PRODUCTION', 'TASKS', 'STORYBOARD'];
    for (const hint of hints) {
      expect(guideSourceDescription(hint.owner as GuideSourceId).length).toBeGreaterThan(0);
      if (hint.navigate !== null) expect(views).toContain(hint.navigate);
      for (const citation of hint.sources) expect(citation.source).toMatch(/^[a-z_][A-Za-z0-9_.:-]*$/);
    }
  });

  it('facts 里不存在的维度不会被引用（收件箱缺失时不引用审核字段）', () => {
    const partial = guideInput({ workflow: projection({ selected: ['novel_writing'] }), tasks: tasksProjection([]) });
    const codes = codesOf(nextSteps(partial));
    expect(codes).toContain('TASKS_NONE_READ');
    expect(codes).not.toContain('INTENT_NOT_SET');
    expect(codes).not.toContain('REVIEW_ITEMS_UNRESOLVED');
    // 收件箱没有声明 ⇒ 它整条不会出现在 FACTS_PARTIALLY_UNREADABLE 的引用之外。
    const partialHint = hintOf(nextSteps(partial), 'FACTS_PARTIALLY_UNREADABLE');
    expect(partialHint.sources[0].detail).toContain('REVIEW_INBOX_PROJECTION');
    for (const hint of nextSteps(partial)) {
      for (const citation of hint.sources) expect(citation.source.startsWith('review_inbox.')).toBe(false);
    }
  });

  it('GuideFacts 的每个具名维度都能从解码结果里取到', () => {
    const facts: GuideFacts = fullProject().facts;
    expect(Object.keys(facts).sort()).toEqual([
      'asset_library', 'asset_overview', 'graph', 'identity', 'intent', 'modules', 'project_id',
      'review_inbox', 'storyboard', 'tasks', 'timeline',
    ]);
    expect(facts.project_id).toBe(PROJECT);
    expect(facts.identity).toBe(IDENTITY);
    expect(facts.modules?.length).toBe(7);
  });
});

describe('青简扩展点：存在但不可用', () => {
  it('冻结标记永远不可用，且不透露任何端点', () => {
    expect(QINGJIAN_EXTENSION.available).toBe(false);
    expect(QINGJIAN_EXTENSION.reason).toBe(GUIDE_CODES.qingjianUnavailable);
    expect(QINGJIAN_EXTENSION.message).toContain('不注册任何适配器');
    expect(Object.keys(QINGJIAN_EXTENSION).some(key => /connect|endpoint|url|token/i.test(key))).toBe(false);
  });
});

describe('分镜回执（复用既有 owner 解码器）', () => {
  it('已批准的分镜不再提示批准', () => {
    const approved = fullProject();
    expect(sourceReadable(approved, 'STORYBOARD_RECEIPT')).toBe(true);
    expect(approved.facts.storyboard?.shot_count).toBe(1);
    expect(approved.facts.storyboard?.approved).toBe(true);
    expect(codesOf(nextSteps(approved))).not.toContain('STORYBOARD_NOT_APPROVED');
  });

  it('未批准的分镜提示批准，并引用 owner 自己的 approved 字段', () => {
    const notApproved = fullProject({ storyboard: storyboardReceipt(2, false) });
    const hint = hintOf(nextSteps(notApproved), 'STORYBOARD_NOT_APPROVED');
    expect(hint.sources.map(entry => entry.source)).toEqual(['storyboard.approved', 'storyboard.shots']);
    expect(hint.sources[1].detail).toBe('2');
    expect(hint.navigate).toBe('STORYBOARD');
    expect(hint.next_action).toContain('原分镜 owner');
  });

  it('形状不合法的分镜回执被判不可读，绝不按"没有分镜"处理', () => {
    const broken = fullProject({ storyboard: { ...storyboardReceipt(1, false), model_called: true } });
    expect(sourceReadable(broken, 'STORYBOARD_RECEIPT')).toBe(false);
    expect(broken.problems.some(problem => problem.source === 'STORYBOARD_RECEIPT')).toBe(true);
    expect(codesOf(nextSteps(broken))).not.toContain('STORYBOARD_NOT_APPROVED');
  });
});
