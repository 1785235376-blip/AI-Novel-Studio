import type { Page, Request, Response, Route } from '@playwright/test';

type Pending = { sequence: number; method: string; path: string; started: number; status: number | null; phase: string };
const routeWords = new Set(('api v1 novels chapters experimental workspace search resume history tasks features capabilities health models text-models media-tasks writing-goal archived characters locations canon foreshadowing timeline relationships volumes scenes story-routes story_routes outline secrets assets exports diagnostics context author-context runtime model-center providers runtimes events generations jobs agent-jobs planning graphs world records imports inbox teams media audiobook profiles').split(' '));
/** Keep route shape only: no host, credentials, query, fragment or dynamic IDs. */
function safePath(request: Request) {
  try { return new URL(request.url()).pathname.split('/').map(part => !part || routeWords.has(part) ? part : ':id').join('/').slice(0, 240); }
  catch { return '/invalid-url'; }
}

/** Track actual requests; interception begins only when teardown is requested.
 * Page reload can detach the Page association from a terminal network event.
 * Context events still reconcile the exact Request objects this page started.
 * A timeout/failure never authorizes fixture deletion or closing under readers.
 */
export function createPageQuiescer(page: Page, timeoutMs = 15_000) {
  if (!Number.isFinite(timeoutMs) || timeoutMs <= 0) throw new Error('Drain timeout must be positive and bounded');
  const pending = new Map<Request, Pending>(), waiters = new Set<() => void>();
  const inspected = new WeakSet<Request>(), blocked = new WeakSet<Request>(), acknowledgedBlocked = new WeakSet<Request>();
  const context = page.context();
  let sequence = 0, completed = 0, blockedBeforeDispatch = 0, active = true;
  let phase = 'observing', teardown: Promise<void> | undefined;
  const notify = () => { if (!pending.size) for (const done of [...waiters]) done(); };
  const started = (request: Request) => {
    if (!active || acknowledgedBlocked.has(request) || !new URL(request.url()).pathname.startsWith('/api/')) return;
    const method = request.method();
    pending.set(request, { sequence: ++sequence, method: /^[A-Z]{1,12}$/.test(method) ? method : 'OTHER',
      path: safePath(request), started: Date.now(), status: null, phase: 'awaiting_response' });
  };
  const finished = (request: Request) => {
    if (!active) return;
    if (pending.delete(request)) completed++;
    notify();
  };
  const failed = (request: Request) => {
    if (!active) return;
    if (acknowledgedBlocked.has(request)) { pending.delete(request); notify(); return; }
    if (blocked.has(request)) {
      if (pending.has(request)) pending.get(request)!.phase = 'awaiting_teardown_abort_ack';
      return;
    }
    const item = pending.get(request);
    // A browser-side abort is not evidence that an already dispatched server
    // handler stopped touching files. Preserve it as an actionable blocker.
    if (item) item.phase = 'request_failed_server_completion_unknown';
  };
  const responseObserved = (response: Response) => {
    const request = response.request(), item = pending.get(request);
    if (!active || !item) return;
    item.status = response.status();
    if (!item.phase.startsWith('request_failed')) item.phase = 'awaiting_response_end';
    void response.finished().then(() => finished(request), () => {
      if (active && pending.has(request)) pending.get(request)!.phase = 'response_end_failed_server_completion_unknown';
    });
  };
  const inspect = (request: Request) => {
    if (inspected.has(request)) return;
    inspected.add(request);
    // Response.finished observes a real protocol completion; no sleep, retry
    // request, mock response or inferred idle interval establishes completion.
    void request.response().then(response => { if (response) responseObserved(response); }, () => {
      if (active && pending.has(request)) pending.get(request)!.phase = 'response_unavailable';
    });
  };
  const diagnostics = () => ({ phase, timeout_ms: timeoutMs, page_closed: page.isClosed(),
    pending_count: pending.size, completed_requests: completed, blocked_before_dispatch: blockedBeforeDispatch,
    pending: [...pending.values()].slice(0, 20).map(item => ({ sequence: item.sequence, method: item.method,
      path: item.path, status: item.status, phase: item.phase, age_ms: Math.max(0, Date.now() - item.started) })),
    diagnostics_truncated: pending.size > 20, contains_headers_body_query_or_dynamic_ids: false });
  const drain = async () => {
    for (const request of pending.keys()) inspect(request);
    if (!pending.size) return;
    await new Promise<void>((resolve, reject) => {
      const done = () => { clearTimeout(timer); waiters.delete(done); resolve(); };
      const timer = setTimeout(() => {
        waiters.delete(done);
        reject(new Error(`Owned-project cleanup blocked: page API requests did not drain; ${JSON.stringify(diagnostics())}`));
      }, timeoutMs);
      waiters.add(done);
      notify(); // Close the finish-between-snapshot-and-subscription race.
    });
  };
  const blockNew = async (route: Route) => {
    const request = route.request();
    // Mark only this intercepted request, never an older in-flight one. The
    // interception establishes it has not reached the backend.
    blocked.add(request);
    try { await route.abort('aborted'); acknowledgedBlocked.add(request); blockedBeforeDispatch++; pending.delete(request); notify(); }
    catch { if (pending.has(request)) pending.get(request)!.phase = 'teardown_interception_failed'; }
  };
  page.on('request', started);
  page.on('response', responseObserved);
  page.on('requestfinished', finished);
  page.on('requestfailed', failed);
  context.on('response', responseObserved);
  context.on('requestfinished', finished);
  context.on('requestfailed', failed);
  const quiesce = () => {
    if (teardown) return teardown;
    teardown = (async () => {
      try {
        phase = 'blocking_new_requests';
        if (!page.isClosed()) await page.route('**/api/**', blockNew);
        phase = 'draining'; await drain();
        if (!page.isClosed()) await page.close({ runBeforeUnload: false });
        phase = 'closed';
      } catch (error) { phase = 'blocked'; throw error; }
      finally {
        active = false;
        page.off('request', started); page.off('response', responseObserved);
        page.off('requestfinished', finished); page.off('requestfailed', failed);
        context.off('response', responseObserved); context.off('requestfinished', finished); context.off('requestfailed', failed);
      }
    })();
    return teardown;
  };
  return Object.assign(quiesce, { drain, diagnostics });
}
