import type { StoryPlay, StorySpec } from './interactiveStoryClient';

// Read-only derivation of a readable path from the saved story definition and the
// existing playback choice log. It never mutates the story, never evaluates
// conditions or variables, never follows an unrecorded edge and never looks a
// choice ID up outside the current node.
export type StoryPathIssueCode =
  | 'SPEC_UNAVAILABLE' | 'STORY_EMPTY' | 'ENTRY_MISSING' | 'ENTRY_UNKNOWN'
  | 'NODE_TITLE_MISSING' | 'CHOICES_UNAVAILABLE' | 'CHOICE_UNKNOWN' | 'CHOICE_AMBIGUOUS'
  | 'CHOICE_ID_INVALID' | 'CHOICE_LABEL_MISSING' | 'TARGET_MISSING' | 'TARGET_INVALID'
  | 'TARGET_UNKNOWN' | 'STEP_LIMIT' | 'PATH_INVALID' | 'CURRENT_NODE_MISMATCH' | 'STEPS_MISMATCH';

export type StoryPathIssue = {
  code: StoryPathIssueCode;
  message: string;
  nodeId?: string;
  choiceId?: string;
  target?: string;
};

export type StoryPathChoice = { id: string; label: string | null; labelMissing: boolean };

export type StoryPathStep = {
  step: number;
  nodeId: string;
  title: string | null;
  choice: StoryPathChoice | null;
  issues: StoryPathIssue[];
};

export type StoryPathStop =
  | 'NONE' | 'SPEC_UNAVAILABLE' | 'STORY_EMPTY' | 'ENTRY_MISSING' | 'ENTRY_UNKNOWN'
  | 'PATH_INVALID' | 'CHOICE_ID_INVALID' | 'CHOICES_UNAVAILABLE' | 'CHOICE_UNKNOWN'
  | 'CHOICE_AMBIGUOUS' | 'TARGET_MISSING' | 'TARGET_INVALID' | 'TARGET_UNKNOWN' | 'STEP_LIMIT';

export type StoryPathView = {
  steps: StoryPathStep[];
  issues: StoryPathIssue[];
  stoppedBy: StoryPathStop;
};

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const read = (row: unknown, key: string): unknown => isRecord(row) ? row[key] : undefined;
const asText = (value: unknown): string | null => typeof value === 'string' ? value : null;
const hasText = (value: string | null): value is string => value !== null && value.trim().length > 0;
const positiveInt = (value: unknown): number | null => typeof value === 'number' && Number.isInteger(value) && value > 0 ? value : null;
const describeRaw = (value: unknown): string => {
  if (typeof value === 'string') return value;
  try { return JSON.stringify(value) ?? String(value); } catch { return String(value); }
};
const titleOf = (node: unknown): string | null => {
  const title = asText(read(node, 'title'));
  return hasText(title) ? title : null;
};
const titleIssue = (nodeId: string): StoryPathIssue => ({ code: 'NODE_TITLE_MISSING', nodeId, message: '节点 ' + nodeId + ' 的标题缺失，仍保留原始节点 ID。' });

export function deriveStoryPath(spec: StorySpec | undefined, play: StoryPlay | undefined): StoryPathView {
  const steps: StoryPathStep[] = [];
  const issues: StoryPathIssue[] = [];
  let stoppedBy: StoryPathStop = 'NONE';
  const stop = (reason: StoryPathStop) => { stoppedBy = reason; };
  const view = (): StoryPathView => ({ steps, issues, stoppedBy });
  if (!isRecord(spec)) {
    issues.push({ code: 'SPEC_UNAVAILABLE', message: '互动故事定义不可用，无法展示步骤路径。' });
    stop('SPEC_UNAVAILABLE');
    return view();
  }
  const rawNodes = read(spec, 'nodes');
  const nodes = new Map<string, unknown>();
  if (Array.isArray(rawNodes)) for (const node of rawNodes) {
    const id = asText(read(node, 'node_id'));
    if (id !== null && !nodes.has(id)) nodes.set(id, node);
  }
  if (!nodes.size) {
    issues.push({ code: 'STORY_EMPTY', message: '故事没有可解析的节点，无法展示步骤路径。' });
    stop('STORY_EMPTY');
    return view();
  }
  const entry = asText(read(spec, 'entry_node_id'));
  if (!hasText(entry)) {
    issues.push({ code: 'ENTRY_MISSING', message: '入口节点缺失：已保存的 entry_node_id 为空，未选择任何替代节点，无法解析步骤路径。' });
    stop('ENTRY_MISSING');
    return view();
  }
  const entryNode = nodes.get(entry);
  if (!entryNode) {
    steps.push({ step: 1, nodeId: entry, title: null, choice: null, issues: [{ code: 'ENTRY_UNKNOWN', nodeId: entry, message: '未知入口节点：故事定义中不存在节点 ' + entry + '，停止继续解析。' }] });
    stop('ENTRY_UNKNOWN');
    return view();
  }
  const firstIssues: StoryPathIssue[] = [];
  if (!titleOf(entryNode)) firstIssues.push(titleIssue(entry));
  steps.push({ step: 1, nodeId: entry, title: titleOf(entryNode), choice: null, issues: firstIssues });

  let recorded: unknown[] = [];
  if (play !== undefined) {
    const rawPath = read(play, 'path');
    if (rawPath === undefined || rawPath === null) recorded = [];
    else if (Array.isArray(rawPath)) recorded = rawPath;
    else {
      issues.push({ code: 'PATH_INVALID', message: '播放记录中的路径格式无效，无法展示后续步骤。' });
      stop('PATH_INVALID');
      return view();
    }
  }
  const declaredMax = positiveInt(read(spec, 'max_steps')) ?? (play === undefined ? null : positiveInt(read(play, 'max_steps')));
  const cap = declaredMax === null ? recorded.length : Math.min(recorded.length, declaredMax);
  let currentNodeId = entry;
  let currentNode: unknown = entryNode;
  for (let index = 0; index < cap; index += 1) {
    const rawChoice = recorded[index];
    const choiceId = asText(rawChoice);
    if (!hasText(choiceId)) {
      issues.push({ code: 'CHOICE_ID_INVALID', nodeId: currentNodeId, choiceId: describeRaw(rawChoice), message: '路径记录中的选择 ID 格式无效，无法继续解析后续节点。' });
      stop('CHOICE_ID_INVALID');
      return view();
    }
    const choices = read(currentNode, 'choices');
    if (!Array.isArray(choices)) {
      issues.push({ code: 'CHOICES_UNAVAILABLE', nodeId: currentNodeId, choiceId, message: '当前节点 ' + currentNodeId + ' 的选择信息不可用，无法确定该步骤的选择。' });
      stop('CHOICES_UNAVAILABLE');
      return view();
    }
    const matches = choices.filter(candidate => asText(read(candidate, 'id')) === choiceId);
    if (matches.length > 1) {
      issues.push({ code: 'CHOICE_AMBIGUOUS', nodeId: currentNodeId, choiceId, message: '选择 ' + choiceId + ' 在当前节点 ' + currentNodeId + ' 中存在重复（歧义），无法确定唯一选择，停止继续解析。' });
      stop('CHOICE_AMBIGUOUS');
      return view();
    }
    if (!matches.length) {
      const ending = asText(read(currentNode, 'ending'));
      issues.push({ code: 'CHOICE_UNKNOWN', nodeId: currentNodeId, choiceId, message: hasText(ending)
        ? '路径记录与当前故事定义不一致：节点 ' + currentNodeId + ' 已是结局，但仍记录选择 ' + choiceId + '。'
        : '未知选择：当前节点 ' + currentNodeId + ' 中不存在 choice ' + choiceId + '；路径记录与当前故事定义不一致。' });
      stop('CHOICE_UNKNOWN');
      return view();
    }
    const choice = matches[0];
    const labelRaw = asText(read(choice, 'label'));
    const label = hasText(labelRaw) ? labelRaw : null;
    const targetRaw = read(choice, 'target');
    if (targetRaw === undefined || targetRaw === null) {
      issues.push({ code: 'TARGET_MISSING', nodeId: currentNodeId, choiceId, message: '目标节点缺失：选择 ' + choiceId + ' 未记录 target，已停止后续解析。' });
      stop('TARGET_MISSING');
      return view();
    }
    const target = asText(targetRaw);
    if (target === null) {
      issues.push({ code: 'TARGET_INVALID', nodeId: currentNodeId, choiceId, target: describeRaw(targetRaw), message: '目标节点格式无效：选择 ' + choiceId + ' 的 target 不是节点 ID 字符串，已停止后续解析。' });
      stop('TARGET_INVALID');
      return view();
    }
    if (!target.trim()) {
      issues.push({ code: 'TARGET_MISSING', nodeId: currentNodeId, choiceId, message: '目标节点缺失：选择 ' + choiceId + ' 的 target 为空，已停止后续解析。' });
      stop('TARGET_MISSING');
      return view();
    }
    const nextNode = nodes.get(target);
    if (!nextNode) {
      issues.push({ code: 'TARGET_UNKNOWN', nodeId: currentNodeId, choiceId, target, message: '目标节点不存在：选择 ' + choiceId + ' 指向 ' + target + '，故事定义中不存在该节点，已停止后续解析。' });
      stop('TARGET_UNKNOWN');
      return view();
    }
    const stepIssues: StoryPathIssue[] = [];
    if (label === null) stepIssues.push({ code: 'CHOICE_LABEL_MISSING', nodeId: target, choiceId, message: '选择 ' + choiceId + ' 的文案缺失，仍保留原始 choice ID。' });
    if (!titleOf(nextNode)) stepIssues.push(titleIssue(target));
    steps.push({ step: steps.length + 1, nodeId: target, title: titleOf(nextNode), choice: { id: choiceId, label, labelMissing: label === null }, issues: stepIssues });
    currentNodeId = target;
    currentNode = nextNode;
  }
  if (cap < recorded.length) {
    issues.push({ code: 'STEP_LIMIT', nodeId: currentNodeId, message: '路径记录长度 ' + recorded.length + ' 超过步数上限 ' + String(declaredMax) + '，已停止解析超出部分。' });
    stop('STEP_LIMIT');
    return view();
  }
  if (play !== undefined) {
    const reportedNodeId = asText(read(read(play, 'node'), 'node_id'));
    const lastNodeId = steps[steps.length - 1].nodeId;
    if (reportedNodeId !== null && reportedNodeId !== lastNodeId) {
      issues.push({ code: 'CURRENT_NODE_MISMATCH', nodeId: lastNodeId, message: '路径记录与当前故事定义不一致：按已记录选择与 choice.target 应到达节点 ' + lastNodeId + '，但播放记录当前节点为 ' + reportedNodeId + '。' });
    }
    const reportedSteps = read(play, 'steps');
    if (typeof reportedSteps === 'number' && Number.isInteger(reportedSteps) && reportedSteps !== recorded.length) {
      issues.push({ code: 'STEPS_MISMATCH', message: '播放记录的步数 ' + String(reportedSteps) + ' 与已记录选择长度 ' + String(recorded.length) + ' 不一致，路径展示以已记录选择为准。' });
    }
  }
  return view();
}
