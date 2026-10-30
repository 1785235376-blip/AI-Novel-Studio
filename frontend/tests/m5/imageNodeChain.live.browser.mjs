/**
 * [HERMIA-FE-20261030 BE-ALIGN] 「真实 API＋Mock provider」 IMAGE node chain harness (real app.main File storage; mock only for model output).
 * Env: DCI_BASE_URL (vite proxying to app.main), DCI_HOST_TOKEN (the dev session configured on that backend run; never hard-coded), DCI_OUT, PLAN (JSON steps).
 * Known limit (d657b424): local File novels need studio activation for providers (422 STUDIO_NEUTRAL_PROJECT_ACTIVATION_REQUIRED); activation is a labelled harness API step,
 * and once activated the app renders the neutral-studio shell, where this classic canvas path is not reachable. Not a pass harness yet.
 * Stage 3: Playwright + real app.main (File) + Mock A1111 via vite proxy.
 * Barriers = waitForResponse (no sleep for readiness of API steps).
 */
import {createRequire} from 'node:module';
const {chromium} = createRequire(import.meta.url)('playwright-core');
import fs from 'fs';
import path from 'path';

const BASE = process.env.DCI_BASE_URL || 'http://127.0.0.1:4741';
const OUT = process.env.DCI_OUT || '/workspace/hr/align-20261030/stage3';
const shots = path.join(OUT, 'shots');
fs.mkdirSync(shots, {recursive: true});

const report = {
  mode: 'REAL_API_PLUS_MOCK_PROVIDER',
  base: BASE,
  started_at: new Date().toISOString(),
  barriers: [],
  network_posts: [],
  auto_exec_posts: 0,
  steps: [],
  BACKEND_BLOCKED: null,
  ok: false,
};

function step(name, detail) {
  report.steps.push({name, ...detail, at: new Date().toISOString()});
  console.log('STEP', name, detail.status || detail.note || '');
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

const browser = await chromium.launch({executablePath: '/usr/bin/google-chrome', headless: true});
const context = await browser.newContext({viewport: {width: 1440, height: 900}});
const page = await context.newPage();
page.on('request', (req) => {
  if (req.method() !== 'GET' && req.url().includes('/api/')) {
    report.network_posts.push({method: req.method(), url: req.url()});
    if (/\/execute\b/.test(req.url()) && req.method() === 'POST') report.auto_exec_posts += 1;
  }
});

try {
  page.on('response', r => { if (/\/api\//.test(r.url())) console.log('NET', r.request().method(), r.status(), r.url().replace(BASE,'')); });
  // Seed novel via proxied API (no session needed for local file novels list/create)
  const title = `DCI Stage3 ${Date.now()}`;
  const novelRes = await page.request.post(`${BASE}/api/novels`, {data: {title}});
  const novel = await novelRes.json();
  step('api.novel', {status: novelRes.status(), id: novel.id});
  if (!novelRes.ok()) throw new Error('novel create failed ' + novelRes.status());
  // HARNESS SETUP (not UI): local File novels have no UI path to studio activation in this frontend (only the collaboration entry calls activate()).
  const act = await page.request.post(`${BASE}/api/projects/${novel.id}/studio/activate`, {headers: {'X-Session-Token': process.env.DCI_HOST_TOKEN}});
  step('api.studioActivate(harness)', {status: act.status()}); if (!act.ok()) throw new Error('activate ' + act.status() + ' ' + (await act.text()).slice(0, 200));

  // Pre-seed IMAGE canvas draft with one image_generate node (browser localStorage key)
  const graph = {
    nodes: [{id: 'generation-node-one', t: 'image_generate', x: 48, y: 80, title: 'Explicit generation node', prompt: 'A synthetic node intent; mock provider only'}],
    edges: [],
  };
  await context.addInitScript(({novelId, graph}) => {
    const key = `poemseed.rebuild.canvas.image.${novelId}`;
    localStorage.setItem(key, JSON.stringify(graph));
  }, {novelId: novel.id, graph});

  await page.goto(BASE + '/#skip-tour', {waitUntil: 'domcontentloaded'});
  await page.waitForTimeout(3000);
  const skipIntent = page.getByText('跳过，直接进入小说写作');
  if (await skipIntent.isVisible().catch(()=>false)) await skipIntent.click();
  // Open novel (file backend may already be inside a novel)
  const home = page.getByRole('heading', {name: '本机作品'});
  const launcher = page.locator('.feature-launcher');
  await Promise.race([
    home.waitFor({state: 'visible', timeout: 45_000}).catch(() => {}),
    launcher.waitFor({state: 'visible', timeout: 45_000}).catch(() => {}),
  ]);
  if (await launcher.isVisible().catch(() => false)) {
    const switcher = page.getByRole('button', {name: '切换本机作品'});
    if (await switcher.isVisible().catch(() => false)) {
      await switcher.click();
      await home.waitFor({state: 'visible', timeout: 20_000});
    }
  }
  if (await home.isVisible().catch(() => false)) {
    await page.getByRole('button', {name: title, exact: true}).click();
  }
  { const si = page.getByText('跳过，直接进入小说写作'); if (await si.isVisible().catch(()=>false)) await si.click(); }
  await page.getByText('图片',{exact:true}).first().waitFor({state:'visible',timeout:45000});
  { // The local shell reopens the last-opened novel; resolve which one by its visible title, then activate that one (harness setup, real API).
    await page.getByText(/《[^》]+》|项目：/).first().waitFor({state: 'visible', timeout: 30000}).catch(() => {}); const txt = await page.locator('body').innerText(); const m = txt.match(/《([^》]+)》/) || txt.match(/项目：\s*([^\n]+)/); const shown = m && m[1];
    const list = await (await page.request.get(`${BASE}/api/novels`)).json(); const arr = Array.isArray(list) ? list : (list.items || []);
    const hit = arr.find(x => x.title === shown); if (!hit) throw new Error('cannot resolve opened novel ' + shown);
    if (hit.id !== novel.id) { const a2 = await page.request.post(`${BASE}/api/projects/${hit.id}/studio/activate`, {headers: {'X-Session-Token': process.env.DCI_HOST_TOKEN}}); step('api.studioActivate(opened,harness)', {status: a2.status(), id: hit.id}); novel.id = hit.id; }
  }
  step('ui.openNovel', {status: 'ok', novel: novel.id});
  if (process.env.EXPLORE) {
    await page.getByRole('button',{name:/新建章节/}).first().click(); await page.waitForTimeout(1500);
    await page.getByRole('button',{name:'专业',exact:true}).first().click(); await page.waitForTimeout(800); { const sk=page.locator('[data-onboarding-skip]'); if (await sk.isVisible().catch(()=>false)) await sk.click(); }
    await page.getByText('搜索功能、章节或命令').first().click(); await page.waitForTimeout(500);
    await page.keyboard.type(process.env.EXPLORE); await page.waitForTimeout(1000);
    console.log('OPTS', JSON.stringify(await page.getByRole('option').allInnerTexts()));
    await page.screenshot({path: path.join(shots,'explore.png')}); process.exit(0);
  }
  // Bind local host session via the real UI (AI 任务 panel). Token = the dev session configured for this backend run (serve_backend.sh), read from env, never hard-coded here.
  const bindSession = async (tag) => {
    const TOKEN = process.env.DCI_HOST_TOKEN; if (!TOKEN) throw new Error('DCI_HOST_TOKEN missing');
    await page.keyboard.press('Escape'); await page.locator('[data-module-tab="NOVEL"]').first().click().catch(() => {}); await page.waitForTimeout(1500);
    { const si = page.getByText('跳过，直接进入小说写作'); if (await si.isVisible().catch(() => false)) await si.click(); }
    if (!(await page.getByText('AI 任务', {exact: true}).first().isVisible().catch(() => false))) {
      if (await page.getByRole('button', {name: /新建章节/}).first().isVisible().catch(() => false) && !(await page.getByText('第 1 章', {exact: false}).first().isVisible().catch(() => false))) await page.getByRole('button', {name: /新建章节/}).first().click();
      await page.getByRole('button', {name: '专业', exact: true}).first().click(); await page.waitForTimeout(800);
      const sk = page.locator('[data-onboarding-skip]'); if (await sk.isVisible().catch(() => false)) await sk.click();
    }
    if (!(await page.getByText('第 1 章', {exact: false}).first().isVisible().catch(() => false))) { await page.getByRole('button', {name: /新建章节/}).first().click(); await page.waitForTimeout(1500); }
    await page.getByText('AI 任务', {exact: true}).first().click();
    const inp = page.getByLabel('本机访问凭证'); await inp.waitFor({state: 'visible', timeout: 20000});
    await inp.fill(TOKEN);
    await barrier(page, 'local-session:' + tag, r => r.url().includes('/api/local-session') && r.status() === 200, () => page.getByRole('button', {name: '验证并绑定本机会话'}).click());
    await page.waitForTimeout(800);
    await page.screenshot({path: path.join(shots, `00-bind-${tag}.png`), fullPage: true});
    step('ui.bindLocalSession:' + tag, {status: 'ok'});
  };
  globalThis.__bind = bindSession;
  if (!process.env.EXPLORE) await bindSession('initial');
  await page.screenshot({path: path.join(shots, '01-novel-open.png'), fullPage: true});

  await page.getByText('图片',{exact:true}).first().click();
  // IMAGE shell
  await page.waitForTimeout(1500); { const nm = page.getByText('新手模式', {exact: true}).first(); if (await nm.isVisible().catch(() => false)) { await nm.click(); await page.waitForTimeout(1500); step('ui.interfaceMode新手', {status: 'ok'}); } }
  await page.waitForSelector('[data-module="IMAGE"], [data-module-shell="IMAGE"], .img-ws, [aria-label="图片工作区"]', {timeout: 45_000});
  step('ui.imageModule', {status: 'ok'});
  await page.screenshot({path: path.join(shots, '02-image-module.png'), fullPage: true});

  // Open canvas subview
  { const cc = page.getByRole('button', {name: '创作画布', exact: true}); if (await cc.first().isVisible().catch(() => false)) { await cc.first().click(); await page.waitForTimeout(2000); step('ui.studioShell创作画布', {status: 'ok'}); await page.screenshot({path: path.join(shots, '02b-studio-canvas.png'), fullPage: true}); } }
  const canvasTab = page.getByRole('button', {name: '图片画布'}).or(page.getByRole('tab', {name: /图片画布/})).or(page.locator('[data-image-sub="canvas"], button:has-text("图片画布")'));
  if (await canvasTab.first().isVisible().catch(() => false)) {
    await canvasTab.first().click();
  } else {
    // NovelModTabs may use text 图片画布 / canvas
    const t = page.getByText('图片画布', {exact: true});
    if (await t.first().isVisible().catch(() => false)) await t.first().click();
  }
  await page.waitForSelector('[data-img-view="canvas"], .img-canvaswrap, [aria-label*="无限画布"]', {timeout: 30_000});
  step('ui.canvasView', {status: 'ok'});

  console.log('NODES', JSON.stringify(await page.locator('[data-node-id]').evaluateAll(es=>es.map(e=>e.getAttribute('data-node-id')+':'+e.textContent.slice(0,30)))));
  // Select generation node
  if (await page.locator('[data-node-id]').count() === 0) {
    await page.locator('.img-canvaswrap, [data-img-view="canvas"]').first().click({button:'right', position:{x:300,y:250}});
    await page.getByText(/^\W*生成图片$/).first().click();
    await page.waitForTimeout(800);
    step('ui.addNodeViaContextMenu', {status:'ok'});
  }
  const node = page.locator('[data-node-id]').filter({hasText:'生成图片'});
  await node.first().waitFor({state: 'visible', timeout: 30_000});
  await node.first().click();
  step('ui.selectNode', {status: 'ok'});
  await page.screenshot({path: path.join(shots, '03-node-selected.png'), fullPage: true});

  await page.locator('textarea:visible').first().fill('A synthetic node intent; mock provider only');
  const openFormal = page.getByRole('button',{name:'打开正式生成与服务端保存'});
  if (await openFormal.isVisible().catch(()=>false)) await openFormal.click();
  // Formal panel should appear (RebuildFormalImageNode / CanvasImageNodeTask)
  const formal = page.getByRole('region', {name: '正式图片节点与保存位置'}).or(page.getByText('正式图片节点任务'));
  await formal.first().waitFor({state: 'visible', timeout: 20_000});
  step('ui.formalPanel', {status: 'ok'});


  globalThis.__page = page;
  const dump = async (tag) => {
    const names = await page.locator('button:visible, input[type=checkbox]:visible').evaluateAll(els => els.map(e => (e.getAttribute('aria-label')||e.textContent||'').trim().slice(0,40) + (e.disabled?' [D]':'')));
    console.log('DUMP', tag, JSON.stringify(names.filter(n=>n)));
  };
  const plan = JSON.parse(process.env.PLAN || '[]');
  for (const [i, act] of plan.entries()) {
    const [kind, name] = act;
    if (kind === 'click') { const b = page.getByRole('button', {name: new RegExp(name)}).first(); await b.waitFor({state:'visible', timeout: 20000}); await b.click(); }
    if (kind === 'check') { await page.getByRole('checkbox', {name: new RegExp(name)}).first().check(); }
    if (kind === 'select') { const sel = page.getByLabel(name).first(); const opts = await sel.locator('option').evaluateAll(o => o.map(x => x.value).filter(Boolean)); console.log('OPTIONS', name, JSON.stringify(opts)); await sel.selectOption(opts[0]); }
    if (kind === 'dbl') { const b = page.getByRole('button', {name: new RegExp(name)}).first(); await b.waitFor({state:'visible', timeout: 20000}); const before = report.network_posts.length; await b.dblclick(); await page.waitForTimeout(2500); const posts = report.network_posts.slice(before).filter(x => !/canvas-views|local-session/.test(x.url)); report.dbl = report.dbl || []; report.dbl.push({name, posts}); console.log('DBL', name, posts.length, JSON.stringify(posts)); }
    if (kind === 'trycheck') { const c = page.getByRole('checkbox', {name: new RegExp(name)}).first(); if (await c.isEnabled().catch(() => false)) await c.check(); else console.log('SKIP', name); }
    if (kind === 'dump') await dump('step' + i);
    if (kind === 'wait') { await page.waitForTimeout(Number(name)); }
    if (kind === 'reload') { await page.reload({waitUntil:'domcontentloaded'}); await page.waitForTimeout(3000); const n2 = page.locator('[data-node-id]').filter({hasText:'生成图片'}); const t=page.getByText('图片画布',{exact:true}); if (await t.first().isVisible().catch(()=>false)) await t.first().click(); await n2.first().waitFor({state:'visible', timeout: 30000}); await n2.first().click(); }
    if (kind === 'text') { const loc = page.getByRole('definition').or(page.locator('dl[aria-label="'+name+'"]')); console.log('TEXT', name, (await page.locator('[aria-label="'+name+'"]').first().innerText().catch(e=>'ERR '+e)).slice(0,800)); }
    await page.waitForTimeout(1500);
    await page.screenshot({path: path.join(shots, `c${String(i).padStart(2,'0')}-${kind}.png`), fullPage: true});
    console.log('DID', i, kind, name, 'auto_exec_posts', report.auto_exec_posts);
  }
  await dump('final');
  const region = page.getByRole('region', {name: '正式图片节点与保存位置'});
  console.log('REGION', (await region.first().innerText().catch(()=>'')).slice(0,1500));
  report.ok = true;
} catch (e) {
  await page.screenshot({path: path.join(shots, 'FAIL.png'), fullPage: true}).catch(() => {});
  console.error('ERR', String(e).slice(0,600), e.stack.split('\n').filter(l=>l.includes('pw_full')).join('|'));
} finally {
  fs.writeFileSync(path.join(OUT, 'chain-report.json'), JSON.stringify(report, null, 2));
  await browser.close();
  process.exit(0);
}

async function expectVisible(locator, timeout) { await locator.first().waitFor({state: "visible", timeout}); }
