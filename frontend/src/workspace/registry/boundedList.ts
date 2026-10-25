/**
 * [HERMIA-FE-20261025 U2-M10] Bounded loading + controlled subscriptions for large task/node counts.
 * - windowRange: only rows in view (+overscan) are rendered.
 * - pageCap: owners have no pagination (INTERFACE_COVERAGE: task center unpaged, production list ≤1000), so the UI
 *   reveals rows in fixed pages and says how many are hidden instead of mounting everything.
 * - SubscriptionHub: per-key fan-out, coalesced to one notify per microtask, hard cap on live subscribers, and
 *   dispose() drops everything (call on ScopeLease retire) so late pushes after a scope switch are ignored.
 */
export function windowRange(total: number, scrollTop: number, rowH: number, viewH: number, overscan = 6): {start: number; end: number} {
  if (total <= 0 || rowH <= 0) return {start: 0, end: 0};
  const start = Math.max(0, Math.floor(scrollTop / rowH) - overscan);
  const end = Math.min(total, Math.ceil((scrollTop + Math.max(0, viewH)) / rowH) + overscan);
  return {start, end: Math.max(start, end)};
}
export function pageCap(total: number, pages: number, pageSize = 100): {shown: number; hidden: number; text: string | null} {
  const shown = Math.min(total, Math.max(1, pages) * pageSize); const hidden = total - shown;
  return {shown, hidden, text: hidden > 0 ? `还有 ${hidden} 项没有显示。下一步：点「再显示 ${Math.min(pageSize, hidden)} 项」，或用搜索缩小范围。` : null};
}
export class SubscriptionHub<T> {
  private subs = new Map<string, Set<(v: T) => void>>();
  private pending = new Map<string, T>(); private scheduled = false; private dead = false;
  notifies = 0; dropped = 0;
  constructor(private maxSubscribers = 200) {}
  size() { let n = 0; for (const s of this.subs.values()) n += s.size; return n; }
  subscribe(key: string, fn: (v: T) => void): () => void {
    if (this.dead) return () => {};
    if (this.size() >= this.maxSubscribers) { this.dropped++; return () => {}; }
    let s = this.subs.get(key); if (!s) this.subs.set(key, s = new Set()); s.add(fn);
    return () => { s!.delete(fn); if (!s!.size) this.subs.delete(key); };
  }
  publish(key: string, v: T) {
    if (this.dead || !this.subs.has(key)) return;
    this.pending.set(key, v);
    if (this.scheduled) return; this.scheduled = true;
    queueMicrotask(() => {
      this.scheduled = false; if (this.dead) return;
      const batch = [...this.pending]; this.pending.clear();
      for (const [k, val] of batch) for (const fn of this.subs.get(k) ?? []) { this.notifies++; fn(val); }
    });
  }
  dispose() { this.dead = true; this.subs.clear(); this.pending.clear(); }
}
