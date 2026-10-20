import type { MediaCommand, ProductionJob, ProductionRecipe } from '../../creative/studioProductionClient';

export type ExecutionImpactInput = {
  scope: Pick<ProductionJob, 'novel_id' | 'branch_id'> & { incarnation: string };
  command: MediaCommand;
  recipe?: ProductionRecipe;
  previousJob?: ProductionJob;
  editScope: 'TASK' | 'SHARED_TEMPLATE';
};
export type ExecutionImpactDifference = { path: string; before: string; after: string; changed: boolean | null };
export type ExecutionImpactSnapshot = {
  canonical: string;
  differences: ExecutionImpactDifference[];
  previousCommandAvailable: boolean;
  recipeAvailable: boolean;
  taskOnly: boolean;
};
/** A local input-review receipt, never an execution permit or a backend digest. */
export type ExecutionImpactConfirmation = {
  readonly contract: 'studio-execution-impact-confirmation/1';
  readonly inputFingerprint: string;
  readonly scope: 'TASK';
  readonly isCurrent: () => boolean;
};

function invalid(): never { throw new Error('输入范围或原任务快照不完整，请从原入口重新读取核对。'); }

/** JSON wire semantics, sorted keys, ordered arrays. Includes every additive field. */
export function canonicalExecutionImpact(value: unknown): string {
  const visiting = new Set<object>();
  function encode(v: unknown): string {
    if (v === null || typeof v === 'string' || typeof v === 'boolean') return JSON.stringify(v);
    if (typeof v === 'number') { if (!Number.isFinite(v)) invalid(); return JSON.stringify(v); }
    if (!v || typeof v !== 'object' || visiting.has(v)) invalid();
    const prototype = Object.getPrototypeOf(v);
    if (!Array.isArray(v) && prototype !== Object.prototype && prototype !== null) invalid();
    visiting.add(v);
    let result: string;
    if (Array.isArray(v)) result = '[' + Array.from(v, item => encode(item)).join(',') + ']';
    else result = '{' + Object.keys(v).sort().filter(key => (v as Record<string, unknown>)[key] !== undefined)
      .map(key => JSON.stringify(key) + ':' + encode((v as Record<string, unknown>)[key])).join(',') + '}';
    visiting.delete(v);
    return result;
  }
  return encode(value);
}

function flatten(value: unknown, path: string, into: Map<string, string>) {
  if (value !== null && typeof value === 'object' && Object.keys(value).length) {
    for (const key of Object.keys(value).sort()) flatten((value as Record<string, unknown>)[key],
      Array.isArray(value) ? `${path}[${key}]` : `${path}.${key}`, into);
  } else into.set(path, typeof value === 'string' ? value : canonicalExecutionImpact(value));
}

export function executionImpactSnapshot(input: ExecutionImpactInput): ExecutionImpactSnapshot {
  const canonical = canonicalExecutionImpact(input), value = JSON.parse(canonical) as ExecutionImpactInput;
  const scope = value.scope;
  if (!scope || typeof scope.novel_id !== 'string' || !scope.novel_id.trim()
    || typeof scope.incarnation !== 'string' || !scope.incarnation.trim()
    || scope.branch_id !== null && (typeof scope.branch_id !== 'string' || !scope.branch_id.trim())
    || !value.command || !['TASK', 'SHARED_TEMPLATE'].includes(value.editScope)) invalid();
  const previous = value.previousJob;
  if (previous && (previous.novel_id !== scope.novel_id || previous.branch_id !== scope.branch_id)) invalid();
  if (value.recipe && value.recipe.operation_id !== value.command.operation_id) invalid();
  const differences: ExecutionImpactDifference[] = [];
  function compare(before: unknown, after: unknown, prefix: string, known: boolean) {
    const oldValues = new Map<string, string>(), nextValues = new Map<string, string>();
    if (before !== undefined) flatten(before, prefix, oldValues);
    if (after !== undefined) flatten(after, prefix, nextValues);
    for (const path of [...new Set([...oldValues.keys(), ...nextValues.keys()])].sort()) {
      const oldValue = oldValues.get(path), nextValue = nextValues.get(path);
      if (!known || oldValue !== nextValue) differences.push({ path, before: known ? oldValue ?? '未提供此字段' : '原快照未提供',
        after: nextValue ?? '本次未提供', changed: known ? oldValue !== nextValue : null });
    }
  }
  compare(previous?.command ?? undefined, value.command, 'command', !!previous?.command);
  compare(previous?.execution_recipe, value.recipe, 'recipe', !!previous?.execution_recipe && !!value.recipe);
  return { canonical, differences, previousCommandAvailable: !!previous?.command, recipeAvailable: !!value.recipe,
    taskOnly: value.editScope === 'TASK' };
}

export async function fingerprintExecutionImpact(snapshot: ExecutionImpactSnapshot): Promise<string> {
  const digest = await crypto.subtle.digest('SHA-256', new TextEncoder().encode(snapshot.canonical));
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('');
}
