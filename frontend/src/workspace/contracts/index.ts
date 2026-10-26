/**
 * [HERMIA-FE-20261025 LOOP-C0] Shared cross-unit contracts for the unified-loop task group (t150u M1–M10).
 * Types only (plus tiny pure helpers). Owned by 总控; work units consume, never fork. Changes go through 总控.
 * Every type here is a FRONTEND projection of an EXISTING owner/SDK response — no second backend state system.
 * Evidence kinds are mandatory on every acceptance claim (task book §五).
 */
import type {LayoutScope} from '../../workbench/layout';

// ── Evidence ──────────────────────────────────────────────────────────────────────────────────────────────
export type EvidenceKind = 'mock' | 'synthetic-provider' | 'real-file-api' | 'real-browser' | 'real-provider' | 'postgresql' | 'windows';
export type MatrixStatus = 'IMPLEMENTED' | 'VERIFIED' | 'PARTIAL' | 'BLOCKED' | 'NOT_RUN';

// ── Unit 1 身份与恢复 (M1/M2) ─────────────────────────────────────────────────────────────────────────────
/** Real identity only from the bootstrap actor + collaboration scope. Never fabricated, never 'local-author'. */
export type WorkspaceIdentity =
  | {kind: 'real'; scope: LayoutScope; key: string}
  | {kind: 'session'; reason: 'no-actor' | 'no-project' | 'no-instance' | 'scope-mismatch' /* [HERMIA-FE-20261025 U1fix P2] */; key: string};
/** One activation of an identity. A→B→A creates a NEW lease; a retired lease never becomes current again. */
export interface ScopeLease {
  readonly key: string;
  readonly epoch: number;
  readonly signal: AbortSignal;
  isCurrent(): boolean;
  /** Wraps a callback so it becomes a no-op once the lease is retired. */
  guard<A extends unknown[]>(fn: (...a: A) => void): (...a: A) => void;
  /** Deferred work (debounced save etc.) cancelled on retire. */
  defer(ms: number, fn: () => void): void;
  retire(): void;
}

// ── Unit 3 任务与双画布 (M3/M4/M7) ───────────────────────────────────────────────────────────────────────
export type TaskSource = 'task-center' | 'production-job' | 'graph-run';
export type TaskPanelState =
  | {kind: 'loading'} | {kind: 'empty'} | {kind: 'error'; text: string; next: string}
  | {kind: 'revoked'; text: string} | {kind: 'not-connected'; gap: string}
  | {kind: 'ready'; items: TaskRef[]; truncated: boolean};
/** Read-only reference to an existing task row. `link` is null when the owner gives no work/node relation. */
export interface TaskRef {
  source: TaskSource; id: string; owner: string; status: string; revision: number | null;
  title: string; link: TaskWorkLink | null; stale: boolean;
}
export interface TaskWorkLink { canvas: 'creative' | 'execution'; documentId: string | null; nodeId: string | null; }
/** Return position for task→canvas→back navigation (M4). */
export interface NavReturnPoint { panelId: string; canvas: 'creative' | 'execution'; nodeIds: string[]; focusTestId: string | null; viewport: {x: number; y: number; zoom: number} | null; }

/** Parameter surface derived from a real capability declaration (M7). Never invented. */
export interface ParamField { key: string; label: string; mode: 'editable' | 'readonly' | 'unsupported'; reason?: string; }
export type CostInfo = {state: 'KNOWN'; estimate: number; unit: string} | {state: 'UNKNOWN'; why: string};
export type ChangeScope = 'this-task' | 'shared-template';

// ── Unit 4 结果与历史 (M8/M9) ──────────────────────────────────────────────────────────────────────────
export type ResultStanding = 'candidate' | 'reviewed-asset' | 'adopted';
export interface CandidateRef { jobId: string; owner: string; digest: string | null; standing: ResultStanding; sourceVersion: number | null; }
/** Pre-adopt check: every field must still match the live read, else block (no auto-adopt). */
export interface AdoptGuard { projectId: string; nodeId: string; jobId: string; jobVersion: number; assetVersion: number | null; leaseEpoch: number; }
export type RecordKind = 'local-draft' | 'saved-work' | 'asset-version' | 'execution-record';
/** Unknown execution outcome after refresh/offline/restart: read the original task first, never auto-regenerate. */
export type ExecutionTruth = {state: 'CONFIRMED'; status: string} | {state: 'UNKNOWN'; next: string};

// ── Unit 2 窗口与交互 (M6/M10) ────────────────────────────────────────────────────────────────────────
export interface CapabilityState { id: string; available: boolean; reason?: string; }
