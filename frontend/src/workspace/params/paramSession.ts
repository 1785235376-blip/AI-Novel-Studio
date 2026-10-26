/**
 * [HERMIA-FE-20261025 U3-M7] Confirmable real parameter edit for the single-image vertical slice.
 * Source of truth = the provider's own capability declaration (`studioProductionClient.providers()` →
 * ProductionProvider.supported_parameters / image_capabilities). Nothing is invented:
 *  - editable   : listed in supported_parameters (cfg bounded by image_capabilities.cfg when declared)
 *  - readonly   : operation / provider / model / local-vs-cloud / prompt-recipe fixed by the original task
 *  - unsupported: keys present in the original task but not declared by the provider; plus the cloud model's internal
 *                 steps, which are not an editable workflow.
 * Flow (all explicit): edit → (old preview invalidated) → 生成预览 (POST /preview, no execution) → 确认创建 (create with
 *   reviewed_preview_digest) → 确认执行 (execute with expected_version + expected_request_digest).
 * Single-flight: a second click while in flight is ignored. Timeout / lost response ⇒ state UNKNOWN; NEVER resent.
 * The user must re-read the original task (get) to learn the truth. Cost is always UNKNOWN (no estimate endpoint).
 * 'shared-template' scope is BLOCKED: no template write interface exists (gap G-U3-5).
 */
import type {MediaCommand, ProductionJob, ProductionPreview, ProductionProvider} from '../../creative/studioProductionClient';
import type {ChangeScope, CostInfo, ParamField, ScopeLease} from '../contracts';

export interface ProductionPort {
  preview(command: MediaCommand): Promise<ProductionPreview>;
  create(command: MediaCommand, reviewed_preview_digest: string): Promise<ProductionJob>;
  execute(job: ProductionJob): Promise<ProductionJob>;
  get(owner: ProductionJob['owner'], id: string): Promise<ProductionJob>;
}

const LABELS: Record<string, string> = {cfg: '提示词引导强度', scale: '放大倍数', seed: '随机种子', steps: '步数', strength: '重绘强度', width: '宽度', height: '高度'};
export const label = (k: string) => LABELS[k] ?? '其他参数';
export const COST_UNKNOWN: CostInfo = {state: 'UNKNOWN', why: '服务端没有提供成本估算，所以这里不显示价格。'};
export const TEMPLATE_GAP = '共享模板修改暂不可用：现有接口没有模板写入能力，只能修改本次任务。';
export const CLOUD_INTERNAL = '云端模型内部步骤不可编辑：只能看到实际发出的接口调用。';

export function fieldsFromProvider(p: ProductionProvider, original: Record<string, string | number>): ParamField[] {
  const declared = new Set(p.supported_parameters);
  const out: ParamField[] = [
    {key: 'operation', label: '任务类型', mode: 'readonly', reason: '由原任务决定'},
    {key: 'model', label: '模型', mode: 'readonly', reason: '由原任务决定，换模型需要新建任务'},
    {key: 'route', label: p.local ? '本机执行' : '云端执行', mode: 'readonly', reason: '由原任务决定'},
  ];
  for (const k of p.supported_parameters) out.push({key: k, label: label(k), mode: 'editable'});
  for (const k of Object.keys(original)) if (!declared.has(k)) out.push({key: k, label: label(k), mode: 'unsupported', reason: '当前模型没有声明支持这个参数'});
  if (!p.local) out.push({key: 'cloud-internal', label: '模型内部步骤', mode: 'unsupported', reason: CLOUD_INTERNAL});
  return out;
}

export function validate(p: ProductionProvider, key: string, value: string | number): string | null {
  if (!p.supported_parameters.includes(key)) return '这个参数不可修改';
  if (key === 'cfg') { const c = p.image_capabilities?.cfg; const n = Number(value);
    if (!Number.isFinite(n)) return '请输入数字'; if (c && (n < c.min || n > c.max)) return `范围是 ${c.min}–${c.max}`; }
  if (key === 'scale') { const s = p.image_capabilities?.upscaling?.scales; if (s && !s.includes(Number(value) as 2 | 4)) return `只能是 ${s.join(' 或 ')}`; }
  return null;
}

export type SessionPhase =
  | {kind: 'editing'} | {kind: 'previewing'} | {kind: 'previewed'; preview: ProductionPreview}
  | {kind: 'creating'} | {kind: 'created'; job: ProductionJob} | {kind: 'executing'; job: ProductionJob}
  | {kind: 'executed'; job: ProductionJob} | {kind: 'unknown'; step: 'create' | 'execute'; job: ProductionJob | null; next: string}
  | {kind: 'failed'; text: string} | {kind: 'blocked'; text: string};

export const TIMEOUT_MS = 30000;
const UNKNOWN_NEXT = '结果未知：请求可能已被服务端处理。不会自动重发。请点「读取原任务核对」或到任务面板查看。';

function withTimeout<T>(p: Promise<T>, ms: number): Promise<T> {
  return new Promise((res, rej) => { const t = setTimeout(() => rej(new TimeoutLike()), ms); p.then(v => { clearTimeout(t); res(v); }, e => { clearTimeout(t); rej(e); }); });
}
class TimeoutLike extends Error {}
/** A failure where the server may have acted: timeout, network loss, 5xx. 4xx is a definite refusal. */
const ambiguous = (e: unknown) => e instanceof TimeoutLike || e instanceof TypeError
  || (typeof (e as {problem?: {status?: number}})?.problem?.status === 'number' && (e as {problem: {status: number}}).problem.status >= 500);

export class ParamSession {
  phase: SessionPhase = {kind: 'editing'};
  values: Record<string, string | number>;
  scope: ChangeScope = 'this-task';
  readonly cost = COST_UNKNOWN;
  readonly fields: ParamField[];
  private inflight = false;
  private listeners = new Set<() => void>();
  constructor(private port: ProductionPort, private provider: ProductionProvider, private base: MediaCommand, private lease: ScopeLease, private timeoutMs = TIMEOUT_MS) {
    this.values = {...base.parameters};
    this.fields = fieldsFromProvider(provider, base.parameters);
  }
  subscribe(f: () => void) { this.listeners.add(f); return () => { this.listeners.delete(f); }; }
  private set(p: SessionPhase) { if (!this.lease.isCurrent()) return; this.phase = p; for (const l of this.listeners) l(); }
  /** Edits always invalidate any earlier preview/confirmation — the old digest is never reused. */
  edit(key: string, value: string | number): string | null {
    const err = validate(this.provider, key, value); if (err) return err;
    if (this.inflight || ['creating', 'executing', 'created', 'executed', 'unknown'].includes(this.phase.kind)) return '任务已提交，不能再改参数';
    this.values = {...this.values, [key]: typeof this.base.parameters[key] === 'number' ? Number(value) : value};
    this.set({kind: 'editing'}); return null;
  }
  setScope(s: ChangeScope) { this.scope = s; this.set(s === 'shared-template' ? {kind: 'blocked', text: TEMPLATE_GAP} : {kind: 'editing'}); }
  changed(): string[] { return Object.keys(this.values).filter(k => this.values[k] !== this.base.parameters[k]); }
  command(): MediaCommand { return {...this.base, parameters: {...this.values}}; }

  private async once<T>(run: () => Promise<T>): Promise<T | undefined> {
    if (this.inflight || !this.lease.isCurrent()) return undefined; // double click / stale scope ⇒ ignored
    this.inflight = true;
    try { return await run(); } finally { this.inflight = false; }
  }
  /** Preview is non-executing (`automatic_dispatch:false`) and still only on explicit click. */
  preview() { return this.once(async () => {
    if (this.scope !== 'this-task') return;
    this.set({kind: 'previewing'});
    try { const pv = await withTimeout(this.port.preview(this.command()), this.timeoutMs); this.set({kind: 'previewed', preview: pv}); }
    catch { this.set({kind: 'failed', text: '预览没有生成，未提交任何任务。可以检查参数后再点「生成预览」。'}); }
  }); }
  /** Explicit confirmation #1: create the job bound to the reviewed preview digest. */
  confirmCreate(confirmedDigest: string) { return this.once(async () => {
    const ph = this.phase; if (ph.kind !== 'previewed' || ph.preview.preview_digest !== confirmedDigest) return;
    this.set({kind: 'creating'});
    try { const job = await withTimeout(this.port.create(this.command(), ph.preview.preview_digest), this.timeoutMs); this.set({kind: 'created', job}); }
    catch (e) { this.set(ambiguous(e) ? {kind: 'unknown', step: 'create', job: null, next: UNKNOWN_NEXT} : {kind: 'failed', text: '服务端拒绝创建任务，未提交。请重新生成预览后再确认。'}); }
  }); }
  /** Explicit confirmation #2: execute via the original production entry with expected_version + request_digest. */
  confirmExecute(confirmedVersion: number) { return this.once(async () => {
    const ph = this.phase; if (ph.kind !== 'created' || ph.job.version !== confirmedVersion) return;
    this.set({kind: 'executing', job: ph.job});
    try { const job = await withTimeout(this.port.execute(ph.job), this.timeoutMs); this.set({kind: 'executed', job}); }
    catch (e) { this.set(ambiguous(e) ? {kind: 'unknown', step: 'execute', job: ph.job, next: UNKNOWN_NEXT} : {kind: 'failed', text: '服务端拒绝执行（版本或请求已变化），没有重发。请读取原任务核对。'}); }
  }); }
  /** Read-only verification after UNKNOWN. Never re-executes; only reports what the owner says. */
  verify() { return this.once(async () => {
    const ph = this.phase; if (ph.kind !== 'unknown' || !ph.job) return;
    try { const job = await this.port.get(ph.job.owner, ph.job.id);
      // QUEUED ⇒ execute never landed: back to 'created' so the USER may confirm again (never automatic).
      this.set(job.status === 'UNKNOWN' ? {...ph, job} : job.status === 'QUEUED' ? {kind: 'created', job} : {kind: 'executed', job}); }
    catch { /* still unknown; stay */ }
  }); }
}
