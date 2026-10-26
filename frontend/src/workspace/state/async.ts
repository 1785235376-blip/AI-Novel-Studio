// [HERMIA-FE-20261024 M5-s1] Async robustness helpers for ?uw=1: honest timeouts and last-wins request gates.
export const WORKSPACE_TIMEOUTS = {readMs: 15000, writeMs: 20000};

export class WorkspaceTimeoutError extends Error {
  constructor(public readonly op: 'read' | 'write') { super(op === 'read' ? READ_TIMEOUT_TEXT : WRITE_TIMEOUT_TEXT); this.name = 'WorkspaceTimeoutError'; }
}
export const READ_TIMEOUT_TEXT = '读取超时：服务器长时间没有回应，请稍后重试。';
/** A write that timed out has an UNKNOWN result — never reported as saved, never as definitely failed. */
export const WRITE_TIMEOUT_TEXT = '保存超时：服务器没有回应，不确定是否已保存。修改还在面板里，请刷新后确认。';

/** Rejects with WorkspaceTimeoutError after ms; the underlying promise's late result is ignored. */
export function withTimeout<T>(p: Promise<T>, ms: number, op: 'read' | 'write'): Promise<T> {
  return new Promise<T>((resolve, reject) => {
    let done = false;
    const t = setTimeout(() => { if (!done) { done = true; reject(new WorkspaceTimeoutError(op)); } }, ms);
    p.then(v => { if (done) return; done = true; clearTimeout(t); resolve(v); },
      e => { if (done) return; done = true; clearTimeout(t); reject(e); });
  });
}

/**
 * Last-wins gate. `begin()` aborts the previous request's AbortController and returns a token; `isLatest(token)` is
 * false for any older request, so out-of-order resolutions from a previous project/selection are dropped.
 */
export class LatestGate {
  private seq = 0;
  private ctl: AbortController | null = null;
  begin(): {id: number; signal: AbortSignal} {
    this.ctl?.abort(); this.ctl = new AbortController();
    return {id: ++this.seq, signal: this.ctl.signal};
  }
  isLatest(t: {id: number}): boolean { return t.id === this.seq; }
  cancel(): void { this.seq++; this.ctl?.abort(); this.ctl = null; }
}
