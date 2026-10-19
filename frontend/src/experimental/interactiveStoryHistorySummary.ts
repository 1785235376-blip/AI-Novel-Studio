import type { StorySpec } from './interactiveStoryClient';

// Read-only summary of one archived version. Every value is derived from that
// version's own spec only: never from the current draft, other revisions, the
// running playback state or any regenerated backend data.
export type HistoryVersionSummary = {
  title: string | null;
  titleMissing: boolean;
  entryId: string | null;
  entryTitle: string | null;
  entryResolved: boolean;
  nodeCount: number | null;
  choiceCount: number | null;
  declaredEndingCount: number | null;
  variableCount: number | null;
};

const isRecord = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
const nonEmpty = (value: unknown): string | null => typeof value === 'string' && value.trim().length > 0 ? value : null;

export function summarizeHistorySpec(spec: unknown): HistoryVersionSummary {
  if (!isRecord(spec)) {
    return { title: null, titleMissing: true, entryId: null, entryTitle: null, entryResolved: false, nodeCount: null, choiceCount: null, declaredEndingCount: null, variableCount: null };
  }
  const title = nonEmpty(spec.title);
  const nodes = Array.isArray(spec.nodes) ? spec.nodes : null;
  const entryId = nonEmpty(spec.entry_node_id);
  let entryTitle: string | null = null;
  if (nodes && entryId) {
    const entryNode = nodes.find(node => isRecord(node) && node.node_id === entryId);
    if (isRecord(entryNode)) entryTitle = nonEmpty(entryNode.title);
  }
  let choiceCount: number | null = null;
  if (nodes) {
    let total = 0, complete = true;
    for (const node of nodes) {
      if (!isRecord(node) || !Array.isArray(node.choices)) { complete = false; break; }
      total += node.choices.length;
    }
    choiceCount = complete ? total : null;
  }
  let declaredEndingCount: number | null = null;
  if (nodes) {
    let total = 0, complete = true;
    for (const node of nodes) {
      if (!isRecord(node)) { complete = false; break; }
      const ending = node.ending;
      if (ending === undefined || ending === null) continue;
      if (typeof ending !== 'string') { complete = false; break; }
      if (ending.trim().length > 0) total += 1;
    }
    declaredEndingCount = complete ? total : null;
  }
  return {
    title,
    titleMissing: title === null,
    entryId,
    entryTitle,
    entryResolved: entryTitle !== null,
    nodeCount: nodes ? nodes.length : null,
    choiceCount,
    declaredEndingCount,
    variableCount: Array.isArray(spec.variables) ? spec.variables.length : null
  };
}

export type { StorySpec };
