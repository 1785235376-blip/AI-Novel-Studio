import type { Page, Request } from '@playwright/test';

/** Track real business requests without interception until teardown begins. */
export function createPageQuiescer(page: Page, timeoutMs = 15_000) {
  const pending = new Set<Request>();
  const drained = new Set<() => void>();
  const started = (request: Request) => {
    if (new URL(request.url()).pathname.startsWith('/api/')) pending.add(request);
  };
  const finished = (request: Request) => {
    pending.delete(request);
    if (!pending.size) for (const resolve of [...drained]) resolve();
  };
  page.on('request', started);
  page.on('requestfinished', finished);
  page.on('requestfailed', finished);
  return async () => {
    try {
      // Stop late polling/refetches from starting more FileRepository readers.
      // Existing requests are allowed to finish; closing first would abort them
      // client-side while their server handlers could still touch the fixture.
      if (!page.isClosed()) await page.route('**/api/**', route => route.abort('aborted'));
      if (pending.size) await new Promise<void>((resolve, reject) => {
        const done = () => { clearTimeout(timer); drained.delete(done); resolve(); };
        const timer = setTimeout(() => { drained.delete(done); reject(new Error('Owned-project cleanup blocked: page API requests did not drain')); }, timeoutMs);
        drained.add(done);
      });
      if (!page.isClosed()) await page.close({ runBeforeUnload: false });
    } finally {
      page.off('request', started);
      page.off('requestfinished', finished);
      page.off('requestfailed', finished);
    }
  };
}
