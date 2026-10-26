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

  // Formal production flow: the first /预览/ button on the page is the view switch 「回到预览」
  // (ImageRebuild.tsx:127/141), not production preview. Use the exact original labels instead.
  const panel = page.locator('section[aria-label="媒体制作输入"]').first();
  const dumpButtons = async (tag) => {
    const names = await page.locator('button:visible').evaluateAll((els) => els.map((e) => `${e.textContent?.trim()}${e.disabled ? '[disabled]' : ''}`));
    step(`dump:${tag}`, {note: names.filter(Boolean).slice(0, 80).join(' | ')});
  };
  const click = async (name, label, pred) => {
    const btn = page.getByRole('button', {name, exact: true}).first();
    await btn.scrollIntoViewIfNeeded().catch(() => {});
    await btn.waitFor({state: 'visible', timeout: 20_000});
    await page.waitForFunction((el) => el && !el.disabled, await btn.elementHandle(), {timeout: 20_000});
    return barrier(page, label, pred, () => btn.click());
  };
  try {
    await panel.waitFor({state: 'visible', timeout: 20_000});
    await click('重新读取配置', 'production.providers', (r) => r.request().method() === 'GET' && /provider/.test(r.url()));
    // Explicit user choices (no auto-select): provider/model + license note.
    const sel = page.getByLabel('服务商与模型');
    const opt = await sel.locator('option').evaluateAll((os) => os.map((o) => o.value).filter(Boolean));
    step('ui.providerOptions', {note: opt.join(',')});
    await sel.selectOption(opt.find((v) => v.includes('automatic1111')) || opt[0]);
    await page.getByLabel('来源与授权说明').fill('Synthetic DCI browser acceptance; mock provider only');
    const pv = await click('读取制作预览', 'production.preview', (r) => r.request().method() === 'POST' && /\/production\/preview$/.test(new URL(r.url()).pathname));
    step('production.preview', {status: pv.status()});
    await page.screenshot({path: path.join(shots, '06-preview.png'), fullPage: true});
    const ackImpact = async (tag) => {
      const box = page.getByRole('checkbox', {name: '已核对本次输入变化与影响范围'}).last();
      await box.waitFor({state: 'visible', timeout: 20_000});
      await page.waitForFunction((el) => el && !el.disabled, await box.elementHandle(), {timeout: 20_000});
      await box.check();
      const n0 = report.network_mutating.length;
      await page.getByRole('button', {name: '确认本次输入核对', exact: true}).last().click();
      await page.getByText('当前输入已核对；这只是本地核对凭据').last().waitFor({timeout: 20_000});
      step(`impact.ack:${tag}`, {status: report.network_mutating.length === n0 ? 'PASS_NO_MUTATION' : 'FAIL'});
    };
    await ackImpact('create');
    await page.getByRole('checkbox', {name: '已核对本次输入、来源和处理边界'}).check();
    const execBeforeCreate = report.execute_posts;
    const cr = await click('仅创建任务并入队', 'production.create', (r) => r.request().method() === 'POST' && /\/production\/jobs$/.test(new URL(r.url()).pathname));
    step('production.create', {status: cr.status()});
    step('GUARD.no_auto_exec_after_create', {status: report.execute_posts === execBeforeCreate ? 'PASS' : 'FAIL', note: `execute_posts=${report.execute_posts}`});
    await page.screenshot({path: path.join(shots, '07-queued.png'), fullPage: true});

    const reprev = page.getByRole('button', {name: '读取原入队任务预览', exact: true});
    if (await reprev.isVisible().catch(() => false)) {
      await click('读取原入队任务预览', 'production.executePreview', (r) => r.request().method() === 'POST' && /preview/.test(r.url()));
      await ackImpact('execute');
    }
    // Duplicate-click guard: two rapid clicks must dispatch exactly one execute.
    const execBtn = page.getByRole('button', {name: '明确执行当前入队任务', exact: true}).first();
    await execBtn.scrollIntoViewIfNeeded();
    await page.waitForFunction((el) => el && !el.disabled, await execBtn.elementHandle(), {timeout: 20_000});
    const e0 = report.execute_posts;
    const ex = await barrier(page, 'production.execute', (r) => r.request().method() === 'POST' && /\/execute$/.test(new URL(r.url()).pathname),
      async () => { await execBtn.click(); await execBtn.click({force: true, timeout: 2000}).catch(() => {}); });
    step('production.execute', {status: ex.status()});
    await page.waitForFunction(() => !document.querySelector('[aria-busy="true"]'), null, {timeout: 30_000}).catch(() => {});
    step('GUARD.duplicate_execute', {status: report.execute_posts - e0 === 1 ? 'PASS' : 'FAIL', note: `execute_posts_delta=${report.execute_posts - e0}`});
    const rv0 = report.network_mutating.filter((m) => /\/review$/.test(m.url)).length;
    await click('读取并核对候选媒体', 'production.candidate', (r) => r.request().method() === 'GET' && /candidate|content|assets/.test(r.url()));
    step('GUARD.no_auto_review', {status: report.network_mutating.filter((m) => /\/review$/.test(m.url)).length === rv0 ? 'PASS' : 'FAIL'});
    const rbox = page.getByRole('checkbox', {name: '已查看本次候选，确认采用当前任务版本与输出摘要'});
    await rbox.waitFor({state: 'visible', timeout: 30_000});
    await page.waitForFunction((el) => el && !el.disabled, await rbox.elementHandle(), {timeout: 30_000});
    await rbox.check();
    const rv = await click('明确审核并入素材库', 'production.review', (r) => r.request().method() === 'POST' && /\/review$/.test(new URL(r.url()).pathname));
    step('production.review', {status: rv.status(), note: (await rv.text()).match(/"status":"[A-Z_]+"/)?.[0]});
    await page.screenshot({path: path.join(shots, '08-reviewed.png'), fullPage: true});

    // Backfill (BACKEND_BLOCKED): must be rejected safely, not shown as success.
    try {
      await click('核对正式结果与原节点位置', 'backfill.inspect', (r) => r.request().method() === 'GET' && /canvas-views\/[^/]+\/history/.test(r.url()));
      const bbox = page.locator('label:has-text("采用") input[type=checkbox]:not([disabled])').last();
      if (await bbox.count()) await bbox.check();
      const bf = await click('确认采用并保存节点位置', 'backfill.imageNodeResult', (r) => r.request().method() === 'POST' && /image-node-result$/.test(r.url()));
      await page.getByText('节点采用结果待核对；只能读取原记录，不会自动采用或重发。').first().waitFor({timeout: 20_000});
      const body = await page.locator('body').innerText();
      const leaked = /synthetic-studio-host|CREATIVE_SUBGRAPH_SOURCE_READ_REQUIRED|Traceback/.test(body);
      const success = body.includes('已保存正式节点资产位置');
      step('backfill.rejectedSafely', {status: bf.status() === 403 && !leaked && !success ? 'PASS' : 'FAIL', note: `http=${bf.status()} leaked=${leaked} successShown=${success}`});
      await page.screenshot({path: path.join(shots, '09-backfill-blocked.png'), fullPage: true});
    } catch (e) {
      step('backfill.rejectedSafely', {status: 'NOT_REACHED', note: String(e).slice(0, 300)});
      await dumpButtons('backfill');
    }
  } catch (e) {
    step('production.flow', {status: 'NOT_REACHED', note: String(e).slice(0, 300)});
    await dumpButtons('production');
    await page.screenshot({path: path.join(shots, '06-flow-fail.png'), fullPage: true});
  }

  // VIDEO unsupported. Root cause of markers=0: the stage3 project is activated as
  // NEUTRAL_STUDIO, so App.tsx:1466 routes non-IMAGE modules to the original
  // IndependentStudioWorkspace (unchanged product routing), which never mounts DualStack.
  // 1) record the neutral-studio routing; 2) check DualStack VIDEO on a plain (non-studio) novel.
  await page.locator('[data-module-tab="VIDEO"]').first().click();
  await page.waitForSelector('[data-module-shell="VIDEO"], [data-dual-stack="video"], [aria-label="Prompt 工作台"], h3, h2', {timeout: 20_000}).catch(() => {});
  const neutralDual = await page.locator('[data-dual-stack="video"]').count();
  step('ui.video.neutralStudioRouting', {status: 'INFO', note: `dual_stack_video=${neutralDual} (IndependentStudio owns VIDEO for NEUTRAL_STUDIO)`});
  await page.screenshot({path: path.join(shots, '10-video-neutral.png'), fullPage: true});
  const plain = await page.evaluate(async (token) => {
    const r = await fetch('/api/novels', {method: 'POST', headers: {'Content-Type': 'application/json', 'X-Session-Token': token}, body: JSON.stringify({title: 'DCI plain video ' + Date.now()})});
    return {status: r.status, id: (await r.json()).id};
  }, TOKEN);
  step('plainNovel.create', {status: plain.status});
  await page.goto(`${BASE}/novels?novel=${encodeURIComponent(plain.id)}#skip-start`, {waitUntil: 'domcontentloaded'});
  await page.waitForFunction(() => !!document.querySelector('#root')?.children?.length, null, {timeout: 60_000});
  await page.locator('[data-module-tab="VIDEO"]').first().waitFor({state: 'visible', timeout: 60_000});
  await page.locator('[data-module-tab="VIDEO"]').first().click();
  const pro2 = page.getByRole('button', {name: '专业', exact: true});
  await pro2.waitFor({state: 'visible', timeout: 30_000});
  await pro2.click();
  step('ui.video.proMode', {status: await pro2.getAttribute('aria-pressed')});
  const vd = page.locator('[data-dual-stack="video"]');
  await vd.first().waitFor({state: 'visible', timeout: 30_000}).catch(() => {});
  const marker = page.locator('[data-dual-stack="video"] [data-unsupported="video-run"][data-unavailable="canvas-run"]');
  const markers = await marker.count();
  const text = markers ? (await marker.first().innerText()) : '';
  const execVideo = report.network_mutating.filter((m) => /video/.test(m.url) && /execute|jobs/.test(m.url)).length;
  step('ui.videoUnsupported', {status: markers > 0 && /unsupported/.test(text) && execVideo === 0 ? 'PASS' : 'FAIL', note: `markers=${markers} text=${text} video_mutations=${execVideo}`});
  await page.screenshot({path: path.join(shots, '11-video-dual-unsupported.png'), fullPage: true});

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
    && report.steps.some((s) => s.name === 'GUARD.auto_exec' && s.status === 'PASS')
    && !report.steps.some((s) => /^(GUARD|backfill|ui.videoUnsupported|impact)/.test(s.name) && /FAIL|NOT_REACHED/.test(String(s.status)))
    && ['production.review', 'backfill.rejectedSafely', 'ui.videoUnsupported'].every((n) => report.steps.some((s) => s.name === n && (s.status === 200 || s.status === 'PASS')));
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
