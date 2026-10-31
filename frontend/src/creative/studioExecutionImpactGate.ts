import type { CanvasVideoTaskPreview } from './canvasVideoTrimTask';
import { isIssuedExecutionImpactConfirmation } from '../experimental/executionImpact/ExecutionImpactPanel';
import { canonicalExecutionImpact, executionImpactSnapshot, fingerprintExecutionImpact,
  type ExecutionImpactConfirmation, type ExecutionImpactInput } from '../experimental/executionImpact/executionImpact';
import type { ProductionJob, ProductionPreview } from './studioProductionClient';

export type StudioExecutionImpactInput = ExecutionImpactInput & {
  boundary: { kind: 'CREATE' | 'EXECUTE'; job?: Pick<ProductionJob, 'id' | 'owner' | 'version' | 'request_digest'> };
  preview: ProductionPreview | CanvasVideoTaskPreview;
};
/** Ephemeral, single-use input review. Original owner still grants every action. */
export function studioExecutionImpactGate(input: StudioExecutionImpactInput, latest: () => StudioExecutionImpactInput | undefined, guard: () => boolean) {
  let owner: object;
  const snapshot = executionImpactSnapshot(input), canonical = snapshot.canonical;
  let retired = false, consumed = false, proof: ExecutionImpactConfirmation | undefined;
  const fingerprint = fingerprintExecutionImpact(snapshot).catch(() => { retired = true; return ''; });
  function current() {
    if (retired) return false;
    try {
      const value = latest();
      if (!guard() || !value || canonicalExecutionImpact(value) !== canonical) retired = true;
    } catch { retired = true; }
    return !retired;
  }
  function ready() {
    if (!current() || consumed || !proof) return false;
    try { if (!proof.isCurrent()) { retired = true; return false; } } catch { retired = true; return false; }
    return true;
  }
  const gate = { input, current, ready, retire: () => { retired = true; },
    async confirm(value: ExecutionImpactConfirmation) {
      if (!isIssuedExecutionImpactConfirmation(value, owner) || !current() || consumed || proof || value.contract !== 'studio-execution-impact-confirmation/1' || value.scope !== 'TASK') return false;
      const expected = await fingerprint;
      if (!current() || consumed || proof || !expected || value.inputFingerprint !== expected) return false;
      try { if (!value.isCurrent()) return false; } catch { return false; }
      proof = value; return ready();
    },
    consume() { if (!ready()) return false; consumed = true; return true; },
  };
  owner = gate; return gate;
}
export type StudioExecutionImpactGate = ReturnType<typeof studioExecutionImpactGate>;

// Only the existing preview projection's known null defaults and reference marker
// differ from the recorded command; all actual command fields remain compared.
function recordedCommand(value: ProductionJob['command']) {
  if (!value) return null;
  return JSON.parse(JSON.stringify(value, (key, item) => {
    if (key === 'reference_only' && item === true) return undefined;
    if (key === 'parameters' && item && typeof item === 'object') return Object.fromEntries(Object.entries(item).filter(([,v]) => v !== null));
    return item;
  }));
}
export function sameExecutionPreview(job: ProductionJob, preview: ProductionPreview) {
  return job.novel_id === preview.novel_id && job.branch_id === preview.branch_id && job.request_id === preview.request_id
    && job.request_digest === preview.request_digest && job.operation_id === preview.operation_id
    && canonicalExecutionImpact(recordedCommand(job.command)) === canonicalExecutionImpact(recordedCommand(preview.command))
    && canonicalExecutionImpact(job.provider) === canonicalExecutionImpact(preview.provider)
    && canonicalExecutionImpact(job.execution_recipe) === canonicalExecutionImpact(preview.execution_recipe);
}
