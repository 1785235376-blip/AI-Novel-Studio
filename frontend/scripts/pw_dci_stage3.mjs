/**
 * Stage 3: Playwright + real app.main (File) + Mock A1111 via vite proxy.
 * Barriers = waitForResponse (no sleep for API readiness).
 * /novels?novel=… avoids IndependentStudio auto-entry so IMAGE uses ImageRebuild DualStack.
 */
import {chromium} from 'playwright';
import fs from 'fs';
import path from 'path';

const BASE = process.env.DCI_BASE_URL || 'http://127.0.0.1:37905';
const OUT = process.env.DCI_OUT || '/workspace/hr/dci-20261026/stage3';
const TOKEN = 'synthetic-studio-host';
const NOVEL = fs.existsSync(path.join(OUT, 'novel_id.txt'))
  ? fs.readFileSync(path.join(OUT, 'novel_id.txt'), 'utf8').trim()
  : 'dci-stage3-live';
const shots = path.join(OUT, 'shots');
fs.mkdirSync(shots, {recursive: true});

const report = {
  mode: 'REAL_API_PLUS_MOCK_PROVIDER',
  base: BASE,
  novelId: NOVEL,
  started_at: new Date().toISOString(),
  barriers: [],
  network_mutating: [],
  execute_posts: 0,
  steps: [],
  BACKEND_BLOCKED: null,
  ok: false,
};

function step(name, detail = {}) {
  report.steps.push({name, ...detail, at: new Date().toISOString()});
  console.log('STEP', name, detail.status ?? detail.note ?? 'ok');
}

async function barrier(page, name, predicate, action) {
  const waiter = page.waitForResponse(async (res) => {
    try { return await predicate(res); } catch { return false; }
  }, {timeout: 60_000});
  await action();
  const res = await waiter;
  const entry = {name, url: res.url(), status: res.status(), method: res.request().method()};
  report.barriers.push(entry);
  step(`barrier:${name}`, entry);
  return res;
}

const browser = await chromium.launch({channel: 'chrome', headless: true});
const context = await browser.newContext({viewport: {width: 1440, height: 900}});
const page = await context.newPage();
page.on('request', (req) => {
  if (req.method() === 'GET') return;
  if (!req.url().includes('/api/')) return;
  report.network_mutating.push({method: req.method(), url: req.url()});
  if (/\/execute\b/.test(req.url()) && req.method() === 'POST') report.execute_posts += 1;
});

try {
  const graph = {
    nodes: [{
      id: 'generation-node-one',
      t: 'image_generate',
      x: 80,
      y: 100,
      title: 'Explicit generation node',
      prompt: 'A synthetic node intent; mock provider only',
    }],
    edges: [],
  };
  await context.addInitScript(({novelId, graph}) => {
    try { sessionStorage.setItem('studio-start-gate-dismissed', '1'); } catch {}
    try {
      localStorage.setItem(`poemseed.rebuild.canvas.image.${novelId}`, JSON.stringify(graph));
    } catch {}
  }, {novelId: NOVEL, graph});

  // /novels route: skips IndependentStudio auto IMAGE request → ModuleWorkspaceRoutes ImageRebuild
  await page.goto(`${BASE}/novels?novel=${encodeURIComponent(NOVEL)}#skip-start`, {waitUntil: 'domcontentloaded'});
  await page.waitForFunction(() => !!document.querySelector('#root')?.children?.length, null, {timeout: 60_000});

  const bind = await page.evaluate(async (token) => {
    const res = await fetch('/api/local-session', {headers: {'X-Session-Token': token}});
    const receipt = await res.json();
    if (!res.ok) return {ok: false, receipt, status: res.status};
    const mod = await import('/src/localHostSession.ts');
    mod.bindLocalHostSession(token, receipt);
    const st = mod.useLocalHostSession.getState();
    return {ok: true, actorId: st.actorId, hasToken: !!st.token, epoch: st.epoch};
  }, TOKEN);
  step('bind.localHost', bind);
  if (!bind.ok) throw new Error('local-host bind failed ' + JSON.stringify(bind));

  // Wait for novel workspace (writing shell)
  await page.waitForSelector('.feature-launcher, [data-shell-mode], .module-nav, [aria-label="功能面板导航"]', {timeout: 60_000}).catch(() => {});
  await page.screenshot({path: path.join(shots, '00-novels-open.png'), fullPage: true});

  // Switch to 专业
  const pro = page.getByRole('button', {name: '专业', exact: true});
  if (await pro.isVisible().catch(() => false)) {
    await pro.click();
    step('ui.proMode', {status: 'clicked'});
  }

  // Open IMAGE via top nav
  const imageNav = page.locator('[data-module-tab="IMAGE"]');
  await imageNav.first().waitFor({state: 'visible', timeout: 30_000});
  await imageNav.first().click();

  // ImageRebuild shell
  await page.waitForSelector('[data-module-shell="IMAGE"], .img-ws, [aria-label="图片工作区"]', {timeout: 45_000});
  step('ui.imageShell', {status: 'ok'});
  await page.screenshot({path: path.join(shots, '01-image-shell.png'), fullPage: true});

  // DualStack: 双画布 (pro) or 图片画布
  const dualBtn = page.locator('[data-open-dual="true"]').or(page.getByRole('button', {name: '双画布'}));
  if (await dualBtn.first().isVisible().catch(() => false)) {
    await dualBtn.first().click();
  } else {
    await page.getByRole('button', {name: '图片画布'}).or(page.getByText('图片画布', {exact: true})).first().click();
  }
  await page.waitForSelector('[data-dual-stack="image"], [data-img-view="dual"], [data-img-view="canvas"]', {timeout: 30_000});
  step('ui.dualStack', {status: 'ok'});
  await page.screenshot({path: path.join(shots, '02-dualstack.png'), fullPage: true});

  const node = page.locator('[data-node-id="generation-node-one"]');
  await node.first().waitFor({state: 'visible', timeout: 30_000});
  await node.first().click();
  step('ui.selectNode', {status: 'ok'});
  await page.screenshot({path: path.join(shots, '03-node-selected.png'), fullPage: true});

  const openFormal = page.getByRole('button', {name: '打开正式生成与服务端保存'});
  await openFormal.waitFor({state: 'visible', timeout: 20_000});
  const execBefore = report.execute_posts;
  await barrier(
    page,
    'studio.overview',
    (res) => res.request().method() === 'GET' && /\/projects\/[^/]+\/studio\b/.test(res.url()) && !/canvas-views/.test(res.url()),
    () => openFormal.click(),
  );

  const saveBtn = page.getByRole('button', {name: '为此节点保存正式空白位置'});
  await saveBtn.waitFor({state: 'visible', timeout: 30_000});
  await page.screenshot({path: path.join(shots, '04-formal-ready.png'), fullPage: true});
  const createRes = await barrier(
    page,
    'canvas-views.create',
    (res) => res.request().method() === 'POST' && /\/canvas-views\b/.test(res.url()) && !/image-node-result/.test(res.url()),
    () => saveBtn.click(),
  );
  step('formal.blankSave', {status: createRes.status(), body: await createRes.text().then(t => t.slice(0, 240)).catch(() => '')});
  await page.screenshot({path: path.join(shots, '05-blank-saved.png'), fullPage: true});

  step('GUARD.auto_exec', {
    status: report.execute_posts === execBefore ? 'PASS' : 'FAIL',
    note: `execute_posts=${report.execute_posts} before=${execBefore}`,
  });

  // Try production preview if present
  const previewBtn = page.getByRole('button', {name: /预览/}).first();
  if (await previewBtn.isVisible().catch(() => false) && await previewBtn.isEnabled().catch(() => false)) {
    try {
      await barrier(
        page,
        'production.preview',
        (res) => res.request().method() === 'POST' && /preview/.test(res.url()),
        () => previewBtn.click(),
      );
      await page.screenshot({path: path.join(shots, '06-preview.png'), fullPage: true});
    } catch (e) {
      step('production.preview', {status: 'NOT_REACHED', note: String(e).slice(0, 200)});
    }
  } else {
    step('production.preview', {status: 'NOT_RUN', note: 'preview not enabled'});
  }

  // VIDEO unsupported
  await page.locator('[data-module-tab="VIDEO"]').first().click();
  await page.waitForSelector('[data-module-shell="VIDEO"], [data-dual-stack="video"]', {timeout: 20_000}).catch(() => {});
  const markers = await page.locator('[data-unavailable="canvas-run"], [data-unsupported="video-run"], [data-unsupported="video-node"]').count();
  step('ui.videoUnsupported', {status: markers > 0 ? 'PASS' : 'CHECK', note: `markers=${markers}`});
  await page.screenshot({path: path.join(shots, '07-video.png'), fullPage: true});

  const cap = JSON.parse(fs.readFileSync(path.join(OUT, 'capture.json'), 'utf8'));
  const blocked = cap.steps.find((s) => s.name === 'image-node-result');
  report.BACKEND_BLOCKED = {
    endpoint: 'POST .../canvas-views/{id}/image-node-result',
    status: blocked?.status,
    code: blocked?.body?.code || blocked?.body?.detail?.code,
    message: blocked?.body?.message || blocked?.body?.detail?.message,
    note: 'CREATIVE_CANVAS_IMAGE_NODE_FORBIDDEN — backend read-only; FE records BACKEND_BLOCKED, does not fix',
  };
  step('BACKEND_BLOCKED.image-node-result', report.BACKEND_BLOCKED);

  report.ok =
    report.steps.some((s) => s.name === 'ui.selectNode' && s.status === 'ok')
    && report.steps.some((s) => s.name === 'formal.blankSave' && Number(s.status) < 400)
    && report.steps.some((s) => s.name === 'GUARD.auto_exec' && s.status === 'PASS');
} catch (e) {
  report.error = String(e);
  report.stack = e?.stack;
  await page.screenshot({path: path.join(shots, 'FAIL.png'), fullPage: true}).catch(() => {});
  console.error(e);
} finally {
  report.finished_at = new Date().toISOString();
  fs.writeFileSync(path.join(OUT, 'playwright-report.json'), JSON.stringify(report, null, 2));
  await browser.close();
  console.log('REPORT', report.ok, 'barriers', report.barriers.length);
  process.exit(report.ok ? 0 : 1);
}
