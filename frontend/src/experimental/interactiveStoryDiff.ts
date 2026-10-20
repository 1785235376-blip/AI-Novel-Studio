import type { StoryChoice, StoryNode, StorySpec, StoryVariable } from './interactiveStoryClient';

/** Content-meaningful diff between two saved story revisions. This is a pure
 * spec comparison: it never evaluates conditions, never talks to the service and
 * never mutates either revision. */
export type StoryDiffKind =
  | 'TITLE' | 'ENTRY_NODE' | 'MAX_STEPS' | 'GRAPH_RECORDS'
  | 'NODE_ADDED' | 'NODE_REMOVED' | 'NODE_FIELD'
  | 'CHOICE_ADDED' | 'CHOICE_REMOVED' | 'CHOICE_FIELD'
  | 'VARIABLE_ADDED' | 'VARIABLE_REMOVED' | 'VARIABLE_FIELD';

export type StoryDiffRow = {
  kind: StoryDiffKind;
  key: string;
  nodeId?: string;
  nodeTitle?: string;
  choiceId?: string;
  choiceLabel?: string;
  variable?: string;
  field?: string;
  before?: string;
  after?: string;
};

const NODE_FIELD_ORDER: (keyof StoryNode)[] = ['title', 'node_version', 'dialogue', 'character_id', 'background_asset_id', 'music_asset_id', 'ending'];
const NODE_FIELD_LABELS: Record<string, string> = {
  title: '标题', node_version: '来源节点版本', dialogue: '对白', character_id: '对白角色',
  background_asset_id: '背景资产', music_asset_id: '音乐资产', ending: '结局',
};
const CHOICE_FIELD_ORDER: (keyof StoryChoice)[] = ['label', 'target', 'condition', 'assignments'];
const CHOICE_FIELD_LABELS: Record<string, string> = { label: '选项文案', target: '目标节点', condition: '条件', assignments: '选项赋值' };
const VARIABLE_FIELD_ORDER: (keyof StoryVariable)[] = ['type', 'initial', 'minimum', 'maximum'];
const VARIABLE_FIELD_LABELS: Record<string, string> = { type: '类型', initial: '初始值', minimum: '最小值', maximum: '最大值' };
const MAX_TEXT = 160;

function clip(text: string): string {
  const characters = [...text];
  return characters.length > MAX_TEXT ? characters.slice(0, MAX_TEXT - 1).join('') + '…' : text;
}

export function formatStoryDiffValue(value: unknown): string {
  if (value === null || value === undefined) return '（无）';
  if (typeof value === 'string') return value === '' ? '（空）' : clip(value);
  if (typeof value === 'boolean') return value ? 'true' : 'false';
  if (typeof value === 'number') return Number.isFinite(value) ? String(value) : '（非数字）';
  if (Array.isArray(value)) return value.length ? value.map(item => formatStoryDiffValue(item)).join('、') : '（空列表）';
  if (typeof value === 'object') {
    try { return clip(JSON.stringify(sortedPlain(value as Record<string, unknown>))); } catch { return '（无法显示）'; }
  }
  return '（无法显示）';
}

function sortedPlain(value: Record<string, unknown>): Record<string, unknown> {
  const result: Record<string, unknown> = {};
  for (const key of Object.keys(value).sort()) result[key] = value[key];
  return result;
}

function valueKey(value: unknown): string {
  if (value === null || value === undefined) return 'null';
  if (typeof value === 'object' && !Array.isArray(value)) return JSON.stringify(sortedPlain(value as Record<string, unknown>));
  if (Array.isArray(value)) return JSON.stringify(value);
  return JSON.stringify(value);
}

function assignmentsText(value: unknown): string {
  if (!value || typeof value !== 'object' || Array.isArray(value)) return formatStoryDiffValue(value);
  const entries = Object.entries(value as Record<string, unknown>).sort(([left], [right]) => left.localeCompare(right));
  return entries.length ? entries.map(([name, item]) => name + '=' + formatStoryDiffValue(item)).join('、') : '（无）';
}

function arraySpec(source: unknown): any[] { return Array.isArray(source) ? source : []; }

function nodeKey(node: unknown): string | undefined {
  if (!node || typeof node !== 'object') return undefined;
  const id = (node as Record<string, unknown>).node_id;
  return typeof id === 'string' && id ? id : undefined;
}
function choiceKey(choice: unknown): string | undefined {
  if (!choice || typeof choice !== 'object') return undefined;
  const id = (choice as Record<string, unknown>).id;
  return typeof id === 'string' && id ? id : undefined;
}
function variableKey(variable: unknown): string | undefined {
  if (!variable || typeof variable !== 'object') return undefined;
  const name = (variable as Record<string, unknown>).name;
  return typeof name === 'string' && name ? name : undefined;
}

type Match = { pairs: { fromIndex: number; toIndex: number }[]; added: number[]; removed: number[] };

function matchItems(items: unknown[], keys: (item: unknown) => string | undefined, target: unknown[], targetKeys: (item: unknown) => string | undefined): Match {
  const used = new Set<number>();
  const pairs: { fromIndex: number; toIndex: number }[] = [];
  const added: number[] = [];
  target.forEach((item, toIndex) => {
    const key = targetKeys(item);
    let found = -1;
    if (key !== undefined) {
      for (let fromIndex = 0; fromIndex < items.length; fromIndex++) {
        if (used.has(fromIndex)) continue;
        if (keys(items[fromIndex]) === key) { found = fromIndex; break; }
      }
    }
    if (found >= 0) { used.add(found); pairs.push({ fromIndex: found, toIndex }); }
    else added.push(toIndex);
  });
  const removed = items.map((_, index) => index).filter(index => !used.has(index));
  return { pairs, added, removed };
}

function nodeReference(nodeId: string, title: string | undefined): string {
  return title ? '节点「' + title + '」（' + nodeId + '）' : '节点「' + nodeId + '」';
}

function variableSummary(variable: Record<string, unknown>): string {
  const type = typeof variable.type === 'string' ? variable.type : '未知类型';
  const initial = formatStoryDiffValue(variable.initial);
  const bounds = type === 'int' ? ' · ' + formatStoryDiffValue(variable.minimum) + ' 至 ' + formatStoryDiffValue(variable.maximum) : '';
  return type + ' · 初始 ' + initial + bounds;
}

export function diffStorySpecs(from: StorySpec, to: StorySpec): StoryDiffRow[] {
  if (!from || typeof from !== 'object' || !to || typeof to !== 'object') return [];
  const rows: StoryDiffRow[] = [];
  const source = from as unknown as Record<string, unknown>;
  const target = to as unknown as Record<string, unknown>;
  const storyField = (key: string, kind: StoryDiffKind, label: string) => {
    if (valueKey(source[key]) === valueKey(target[key])) return;
    rows.push({ kind, key: kind, field: label, before: formatStoryDiffValue(source[key]), after: formatStoryDiffValue(target[key]) });
  };
  storyField('title', 'TITLE', '故事标题');
  storyField('entry_node_id', 'ENTRY_NODE', '故事入口节点');
  storyField('max_steps', 'MAX_STEPS', '步数上限');
  const fromRecords = arraySpec(source.graph_record_ids), toRecords = arraySpec(target.graph_record_ids);
  if (valueKey(fromRecords) !== valueKey(toRecords)) {
    rows.push({ kind: 'GRAPH_RECORDS', key: 'GRAPH_RECORDS', field: '关联故事图谱记录', before: fromRecords.length + ' 项', after: toRecords.length + ' 项' });
  }

  const fromNodes = arraySpec(source.nodes), toNodes = arraySpec(target.nodes);
  const nodeMatch = matchItems(fromNodes, nodeKey, toNodes, nodeKey);
  for (const toIndex of nodeMatch.added) {
    const node = toNodes[toIndex] as Record<string, unknown>; const id = nodeKey(node) ?? '';
    rows.push({ kind: 'NODE_ADDED', key: 'NODE_ADDED:' + id + ':' + String(toIndex), nodeId: id, nodeTitle: typeof node.title === 'string' ? node.title : undefined, after: typeof node.title === 'string' ? node.title : id });
  }
  for (const fromIndex of nodeMatch.removed) {
    const node = fromNodes[fromIndex] as Record<string, unknown>; const id = nodeKey(node) ?? '';
    rows.push({ kind: 'NODE_REMOVED', key: 'NODE_REMOVED:' + id + ':' + String(fromIndex), nodeId: id, nodeTitle: typeof node.title === 'string' ? node.title : undefined, before: typeof node.title === 'string' ? node.title : id });
  }
  for (const pair of nodeMatch.pairs) {
    const beforeNode = fromNodes[pair.fromIndex] as Record<string, unknown>;
    const afterNode = toNodes[pair.toIndex] as Record<string, unknown>;
    const nodeId = nodeKey(afterNode) ?? nodeKey(beforeNode) ?? '';
    const title = typeof afterNode.title === 'string' ? afterNode.title : typeof beforeNode.title === 'string' ? beforeNode.title : undefined;
    for (const field of NODE_FIELD_ORDER) {
      if (valueKey(beforeNode[field]) === valueKey(afterNode[field])) continue;
      rows.push({ kind: 'NODE_FIELD', key: 'NODE_FIELD:' + nodeId + ':' + field, nodeId, nodeTitle: title, field: NODE_FIELD_LABELS[field] ?? field,
        before: formatStoryDiffValue(beforeNode[field]), after: formatStoryDiffValue(afterNode[field]) });
    }
    const beforeChoices = arraySpec(beforeNode.choices), afterChoices = arraySpec(afterNode.choices);
    const choiceMatch = matchItems(beforeChoices, choiceKey, afterChoices, choiceKey);
    for (const toIndex of choiceMatch.added) {
      const choice = afterChoices[toIndex] as Record<string, unknown>; const choiceId = choiceKey(choice) ?? '';
      rows.push({ kind: 'CHOICE_ADDED', key: 'CHOICE_ADDED:' + nodeId + ':' + choiceId + ':' + String(toIndex), nodeId, nodeTitle: title, choiceId, choiceLabel: typeof choice.label === 'string' ? choice.label : undefined,
        after: typeof choice.label === 'string' ? choice.label : choiceId });
    }
    for (const fromIndex of choiceMatch.removed) {
      const choice = beforeChoices[fromIndex] as Record<string, unknown>; const choiceId = choiceKey(choice) ?? '';
      rows.push({ kind: 'CHOICE_REMOVED', key: 'CHOICE_REMOVED:' + nodeId + ':' + choiceId + ':' + String(fromIndex), nodeId, nodeTitle: title, choiceId, choiceLabel: typeof choice.label === 'string' ? choice.label : undefined,
        before: typeof choice.label === 'string' ? choice.label : choiceId });
    }
    for (const choicePair of choiceMatch.pairs) {
      const beforeChoice = beforeChoices[choicePair.fromIndex] as Record<string, unknown>;
      const afterChoice = afterChoices[choicePair.toIndex] as Record<string, unknown>;
      const choiceId = choiceKey(afterChoice) ?? choiceKey(beforeChoice) ?? '';
      const choiceLabel = typeof afterChoice.label === 'string' ? afterChoice.label : typeof beforeChoice.label === 'string' ? beforeChoice.label : undefined;
      for (const field of CHOICE_FIELD_ORDER) {
        if (valueKey(beforeChoice[field]) === valueKey(afterChoice[field])) continue;
        const format = field === 'assignments' ? assignmentsText : formatStoryDiffValue;
        rows.push({ kind: 'CHOICE_FIELD', key: 'CHOICE_FIELD:' + nodeId + ':' + choiceId + ':' + field, nodeId, nodeTitle: title, choiceId, choiceLabel,
          field: CHOICE_FIELD_LABELS[field] ?? field, before: format(beforeChoice[field]), after: format(afterChoice[field]) });
      }
    }
  }

  const fromVariables = arraySpec(source.variables), toVariables = arraySpec(target.variables);
  const variableMatch = matchItems(fromVariables, variableKey, toVariables, variableKey);
  for (const toIndex of variableMatch.added) {
    const variable = toVariables[toIndex] as Record<string, unknown>; const name = variableKey(variable) ?? '';
    rows.push({ kind: 'VARIABLE_ADDED', key: 'VARIABLE_ADDED:' + name + ':' + String(toIndex), variable: name, after: variableSummary(variable) });
  }
  for (const fromIndex of variableMatch.removed) {
    const variable = fromVariables[fromIndex] as Record<string, unknown>; const name = variableKey(variable) ?? '';
    rows.push({ kind: 'VARIABLE_REMOVED', key: 'VARIABLE_REMOVED:' + name + ':' + String(fromIndex), variable: name, before: variableSummary(variable) });
  }
  for (const pair of variableMatch.pairs) {
    const beforeVariable = fromVariables[pair.fromIndex] as Record<string, unknown>;
    const afterVariable = toVariables[pair.toIndex] as Record<string, unknown>;
    const name = variableKey(afterVariable) ?? variableKey(beforeVariable) ?? '';
    for (const field of VARIABLE_FIELD_ORDER) {
      if (valueKey(beforeVariable[field]) === valueKey(afterVariable[field])) continue;
      rows.push({ kind: 'VARIABLE_FIELD', key: 'VARIABLE_FIELD:' + name + ':' + field, variable: name, field: VARIABLE_FIELD_LABELS[field] ?? field,
        before: formatStoryDiffValue(beforeVariable[field]), after: formatStoryDiffValue(afterVariable[field]) });
    }
  }
  return rows;
}

export type StoryDiffSummary = { total: number; story: number; nodes: number; choices: number; variables: number; identical: boolean };

export function summarizeStoryDiff(rows: readonly StoryDiffRow[]): StoryDiffSummary {
  const count = (prefixes: StoryDiffKind[]) => rows.filter(row => prefixes.includes(row.kind)).length;
  const story = count(['TITLE', 'ENTRY_NODE', 'MAX_STEPS', 'GRAPH_RECORDS']);
  const nodes = count(['NODE_ADDED', 'NODE_REMOVED', 'NODE_FIELD']);
  const choices = count(['CHOICE_ADDED', 'CHOICE_REMOVED', 'CHOICE_FIELD']);
  const variables = count(['VARIABLE_ADDED', 'VARIABLE_REMOVED', 'VARIABLE_FIELD']);
  return { total: rows.length, story, nodes, choices, variables, identical: rows.length === 0 };
}

export function describeStoryDiffRow(row: StoryDiffRow): string {
  const node = row.nodeId ? nodeReference(row.nodeId, row.nodeTitle) : '节点';
  const choice = row.choiceId ? '选择「' + (row.choiceLabel ?? row.choiceId) + '」（' + row.choiceId + '）' : '选择';
  const change = '历史「' + (row.before ?? '（无）') + '」→ 当前「' + (row.after ?? '（无）') + '」';
  switch (row.kind) {
    case 'TITLE': case 'ENTRY_NODE': case 'MAX_STEPS': case 'GRAPH_RECORDS':
      return (row.field ?? row.kind) + '：' + change;
    case 'NODE_ADDED': return '新增节点「' + (row.nodeTitle ?? row.nodeId ?? '') + '」' + (row.nodeId ? '（' + row.nodeId + '）' : '');
    case 'NODE_REMOVED': return '移除节点「' + (row.nodeTitle ?? row.nodeId ?? '') + '」' + (row.nodeId ? '（' + row.nodeId + '）' : '');
    case 'NODE_FIELD': return node + ' · ' + (row.field ?? '') + '：' + change;
    case 'CHOICE_ADDED': return node + ' · 新增' + choice;
    case 'CHOICE_REMOVED': return node + ' · 移除' + choice;
    case 'CHOICE_FIELD': return node + ' · ' + choice + ' · ' + (row.field ?? '') + '：' + change;
    case 'VARIABLE_ADDED': return '新增变量「' + (row.variable ?? '') + '」：' + (row.after ?? '');
    case 'VARIABLE_REMOVED': return '移除变量「' + (row.variable ?? '') + '」（原为 ' + (row.before ?? '') + '）';
    case 'VARIABLE_FIELD': return '变量「' + (row.variable ?? '') + '」 · ' + (row.field ?? '') + '：' + change;
    default: return row.kind;
  }
}
