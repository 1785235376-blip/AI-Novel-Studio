// [HERMIA-FE-20261025 M5] Real Chrome via Playwright against local vite (own port) + in-process MOCK backend.
import {chromium} from 'playwright';
import {createBackend} from './mockBackend.mjs';
export const BASE = process.env.M5_BASE || 'http://127.0.0.1:5391';
export const SHOTS = '/workspace/hr/m10/shots';
export async function open({viewport = {width: 1366, height: 768}, session = true, backend = createBackend(), storage = null, context = null, browser = null} = {}) {
  browser ??= await chromium.launch({executablePath: '/usr/bin/google-chrome', headless: true});
  context ??= await browser.newContext({viewport});
  const page = await context.newPage();
  const consoleLog = [];
  page.on('console', m => { if (['error', 'warning'].includes(m.type())) consoleLog.push(`${m.type()}: ${m.text()}`); });
  page.on('pageerror', e => consoleLog.push(`pageerror: ${e.message}`));
  await context.route('**/*', async route => {
    const req = route.request(), url = new URL(req.url());
    if (url.pathname.startsWith('/api/')) {
      let body = null; try { body = req.postDataJSON(); } catch {}
      const [status, json] = backend.handle(req.method(), req.url(), body);
      return route.fulfill({status, contentType: 'application/json', body: JSON.stringify(json)});
    }
    if (req.method() !== 'GET' && req.method() !== 'HEAD') { backend.st.blocked.push(`${req.method()} ${url.pathname}`); return route.abort(); }
    return route.continue();
  });
  if (session) await context.addInitScript(([s, sc]) => { if (!sessionStorage.getItem('m5-init')) { sessionStorage.setItem('m5-init', '1'); localStorage.setItem('studio.session', s); localStorage.setItem('studio.scope', JSON.stringify(sc)); } }, ['tok-m5', backend.d.SCOPE]);
  if (storage) await context.addInitScript(storage);
  await page.goto(`${BASE}/?uw=1`);
  return {browser, context, page, backend, consoleLog};
}
