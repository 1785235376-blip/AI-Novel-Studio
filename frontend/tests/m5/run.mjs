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
  async projectGone({page, backend}, vp) {
    backend.st.mode = 'gone'; await page.reload(); await page.waitForTimeout(2500); await shot(page, vp, 'project-gone');
    const keys = await page.evaluate(P => Object.keys(localStorage).filter(k => k.includes(`::project::`) && k.includes(P)), backend.d.P);
    return `own keys for vanished project after list refresh: ${JSON.stringify(keys)}`;
  },
};
async function shot(page, vp, name) { if (!vp.pre) await page.screenshot({path: `${SHOTS}/${vp.width}x${vp.height}-${name}.png`}); }
const CORRUPT = () => { for (const k of ['poemseed.workspace.viewprefs.v1::user::project::x', 'poemseed.workspace.layout.v1::user::project::x']) localStorage.setItem(k, '{bad json'); localStorage.setItem('poemseed.rebuild.canvas.image.audio-wav-project', '[[['); };
const browser = await chromium.launch({executablePath: '/usr/bin/google-chrome', headless: true});
writeFileSync(LOG, `# M5 run ${new Date().toISOString()} HEAD=${process.env.M5_HEAD || '?'}\n`);
for (const vp of VIEWPORTS) for (const name of Object.keys(scenarios)) {
  if (ONLY && !ONLY.includes(name)) continue;
  const backend = createBackend(); const context = await browser.newContext({viewport: vp});
  const storage = name === 'corruption' ? CORRUPT : {content: `(${seedCanvas})(${JSON.stringify(backend.d.P)})`};
  const ctx = await open({browser, context, backend, viewport: vp, storage});
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
