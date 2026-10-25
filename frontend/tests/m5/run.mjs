// [HERMIA-FE-20261025 M5] Acceptance scenarios. Evidence kind: real browser (Chrome headless via Playwright) + MOCK backend.
import {writeFileSync, appendFileSync} from 'node:fs';
import {chromium} from 'playwright';
import {open, SHOTS} from './harness.mjs';
import {createBackend} from './mockBackend.mjs';
const VIEWPORTS = (process.env.M5_VP || '1366x768,1440x900,1920x1080').split(',').map(s => { const [w, h] = s.split('x').map(Number); return {width: w, height: h}; });
const ONLY = process.env.M5_ONLY ? process.env.M5_ONLY.split(',') : null;
const LOG = '/workspace/hr/m10/logs/m5-run.log', results = [];
const log = s => { console.log(s); appendFileSync(LOG, s + '\n'); };
const seedCanvas = P => { localStorage.setItem(`poemseed.rebuild.canvas.image.${P}`, JSON.stringify({nodes: [{id: 'm5-node-a', t: 'text_input', x: 120, y: 120, title: '开场（模拟）'}], edges: []})); };
const tid = (page, id) => page.getByTestId(id);
async function check(cond, msg) { if (!cond) throw new Error(msg); }
const scenarios = {
  async loop({page, backend}, vp) {
    await page.locator('[data-node-id="m5-node-a"]').first().click(); await page.locator('[data-node-id="m5-node-a"]').first().click();
    await page.getByRole('button', {name: /音频任务/}).click();
    await tid(page, 'u3-detail').waitFor(); await shot(page, vp, 'loop-1-detail');
    await tid(page, 'u3-locate').click(); await page.waitForTimeout(300); const m1 = await tid(page, 'u3-nav-msg').innerText().catch(() => '');
    await shot(page, vp, 'loop-2-locate');
    await tid(page, 'u3-exec').click(); await page.waitForTimeout(400); await shot(page, vp, 'loop-3-exec');
    const execVisible = await page.getByTestId('uw-execution-canvas').isVisible().catch(() => false);
    await tid(page, 'u3-back').click(); await page.waitForTimeout(400); await shot(page, vp, 'loop-4-return');
    const back = await tid(page, 'u3-tasks').isVisible();
    await check(back, 'return did not bring tasks back');
    return `locate msg="${m1.slice(0, 60)}"; exec canvas visible=${execVisible}; returned to tasks=${back}`;
  },
  async param({page, backend}, vp) {
    await page.getByRole('button', {name: /图像任务/}).click(); await tid(page, 'u3-detail').waitFor();
    await tid(page, 'u3-params').waitFor({timeout: 8000}); await shot(page, vp, 'param-1-panel');
    backend.arm(`POST /api/projects/${backend.d.P}/studio/production/preview`); // explicit, mock-only preview (no model)
    await tid(page, 'u3-preview').click(); await tid(page, 'u3-params').locator('[data-phase="previewed"]').or(page.locator('[data-testid="u3-params"][data-phase="previewed"]')).first().waitFor({timeout: 8000});
    await shot(page, vp, 'param-2-previewed'); await tid(page, 'u3-ask-create').click(); await tid(page, 'u3-confirm').waitFor({timeout: 5000});
    const ctext = (await tid(page, 'u3-confirm').innerText()).replace(/\s+/g, ' ').slice(0, 200);
    await shot(page, vp, 'param-3-confirm-step'); await tid(page, 'u3-confirm').getByRole('button', {name: '取消'}).click();
    const writes = backend.st.log.filter(l => !l.startsWith('GET'));
    await check(writes.length === 1 && /preview$/.test(writes[0]) && backend.st.blocked.length === 0, `unexpected writes ${JSON.stringify(writes)} blocked=${backend.st.blocked}`);
    await check(!(await tid(page, 'u3-confirm').isVisible().catch(() => false)), 'confirm not dismissed');
    return `MOCK preview ok → confirm step shown and cancelled; no create/execute sent; confirm="${ctext}"`;
  },
  async adopt({page, backend}, vp) {
    await page.getByRole('button', {name: /音频任务/}).click(); await tid(page, 'u3-detail').waitFor();
    await tid(page, 'u4-results').waitFor({timeout: 8000}); await page.waitForTimeout(800); await shot(page, vp, 'adopt-1-results');
    await tid(page, 'u4-read').click(); await tid(page, 'u4-adopt').waitFor({timeout: 8000}); await page.waitForTimeout(500); await shot(page, vp, 'adopt-1b-read');
    await tid(page, 'u4-adopt').click();
    await tid(page, 'u4-adopt-confirm').waitFor(); await shot(page, vp, 'adopt-2-confirm');
    const before = backend.st.canvas.version; backend.arm(`PUT /api/projects/${backend.d.P}/studio/canvas-views/${backend.st.canvas.id}`);
    await tid(page, 'u4-adopt-yes').click(); await page.waitForTimeout(1200); await shot(page, vp, 'adopt-3-done');
    const msg = await tid(page, 'u4-msg').innerText().catch(() => '');
    await check(backend.st.canvas.version === before + 1, `canvas version not advanced (${before}→${backend.st.canvas.version}); msg=${msg}; blocked=${backend.st.blocked}`);
    return `mock canvas v${before}→v${backend.st.canvas.version}; msg="${msg.slice(0, 80)}"`;
  },
  async restore({page, backend}, vp) {
    // precondition: adoption done through the same mock (scenario adopt) — performed here explicitly too
    if (backend.st.canvas.version === 1) await scenarios.adopt({page, backend}, {...vp, pre: true});
    await tid(page, 'u4-history').waitFor({timeout: 8000}); const read = tid(page, 'u4-history-read'); if (await read.isVisible().catch(() => false)) await read.click();
    await page.waitForTimeout(800); await shot(page, vp, 'restore-1-list');
    await tid(page, 'u4-compare-1').click(); await tid(page, 'u4-restore').waitFor({timeout: 8000}); await shot(page, vp, 'restore-1b-impact');
    await tid(page, 'u4-restore').click(); await tid(page, 'u4-restore-confirm').waitFor(); await shot(page, vp, 'restore-2-confirm');
    const before = backend.st.canvas.version; backend.arm(`POST /api/projects/${backend.d.P}/studio/canvas-views/${backend.st.canvas.id}/restore`);
    await tid(page, 'u4-restore-yes').click(); await page.waitForTimeout(1200); await shot(page, vp, 'restore-3-done');
    const msg = await tid(page, 'u4-history-msg').innerText().catch(() => '');
    await check(backend.st.canvas.version === before + 1, `restore did not commit (${before}→${backend.st.canvas.version}); msg=${msg}; blocked=${backend.st.blocked}`);
    return `mock canvas v${before}→v${backend.st.canvas.version} (restored v1 content); msg="${msg.slice(0, 80)}"`;
  },
  async coldReopen(ctx, vp) {
    const {page, context} = ctx;
    await page.getByLabel('分屏方式').selectOption('split-h'); await page.waitForTimeout(800);
    const pressed = async p => String((await p.getByLabel('分屏方式').inputValue()) === 'split-h');
    const b = await pressed(page); await page.close();
    const p2 = await context.newPage(); await p2.goto(`${process.env.M5_BASE || 'http://127.0.0.1:5391'}/?uw=1`); await p2.getByTestId('u3-tasks').waitFor(); await p2.waitForTimeout(1500);
    const a = await pressed(p2); await shot(p2, vp, 'cold-reopen'); ctx.page = p2;
    await check(a === 'true' && b === 'true', `layout not restored after reopen (before=${b} after=${a})`);
    const label = await p2.getByText('布局仅在本次会话有效（无本地存储）').count();
    await check(label === 0, 'stale session-only label shown while layout persisted');
    return `split=左右分屏 before=${b} after reopen=${a}; session-only label count=${label}`;
  },
  async audioFilter({page, backend}, vp) {
    const n0 = backend.st.log.length;
    await tid(page, 'aud-filter-audio').click(); await page.waitForTimeout(500); await shot(page, vp, 'audio-1-filter');
    const t = (await tid(page, 'u3-tasks').innerText()).replace(/\s+/g, ' ');
    const gap = await tid(page, 'aud-filter-gap').isVisible().catch(() => false);
    const extra = backend.st.log.slice(n0);
    await check(/音频任务/.test(t) && !/图像任务/.test(t) && gap && extra.length === 0, `filter wrong: gap=${gap} extra=${JSON.stringify(extra)} text=${t.slice(0, 120)}`);
    await tid(page, 'aud-filter-all').click();
    return `audio filter: only 音频 rows, gap text shown, 0 extra requests`;
  },
  async audioPreview({page, backend}, vp) {
    await page.getByRole('button', {name: /音频任务/}).click(); await tid(page, 'aud-preview').waitFor({timeout: 8000});
    const cand = () => backend.st.log.filter(l => l.endsWith('/candidate')).length;
    const before = cand(); await page.waitForTimeout(800); await shot(page, vp, 'audio-2-detail');
    await check(before === 0, `candidate read on mount (${before})`);
    await tid(page, 'aud-load').click(); await page.waitForTimeout(1500); await shot(page, vp, 'audio-3-preview');
    const player = await tid(page, 'aud-player').count(), paused = player ? await tid(page, 'aud-player').evaluate(a => a.paused) : null;
    const msg = await tid(page, 'aud-msg').innerText().catch(() => '');
    await check(cand() === 1 && backend.st.blocked.length === 0 && (player === 0 || paused === true), `cand=${cand()} player=${player} paused=${paused} msg=${msg}`);
    return `试听候选 click → ${cand()} GET candidate (MOCK wav), player=${player} paused(no autoplay)=${paused}; msg="${msg}"; no non-GET`;
  },
  async identity({page, backend}, vp) { // U1fix MUST-FIX 3: ?uw=1 goes through bootstrap, real identity, no fabricated id
    await tid(page, 'uw-open-views').click(); await tid(page, 'uw-views').waitFor(); await shot(page, vp, 'u1-identity');
    const mode = await tid(page, 'uw-views-mode').getAttribute('data-mode'); const boots = backend.st.log.filter(l => l.includes('/bootstrap')).length;
    const body = await page.locator('body').innerText();
    await check(mode === 'persistent' && boots >= 1 && !body.includes('u-m5'), `mode=${mode} bootstraps=${boots} rawIdOnScreen=${body.includes('u-m5')}`);
    return `views mode=${mode}; bootstrap GETs=${boots}; raw actor id on screen=false`;
  },
  async worksetPan({page}, vp) { // U1fix MUST-FIX 1: save workset, then pan canvas — neither write loses the other
    await tid(page, 'uw-open-views').click(); await tid(page, 'uw-views').waitFor();
    await tid(page, 'uw-views').locator('input').first().fill('M5视图'); await tid(page, 'uw-views').locator('button[type=submit]').first().click();
    await page.waitForTimeout(500); const msg = await tid(page, 'uw-views-msg').innerText().catch(() => ''); await shot(page, vp, 'u1-workset-saved');
    await tid(page, 'uw-views').getByRole('button', {name: '关闭'}).last().click();
    const box = await page.locator('[data-node-id]').first().boundingBox();
    const sx = box.x + box.width + 120, sy = box.y + box.height + 60;
    await page.mouse.move(sx, sy); await page.mouse.down(); await page.mouse.move(sx + 90, sy + 40, {steps: 8}); await page.mouse.up(); await page.waitForTimeout(1200);
    const doc = await page.evaluate(() => { const k = Object.keys(localStorage).find(x => x.startsWith('poemseed.workspace.viewprefs.')); return k ? localStorage.getItem(k) : null; });
    await page.reload(); await tid(page, 'u3-tasks').waitFor(); await page.waitForTimeout(1500);
    await tid(page, 'uw-open-views').click(); await tid(page, 'uw-views').waitFor(); await shot(page, vp, 'u1-workset-after-reload');
    const listed = await tid(page, 'uw-views').getByText('M5视图').count();
    const d = doc ? JSON.parse(doc) : {}; const hasVp = !!(d.viewports && Object.keys(d.viewports).length);
    await check(/已保存视图「M5视图」。$/.test(msg) && listed > 0 && (d.worksets || []).length === 1, `msg=${msg} listed=${listed} doc=${(doc || '').slice(0, 160)}`);
    return `msg="${msg}"; after pan+reload workset listed=${listed}; stored worksets=${(d.worksets || []).length}; stored viewport present=${hasVp}`;
  },
  async sessionSave({page}, vp) { // U1fix MUST-FIX 2: no session token → honest session-only save message
    await tid(page, 'uw-open-views').click(); await tid(page, 'uw-views').waitFor();
    const mode = await tid(page, 'uw-views-mode').innerText();
    await tid(page, 'uw-views').locator('input').first().fill('临时'); await tid(page, 'uw-views').locator('button[type=submit]').first().click();
    await page.waitForTimeout(500); const msg = await tid(page, 'uw-views-msg').innerText().catch(() => ''); await shot(page, vp, 'u1-session-save');
    await check(/仅本次会话有效/.test(msg) && !/项目已经切换/.test(msg), `msg=${msg}`);
    return `mode="${mode}"; msg="${msg}"`;
  },
  async axe({page}, vp) { // Vera P2: landmark-unique on #uw-panel-tasks; axe-core from local copy (no network)
    await page.waitForTimeout(800); await page.addScriptTag({path: process.env.M5_AXE || '/tmp/vera-vw-axe/node_modules/axe-core/axe.min.js'});
    const v = await page.evaluate(async () => (await window.axe.run(document.querySelector('[data-testid=dock-layout]'), {resultTypes: ['violations']})).violations.map(x => x.id + ':' + x.nodes.map(n => n.target.join(' ')).join('|')));
    await check(!v.some(x => x.startsWith('landmark-unique')), `axe: ${JSON.stringify(v)}`);
    return `axe violations (color-contrast is pre-existing): ${JSON.stringify(v.map(x => x.split(':')[0]))}`;
  },
  async aba({page, backend}, vp) {
    const reads = () => backend.st.log.filter(l => l.includes('/experimental/workspace/tasks')).length;
    const r0 = reads();
    await page.getByLabel('选择作品').selectOption({label: (await page.getByLabel('选择作品').locator('option', {hasText: '演示 B'}).first().innerText())}); await page.waitForTimeout(1200); await shot(page, vp, 'aba-1-B');
    const tB = (await tid(page, 'u3-tasks').innerText()).replace(/\s+/g, ' ');
    await page.getByLabel('选择作品').selectOption({label: (await page.getByLabel('选择作品').locator('option', {hasText: '演示 A'}).first().innerText())}); await page.waitForTimeout(1500); await shot(page, vp, 'aba-2-A');
    const tA = (await tid(page, 'u3-tasks').innerText()).replace(/\s+/g, ' ');
    await check(!/音频任务|图像任务/.test(tB), `B shows A's tasks: ${tB}`); await check(/音频任务/.test(tA), `A tasks not back: ${tA}`);
    return `B="${tB.slice(0, 70)}"; A again has tasks; task reads ${r0}→${reads()}`;
  },
  async corruption({page}, vp) {
    // write real scoped keys first (explicit layout change), then corrupt every workspace key + canvas draft, reload
    await page.getByLabel('分屏方式').selectOption('split-h'); await page.waitForTimeout(800);
    const keys = await page.evaluate(() => { const ks = Object.keys(localStorage).filter(k => k.startsWith('poemseed.workspace.') || k.startsWith('poemseed.rebuild.canvas.'));
      for (const k of ks) localStorage.setItem(k, '{bad json'); return ks; });
    await page.reload(); await tid(page, 'u3-tasks').waitFor(); await page.waitForTimeout(1500); await shot(page, vp, 'corrupt');
    const ok = await tid(page, 'dock-layout').isVisible(); await check(ok && keys.length > 0, `layout not rendered or no keys corrupted (${keys.length})`);
    return `corrupted ${keys.length} real keys (${keys.map(k => k.split('::')[0]).join(', ')}) → reload renders defaults, no page error`;
  },
  async revoked({page, backend}, vp) {
    backend.st.mode = 'revoked'; await tid(page, 'u3-refresh').click(); await page.waitForTimeout(1200); await shot(page, vp, 'revoked');
    const s = await tid(page, 'u3-tasks').locator('[data-state]').first().getAttribute('data-state'); const t = (await tid(page, 'u3-tasks').innerText()).replace(/\s+/g, ' ');
    await check(!/音频任务/.test(t), `revoked still lists tasks: ${t}`); return `state=${s}; text="${t.slice(0, 90)}"`;
  },
  async unknown({page, backend}, vp) {
    backend.st.mode = 'unknown'; await tid(page, 'u3-refresh').click(); await page.waitForTimeout(1200); await shot(page, vp, 'unknown');
    const s = await tid(page, 'u3-tasks').locator('[data-state]').first().getAttribute('data-state'); const t = (await tid(page, 'u3-tasks').innerText()).replace(/\s+/g, ' ');
    return `state=${s}; text="${t.slice(0, 90)}"`;
  },
  async projectGone({page, backend}, vp) { // [HERMIA-FE-20261025 M10-purgefix] in-session purge, real keys, asserted (was vacuous: matched '::project::' only)
    const P = backend.d.P, inst = encodeURIComponent('ws1/s1/b1');
    const own = [`poemseed.workspace.viewprefs.v1::u-m5::${encodeURIComponent(P)}::${inst}`, `poemseed.workspace.layout.v1::u-m5::${encodeURIComponent(P)}::${inst}`];
    const other = [`poemseed.workspace.viewprefs.v1::u-other::${encodeURIComponent(P)}::${inst}`, `poemseed.workspace.layout.v1::u-other::${encodeURIComponent(P)}::${inst}`];
    await page.evaluate(ks => { for (const k of ks) if (localStorage.getItem(k) === null) localStorage.setItem(k, '{"version":1,"viewports":{},"worksets":[]}'); }, [...own, ...other]);
    backend.st.mode = 'gone'; // list now omits P; refetch WITHOUT reload (cold start is the documented gap G-PURGE-1)
    await refetch(page); // [HERMIA-FE-20261025 M10-purgeguard] first missing list = pending only
    const pend = await page.evaluate(ks => ks.filter(k => localStorage.getItem(k) !== null).length, own);
    await check(pend === 2, `purged after ONE list (must need two): ${pend}/2 kept`);
    await refetch(page); // second consecutive successful list missing P → purge
    await page.waitForFunction(ks => ks.every(k => localStorage.getItem(k) === null), own, {timeout: 15000}).catch(() => {});
    await page.waitForTimeout(500); await shot(page, vp, 'project-gone');
    const st = await page.evaluate(([o, x]) => ({own: o.filter(k => localStorage.getItem(k) !== null), other: x.filter(k => localStorage.getItem(k) !== null).length}), [own, other]);
    await check(st.own.length === 0, `own keys not purged: ${JSON.stringify(st.own)}`);
    await check(st.other === 2, `other user's keys removed: ${st.other}/2 kept`);
    return `after 1st missing list own kept 2/2 (pending); after 2nd: own ${st.own.length} (purged), other user's kept ${st.other}/2`;
  },
  async emptyList({page, backend}, vp) { // [HERMIA-FE-20261025 M10-purgeguard] Vera repro: [all] → [all−P] → 200 [] must not wipe own keys
    const inst = encodeURIComponent('ws1/s1/b1'), ids = backend.d.novels.map(n => n.id);
    const own = ids.flatMap(id => ['viewprefs', 'layout'].map(t => `poemseed.workspace.${t}.v1::u-m5::${encodeURIComponent(id)}::${inst}`));
    await page.evaluate(ks => { for (const k of ks) if (localStorage.getItem(k) === null) localStorage.setItem(k, '{"version":1,"viewports":{},"worksets":[]}'); }, own);
    backend.st.mode = 'gone'; await refetch(page);
    backend.st.mode = 'empty'; await refetch(page); await refetch(page);
    await shot(page, vp, 'empty-list');
    const kept = await page.evaluate(ks => ks.filter(k => localStorage.getItem(k) !== null).length, own);
    const nv = backend.st.log.filter(l => l.includes('/api/novels')).length;
    await check(kept === own.length, `200 [] wiped own keys: ${kept}/${own.length} kept`);
    return `projects ${ids.length}; after [all−P] → 200 [] ×2: own keys kept ${kept}/${own.length}; /api/novels requests ${nv}`;
  },

};
async function refetch(page) { await page.evaluate(() => { window.dispatchEvent(new Event('visibilitychange')); window.dispatchEvent(new Event('focus')); }); await page.waitForTimeout(1500); }
async function shot(page, vp, name) { if (!vp.pre) await page.screenshot({path: `${SHOTS}/${vp.width}x${vp.height}-${name}.png`}); }
const CORRUPT = () => { for (const k of ['poemseed.workspace.viewprefs.v1::user::project::x', 'poemseed.workspace.layout.v1::user::project::x']) localStorage.setItem(k, '{bad json'); localStorage.setItem('poemseed.rebuild.canvas.image.audio-wav-project', '[[['); };
const browser = await chromium.launch({executablePath: '/usr/bin/google-chrome', headless: true});
writeFileSync(LOG, `# M5 run ${new Date().toISOString()} HEAD=${process.env.M5_HEAD || '?'}\n`);
for (const vp of VIEWPORTS) for (const name of Object.keys(scenarios)) {
  if (ONLY && !ONLY.includes(name)) continue;
  const backend = createBackend(); const context = await browser.newContext({viewport: vp});
  const storage = name === 'corruption' ? CORRUPT : {content: `(${seedCanvas})(${JSON.stringify(backend.d.P)})`};
  const ctx = await open({browser, context, backend, viewport: vp, storage, session: name !== 'sessionSave'});
  let status = 'PASS', detail = '';
  try { await ctx.page.getByTestId('u3-tasks').waitFor({timeout: 30000}); await ctx.page.waitForTimeout(1200); detail = await scenarios[name](ctx, vp); }
  catch (e) { status = 'FAIL'; detail = String(e.message).split('\n')[0]; try { await shot(ctx.page, vp, `${name}-FAIL`); } catch {} }
  const unarmed = backend.st.blocked; const errs = ctx.consoleLog.filter(l => l.startsWith('pageerror'));
  const row = {viewport: `${vp.width}x${vp.height}`, scenario: name, status, detail, blockedWrites: unarmed, pageErrors: errs, requests: backend.st.log.length};
  results.push(row); log(`${row.viewport} ${name} ${status} :: ${detail} :: blocked=${JSON.stringify(unarmed)} pageerrors=${errs.length}`);
  writeFileSync(`/workspace/hr/m10/logs/m5-req-${row.viewport}-${name}.log`, backend.st.log.join('\n') + '\n# console\n' + ctx.consoleLog.join('\n'));
  await context.close();
}
writeFileSync('/workspace/hr/m10/logs/m5-results.json', JSON.stringify(results, null, 1));
await browser.close();
