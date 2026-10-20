import type { StoryAnalysis, StoryNode, StoryPlay, StorySpec } from './interactiveStoryClient';

/** Display-only resolution of a server-returned choice path. It never evaluates
 * conditions or assignments: labels are resolved from the authoritative spec and
 * every resolution failure falls back to the raw server ID. */
export type PlayPathStep = {
  choiceId: string;
  label: string;
  nodeId: string;
  targetNodeId: string;
  targetTitle?: string;
  resolved: boolean;
};

export function describePlayPath(spec: StorySpec | undefined, path: readonly string[]): PlayPathStep[] {
  const nodes = spec?.nodes ?? [];
  const byId = new Map<string, StoryNode>();
  for (const node of nodes) if (!byId.has(node.node_id)) byId.set(node.node_id, node);
  let current = spec ? byId.get(spec.entry_node_id) : undefined;
  const steps: PlayPathStep[] = [];
  for (const choiceId of path) {
    const choice = current?.choices.find(candidate => candidate.id === choiceId);
    const target = choice ? byId.get(choice.target) : undefined;
    steps.push({ choiceId, label: choice?.label ?? choiceId, nodeId: current?.node_id ?? '', targetNodeId: choice?.target ?? '', targetTitle: target?.title, resolved: !!choice });
    current = target;
  }
  return steps;
}

/** Every server-returned choice stays visible. A disabled choice carries the
 * authored condition text as the reason; the client never re-evaluates it. */
export type ChoiceAvailability = {
  id: string;
  label: string;
  enabled: boolean;
  condition: string;
  reason?: string;
};

export function choiceOverview(spec: StorySpec | undefined, play: StoryPlay): ChoiceAvailability[] {
  const node = findUniqueNode(spec, play.node.node_id);
  return play.choices.map(choice => {
    const authored = node?.choices.find(candidate => candidate.id === choice.id);
    const condition = authored?.condition.trim() ?? '';
    return {
      id: choice.id,
      label: choice.label,
      enabled: choice.enabled,
      condition,
      reason: choice.enabled ? undefined : condition ? '服务端判定条件未满足：' + condition : '服务端判定当前不可选（该选项没有附加条件）。',
    };
  });
}

export function findUniqueNode(spec: StorySpec | undefined, nodeId: string | null | undefined): StoryNode | undefined {
  if (!spec || typeof nodeId !== 'string' || !nodeId) return undefined;
  const matches = spec.nodes.filter(node => node.node_id === nodeId);
  return matches.length === 1 ? matches[0] : undefined;
}

export function nodeTitle(spec: StorySpec | undefined, nodeId: string | null | undefined): string | undefined {
  return findUniqueNode(spec, nodeId)?.title;
}

export type VariableValueRow = { name: string; value: boolean | number; display: string; type?: 'bool' | 'int'; initial?: boolean | number };

export function variableValueRows(spec: StorySpec | undefined, play: StoryPlay): VariableValueRow[] {
  const variables = new Map((spec?.variables ?? []).map(variable => [variable.name, variable] as const));
  return Object.entries(play.variables).map(([name, value]) => {
    const declared = variables.get(name);
    return { name, value, display: String(value), type: declared?.type, initial: declared?.initial };
  });
}

export type AnalysisSummary = {
  present: boolean;
  endings: number;
  issues: number;
  warnings: number;
  statesChecked: number;
  analysisComplete: boolean;
  canReview: boolean;
  stateLimitReached: boolean;
  stepLimitReached: boolean;
  cycleStepCapRequired: number;
  unreachableNode: number;
  maxSteps: number;
};

export function analysisSummary(analysis: StoryAnalysis | undefined): AnalysisSummary {
  const warnings = analysis?.warnings ?? [];
  return {
    present: !!analysis,
    endings: analysis?.endings.length ?? 0,
    issues: analysis?.issues.length ?? 0,
    warnings: warnings.length,
    statesChecked: analysis?.states_checked ?? 0,
    analysisComplete: analysis?.analysis_complete ?? false,
    canReview: analysis?.can_review ?? false,
    stateLimitReached: analysis?.state_limit_reached ?? false,
    stepLimitReached: analysis?.step_limit_reached ?? false,
    cycleStepCapRequired: warnings.filter(warning => warning.code === 'CYCLE_STEP_CAP_REQUIRED').length,
    unreachableNode: warnings.filter(warning => warning.code === 'UNREACHABLE_NODE').length,
    maxSteps: analysis?.max_steps ?? 0,
  };
}

export type EndingRow = {
  key: string;
  nodeId: string;
  ending: string;
  choices: string[];
  steps: number;
  explored: boolean;
  warningCodes: string[];
  nodeTitle?: string;
};

/** Reachable endings come from the authoritative bounded analysis witness list.
 * Exploration is a UI-only session record and is never written back to the story. */
export function endingRows(analysis: StoryAnalysis | undefined, explored: Readonly<Record<string, boolean>>, spec?: StorySpec): EndingRow[] {
  return (analysis?.endings ?? []).map((ending, index) => ({
    key: ending.node_id + ':' + String(index),
    nodeId: ending.node_id,
    ending: ending.ending,
    choices: [...ending.choices],
    steps: ending.choices.length,
    explored: explored[ending.node_id] === true,
    warningCodes: (analysis?.warnings ?? []).filter(warning => warning.node_id === ending.node_id).map(warning => warning.code),
    nodeTitle: nodeTitle(spec, ending.node_id),
  }));
}

export const WARNING_LABELS: Record<string, string> = {
  CYCLE_STEP_CAP_REQUIRED: '循环需要步数上限',
  UNREACHABLE_NODE: '不可达节点',
};

const WARNING_EXPLANATIONS: Record<string, string> = {
  CYCLE_STEP_CAP_REQUIRED: '存在循环路径，试玩会受步数上限约束；循环本身不等于非法故事。',
  UNREACHABLE_NODE: '从入口节点不可达；请确认是否有意保留该节点。',
};

export type AnalysisWarningRow = { key: string; code: string; label: string; explanation: string; nodeId?: string; nodeTitle?: string };

export function analysisWarningRows(spec: StorySpec | undefined, analysis: StoryAnalysis | undefined): AnalysisWarningRow[] {
  return (analysis?.warnings ?? []).map((warning, index) => ({
    key: warning.code + ':' + (warning.node_id ?? '') + ':' + String(index),
    code: warning.code,
    label: WARNING_LABELS[warning.code] ?? '路径提醒',
    explanation: WARNING_EXPLANATIONS[warning.code] ?? '请结合路径与变量检查核对。',
    nodeId: warning.node_id,
    nodeTitle: nodeTitle(spec, warning.node_id),
  }));
}

export const ISSUE_LABELS: Record<string, string> = {
  NO_EXIT: '节点没有结局或选择',
  UNDEFINED_TARGET: '选择目标节点不存在',
  UNDEFINED_VARIABLE: '条件或赋值引用了未定义变量',
  CONDITION_TYPE_MISMATCH: '条件类型不匹配',
  ASSIGNMENT_TYPE_MISMATCH: '赋值类型不匹配',
  ASSIGNMENT_OUT_OF_BOUNDS: '赋值超出变量范围',
  NO_ENDING_PATH: '节点无法到达结局',
  CONDITIONAL_NO_EXIT: '某个状态中没有可用选择',
  NO_REACHABLE_ENDING_WITHIN_CAP: '步数上限内没有可达结局',
};

export type IssueCodeCount = { code: string; label: string; count: number };

export function issueCodeCounts(analysis: StoryAnalysis | undefined): IssueCodeCount[] {
  const counts = new Map<string, number>();
  for (const issue of analysis?.issues ?? []) counts.set(issue.code, (counts.get(issue.code) ?? 0) + 1);
  return [...counts.entries()]
    .map(([code, count]) => ({ code, label: ISSUE_LABELS[code] ?? code, count }))
    .sort((left, right) => right.count - left.count || left.code.localeCompare(right.code));
}

export type PlayStatusNote = { tone: 'info' | 'success' | 'warning'; text: string };

export function playStatusNote(play: StoryPlay): PlayStatusNote {
  if (play.status === 'ENDING') return { tone: 'success', text: '已到达结局；本次会话会把它记为已探索，不写回故事。' };
  if (play.status === 'STEP_CAP_REACHED') return { tone: 'warning', text: '已到步数上限。请从开头重试或修改已保存的路径；客户端不会自行解释条件。' };
  if (play.status === 'NO_EXIT') return { tone: 'warning', text: '当前变量状态下没有可用出口，请修正条件或赋值后重新试玩。' };
  return { tone: 'info', text: '服务端判定仍有可选选择；每一步都会把完整路径交回服务端重新校验变量与条件。' };
}
