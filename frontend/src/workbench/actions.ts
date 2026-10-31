/**
 * [HERMIA-FE-20261022 slice M1-1] Typed action registry (task book §7.2).
 * Buttons / toolbar / context menu / shortcuts / command search must all call
 * `executeAction` so visibility, enablement, permission, confirmation and pending
 * de-duplication are re-checked AT EXECUTION TIME, not only at render time.
 * This registry never talks to the network itself; `run` must call existing SDK/adapters.
 */
import {LifecycleTracker, type ConfirmationBinding, checkConfirmation, type LifecycleToken} from './lifecycle';

export type ActionSurface = 'button' | 'toolbar' | 'contextMenu' | 'shortcut' | 'commandSearch';
export interface ActionContext { token: LifecycleToken; targetId: string | null; targetVersion: string | null; permissions: ReadonlySet<string>; input?: unknown; }
export type Availability = {enabled: true} | {enabled: false; reason: string};
export interface ActionDefinition {
  id: string; label: string; icon?: string; surfaces: readonly ActionSurface[]; shortcut?: string;
  /** Required permission strings; UI gate only — server stays authoritative. */
  permissions?: readonly string[];
  requiresConfirmation?: boolean;
  visible?: (ctx: ActionContext) => boolean;
  available?: (ctx: ActionContext) => Availability;
  run: (ctx: ActionContext, signal: AbortSignal) => Promise<unknown>;
  /** dev/test-only demo actions must set this; filtered out in production listings. */
  devOnly?: boolean;
}
export type ExecuteResult =
  | {status: 'done'; value: unknown}
  | {status: 'stale'} | {status: 'duplicate'} | {status: 'needs-confirmation'}
  | {status: 'blocked'; reason: string} | {status: 'error'; error: unknown};

export class ActionRegistry {
  private defs = new Map<string, ActionDefinition>();
  private pending = new Set<string>();
  constructor(private tracker: LifecycleTracker, private isDev = false) {}
  register(def: ActionDefinition): () => void {
    if (this.defs.has(def.id)) throw new Error(`duplicate action id: ${def.id}`);
    this.defs.set(def.id, def); return () => { this.defs.delete(def.id); };
  }
  get(id: string) { return this.defs.get(id); }
  list(surface: ActionSurface, ctx: ActionContext): ActionDefinition[] {
    return [...this.defs.values()].filter(d => d.surfaces.includes(surface) && (!d.devOnly || this.isDev) && (d.visible?.(ctx) ?? true));
  }
  availability(id: string, ctx: ActionContext): Availability {
    const d = this.defs.get(id); if (!d) return {enabled: false, reason: '动作未注册'};
    if (d.devOnly && !this.isDev) return {enabled: false, reason: '仅开发/测试模式可用'};
    for (const p of d.permissions ?? []) if (!ctx.permissions.has(p)) return {enabled: false, reason: `缺少权限：${p}`};
    return d.available?.(ctx) ?? {enabled: true};
  }
  isPending(id: string, targetId: string | null) { return this.pending.has(`${id}::${targetId ?? ''}`); }
  async execute(id: string, ctx: ActionContext, opts: {confirmation?: ConfirmationBinding; signal?: AbortSignal} = {}): Promise<ExecuteResult> {
    const d = this.defs.get(id);
    if (!d) return {status: 'blocked', reason: '动作未注册'};
    if (!this.tracker.isCurrent(ctx.token)) return {status: 'stale'};
    const av = this.availability(id, ctx); if (!av.enabled) return {status: 'blocked', reason: av.reason};
    if (d.requiresConfirmation) {
      if (!opts.confirmation) return {status: 'needs-confirmation'};
      const c = checkConfirmation(opts.confirmation, this.tracker, id, ctx.targetId ?? '', ctx.targetVersion, ctx.input);
      if (!c.ok) return {status: 'blocked', reason: `确认已失效：${c.reason}`};
    }
    const key = `${id}::${ctx.targetId ?? ''}`;
    if (this.pending.has(key)) return {status: 'duplicate'};
    this.pending.add(key);
    const ac = new AbortController(); opts.signal?.addEventListener('abort', () => ac.abort(), {once: true});
    try {
      const value = await d.run(ctx, ac.signal);
      // Abort is for resource mgmt only; stale check is separate (§11.2).
      if (!this.tracker.isCurrent(ctx.token)) return {status: 'stale'};
      return {status: 'done', value};
    } catch (error) {
      if (!this.tracker.isCurrent(ctx.token)) return {status: 'stale'};
      return {status: 'error', error};
    } finally { this.pending.delete(key); }
  }
}

/** Shortcut guard: never fire while IME composing or typing in an editable target (§7.2). */
export function shouldHandleShortcut(e: {isComposing?: boolean; keyCode?: number; target?: unknown}): boolean {
  if (e.isComposing || e.keyCode === 229) return false;
  const t = e.target as {tagName?: string; isContentEditable?: boolean} | null | undefined;
  if (!t) return true;
  if (t.isContentEditable) return false;
  return !['INPUT', 'TEXTAREA', 'SELECT'].includes((t.tagName ?? '').toUpperCase());
}
