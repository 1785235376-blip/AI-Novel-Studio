import type { CreativeDocument } from './types';
import type { PlanningSnapshot } from './studioProductionGraphContract';
import type { StudioGraphDefinition } from './studioGraphTypes';

const stable = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(stable).join(',')}]`;
  if (value && typeof value === 'object') return `{${Object.entries(value).sort(([a], [b]) => a.localeCompare(b)).map(([key, item]) => `${JSON.stringify(key)}:${stable(item)}`).join(',')}}`;
  return JSON.stringify(value) ?? '（无）';
};
export function directorContentChanges(before: CreativeDocument, after: CreativeDocument) {
  const rows: { field: string; before: string; after: string }[] = [];
  const add = (field: string, left: unknown, right: unknown) => {
    if (stable(left) !== stable(right)) rows.push({ field, before: stable(left), after: stable(right) });
  };
  for (const field of ['title', 'status', 'visual_target', 'source_independent', 'source_chapter_ids', 'source_documents', 'source_evidence', 'video_plan', 'script', 'shots'] as const) add(field, before[field], after[field]);
  for (const field of ['scenes', 'director_notes'] as const) {
    const left = before[field], right = after[field];
    add(`${field} 顺序`, left.map(row => row.id), right.map(row => row.id));
    const a = new Map(left.map(row => [row.id, row])), b = new Map(right.map(row => [row.id, row]));
    for (const id of new Set([...a.keys(), ...b.keys()])) {
      const old = a.get(id), next = b.get(id);
      if (!old || !next) add(`${field}/${id}`, old, next);
      else for (const key of new Set([...Object.keys(old), ...Object.keys(next)])) add(`${field}/${id}/${key}`, (old as unknown as Record<string, unknown>)[key], (next as unknown as Record<string, unknown>)[key]);
    }
  }
  return rows;
}
export function directorDownstream(graph?: StudioGraphDefinition, selected?: string) {
  if (!graph || !selected || !graph.nodes.some(node => node.id === selected && node.definition_id === 'director_plan')) return [];
  const visited = new Set([selected]), queue = [selected];
  for (let index = 0; index < queue.length; index++) for (const edge of graph.edges) {
    if (edge.source_node_id === queue[index] && !visited.has(edge.target_node_id)) { visited.add(edge.target_node_id); queue.push(edge.target_node_id); }
  }
  return graph.nodes.filter(node => node.id !== selected && visited.has(node.id));
}

const record = (value: unknown): value is Record<string, unknown> => !!value && typeof value === 'object' && !Array.isArray(value);
export function validDirectorSnapshot(value: unknown, id: string, version?: number): value is CreativeDocument {
  if (!record(value) || value.id !== id || value.mode !== 'DIRECTOR' || typeof value.title !== 'string'
    || !Number.isSafeInteger(value.version) || Number(value.version) < 1 || version !== undefined && value.version !== version) return false;
  return ['scenes', 'director_notes'].every(field => {
    const rows = value[field];
    return Array.isArray(rows) && rows.every(row => record(row) && typeof row.id === 'string' && !!row.id)
      && new Set(rows.map(row => row.id)).size === rows.length;
  });
}
/** Only an unambiguous original-owner receipt may establish the historical body. */
export function exactHistoricalDirector(history: unknown, pin: PlanningSnapshot, current: PlanningSnapshot): CreativeDocument | undefined {
  if (!record(history) || history.document_id !== pin.id || history.current_version !== current.version
    || !Array.isArray(history.items) || !Array.isArray(history.snapshot_digests)
    || !history.items.every(record) || !history.snapshot_digests.every(row => record(row)
      && Number.isSafeInteger(row.version) && Number(row.version) > 0 && typeof row.digest === 'string' && /^[a-f0-9]{64}$/.test(row.digest))) return undefined;
  for (const expected of [pin, current]) {
    const receipts = history.snapshot_digests.filter(row => row.version === expected.version);
    const rows = history.items.filter(row => row.version === expected.version);
    if (receipts.length !== 1 || receipts[0].digest !== expected.digest || rows.length !== 1 || !validDirectorSnapshot(rows[0], expected.id, expected.version)) return undefined;
  }
  return history.items.find(row => row.version === pin.version) as CreativeDocument;
}
