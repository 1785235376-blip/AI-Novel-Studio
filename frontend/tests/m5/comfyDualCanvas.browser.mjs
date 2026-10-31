import {createRequire} from 'node:module';
import fs from 'node:fs';
const req = createRequire(import.meta.url);
const {chromium} = req('playwright-core');
const {createBackend} = await import(new URL('./mockBackend.mjs', import.meta.url));
const BASE = process.env.BASE || 'http://127.0.0.1:4745/';
const PHASE = process.env.PHASE || 'after';
const SHOTS = process.env.SHOTS; if (SHOTS) fs.mkdirSync(SHOTS, {recursive: true});
const AXE = process.env.AXE ? fs.readFileSync(process.env.AXE, 'utf8') : null;
const WS = (process.env.WS || '1366,1024').split(',').map(Number);
const b = await chromium.launch({executablePath: process.env.CHROME || '/usr/bin/google-chrome'});
const ch = P => [{id: 'ch-001', novel_id: P, number: 1, title: '第一章', content: '<p>雾</p>', document: {type: 'doc', content: [{type: 'paragraph', content: [{type: 'text', text: '雾从港口漫上来。'}]}]}, version: 3, word_count: 8, status: 'draft'}];
const plays = [{id: 'sp1', shot_status: 'DRAFT', shots: [{id: 'x1', shot_size: '近景', description: '雾港码头'}, {id: 'x2', shot_size: '远景', description: '灯塔'}, {id: 'x3', shot_size: '特写', description: '煤油灯'}]}];
async function session(theme) {
  const be = createBackend(), P = be.d.P;
  const lower = new Map(); // [WIRING] fake project lower-canvas rows (mock only)
  const imported = {M5ImportedNode: {input: {required: {}}, output: ['IMAGE'], category: 'custom', display_name: 'M5 Imported Node'}};
  const ctx = await b.newContext({viewport: {width: 1366, height: 800}});
  await ctx.route('**/*', async rt => {
    const q = rt.request(), u = new URL(q.url());
    const lowerMatch = u.pathname.match(/\/studio\/lower-canvas\/(image|video)$/);
    // [WIRING] the lower-canvas draft API is the one permitted write; everything else stays blocked.
    if (q.method() === 'PUT' && lowerMatch) {
      lowerWrites++;
      const kind = lowerMatch[1];
      const body = JSON.parse(q.postData() || '{}');
      const version = (lower.get(kind)?.version || 0) + 1;
      lower.set(kind, {version, graph: body.graph});
      return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify({kind, version, graph: body.graph})});
    }
    if (!['GET', 'HEAD'].includes(q.method())) { nonGet++; return rt.abort(); } // [P3] counted; must stay 0
    if (!u.pathname.startsWith('/api/')) return rt.continue();
    if (u.pathname === '/api/comfy/object_info') return rt.fulfill({status: 200, contentType: 'application/json',
      headers: {'X-Comfy-Source-Version': 'm5-mock-source'},
      body: JSON.stringify(imported)});
    if (lowerMatch) { const kind = lowerMatch[1];
      return rt.fulfill({status: 200, contentType: 'application/json',
        body: JSON.stringify({kind, version: lower.get(kind)?.version || 0, graph: lower.get(kind)?.graph || {nodes: [], edges: []}})}); }
    if (/\/chapters$/.test(u.pathname)) return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(ch(P))});
    if (/^\/api\/chapters\/ch-001$/.test(u.pathname)) return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(ch(P)[0])});
    if (/screenplays/.test(u.pathname)) return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(plays)});
    const [s, j] = be.handle('GET', q.url(), null);
    if (j && j.__bytes) return rt.fulfill({status: s, contentType: j.type, body: j.__bytes});
    return rt.fulfill({status: s, contentType: 'application/json', body: JSON.stringify(j)});
  });
  await ctx.addInitScript(([th]) => { if (!sessionStorage.getItem('td-init')) { sessionStorage.setItem('td-init', '1');
    localStorage.setItem('studio.session', 'tok-v'); localStorage.setItem('studio.scope', JSON.stringify({workspaceId: 'ws1', projectId: 'audio-wav-project', storylineId: 's1', branchId: 'b1'}));
    localStorage.setItem('studio.locale', 'zh-CN'); localStorage.setItem('studio-theme', th); } }, [theme]);
  const p = await ctx.newPage(); const errs = []; p.on('pageerror', e => errs.push(String(e).slice(0, 160)));
  await p.goto(BASE); await p.waitForFunction(() => !document.body.innerText.includes('正在加载…'), null, {timeout: 60000}).catch(() => {});
  await p.waitForTimeout(1500);
  return {ctx, p, errs, lower};
}
const skipGate = async p => { const l = p.getByRole('button', {name: '跳过，直接进入小说写作', exact: true}).first(); if (await l.count()) { await l.click().catch(() => {}); await p.waitForTimeout(500); } };

// [HERMIA-FE-20261031 DUALCANVAS-COMFY] Real-browser: lower ComfyUI-style canvas + splitter/max/swap, 1024/1440/1920 × light/dark, pro mode.
// MOCK: node-library import + lower-canvas draft PUT are fake; every other non-GET is aborted. Never calls a model or ComfyUI.
// C1 lower menu has >40 node types in >=8 groups; C2 MODEL link ok, CLIP→MODEL refused; C3 swap puts lower above, semantics kept;
// C4 maximize hides upper, restore shows both; C5 splitter keyboard moves aria-valuenow; T1 light: lower canvas bg not dark; dark: dark.
const lum = `(c => { const m = c.match(/rgba?\\(([^)]+)\\)/); if (!m) return null; const [r, g, bb] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
  const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bb); })`;
const fails = [], rows = []; let nonGet = 0; let lowerWrites = 0;
const AXE_FILE = process.env.AXE || '/workspace/hr/ux-20261030/axe/node_modules/axe-core/axe.min.js';
for (const theme of (process.env.THEMES || 'light,dark').split(',')) {
  const {ctx, p, errs, lower} = await session(theme); await skipGate(p);
  for (let i = 0; i < 3; i++) { const t = p.getByRole('button', {name: '跳过', exact: true}); if (await t.count()) { await t.first().click().catch(() => {}); await p.waitForTimeout(300); } }
  await p.getByRole('button', {name: '专业', exact: true}).first().click().catch(() => {}); await p.waitForTimeout(500);
  for (const mod of (process.env.MODS || 'VIDEO,IMAGE').split(',')) {
    await p.setViewportSize({width: 1440, height: 900});
    await p.locator(`[data-module-tab="${mod}"]`).click().catch(() => {}); await p.waitForTimeout(700); await skipGate(p);
    if (mod === 'IMAGE') { await p.locator('.nv-tabs__tab[data-view="dual"]').first().click().catch(() => {}); }
    else { const d = p.locator('[data-open-dual]'); if (await d.count()) await d.first().click(); }
    await p.waitForTimeout(700);
    const LO = '[data-canvas-layer="lower"]', v = [];
    if (!(await p.locator(LO).count())) { if (SHOTS) await p.screenshot({path: `${SHOTS}/FAIL-${theme}-${mod}.png`}); fails.push(`${theme}|${mod} no lower canvas: tabs=` + (await p.locator('[data-module-tab]').count()) + ' toggle=' + (await p.locator('.shell-mode-toggle button').count()) + ' dualBtn=' + (await p.locator('[data-open-dual]').count())); continue; }
    const app = p.locator(`${LO} [role=application]`);
    const addNode = async (t, dx) => { const bb = await app.boundingBox(); await p.mouse.click(bb.x + dx, bb.y + 70, {button: 'right'}); await p.waitForTimeout(150);
      await p.locator(`${LO} [data-add-node-menu] [data-node-type="${t}"]`).click(); await p.waitForTimeout(150); };
    // C1 menu
    { await p.locator(`${LO} [data-comfy-add]`).click(); await p.waitForTimeout(200);
      const n = await p.locator(`${LO} [data-add-node-menu] [data-node-type]`).count(); const g = await p.locator(`${LO} [data-add-node-menu] .grp--h`).count();
      const importedCount = await p.locator(`${LO} [data-add-node-menu] [data-node-type="M5ImportedNode"]`).count();
      if (n < 40 || g < 8) v.push(`C1 menu n=${n} groups=${g}`);
      if (!importedCount) v.push('C1 imported object_info node missing');
      rows.push({key: `${theme}|${mod}|menu`, n, g, importedCount});
      if (SHOTS) await p.screenshot({path: `${SHOTS}/${theme}-${mod}-menu-1440.png`});
      // [P2-2] A1 axe on the open add-node menu: 0 violations of any impact
      await p.addScriptTag({content: fs.readFileSync(AXE_FILE, 'utf8')});
      const ax = await p.evaluate(async sel => (await axe.run(document.querySelector(sel), {resultTypes: ['violations']})).violations.map(x => `${x.id}(${x.impact}):${x.nodes.length}`), `${LO} [data-add-node-menu]`);
      rows.push({key: `${theme}|${mod}|axe-menu`, violations: ax}); if (ax.length) v.push('A1 axe ' + ax.join(','));
      await p.keyboard.press('Escape'); await p.waitForTimeout(100);
      if (await p.locator(`${LO} [data-add-node-menu]`).count()) v.push('K0 Esc did not close menu');
      // [VERA-3 P2] F0 focus returns to「＋ 节点」after Esc
      if (!(await p.evaluate(() => document.activeElement?.hasAttribute('data-comfy-add') ?? false))) v.push('F0 focus not on add button after Esc');
      // [VERA-3 P3 K4/K6] multi-result filter: ↓↓↑ ends on option[1]; changing the filter resets to option[0]
      await p.locator(`${LO} [data-comfy-add]`).click(); await p.waitForTimeout(150);
      { const cb2 = p.locator(`${LO} [data-add-node-menu] [role=combobox]`); await cb2.fill('vae'); await p.waitForTimeout(50);
        const oid = async i => p.locator(`${LO} [data-add-node-menu] [role=option]`).nth(i).getAttribute('id');
        const nOpt = await p.locator(`${LO} [data-add-node-menu] [role=option]`).count();
        await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowUp');
        const a1 = await cb2.getAttribute('aria-activedescendant'), o0 = await oid(0), o1 = await oid(1);
        if (nOpt < 3 || a1 !== o1 || a1 === o0) v.push(`K4 vae n=${nOpt} act=${a1} o1=${o1}`);
        await cb2.fill('va'); await p.waitForTimeout(50); const a2 = await cb2.getAttribute('aria-activedescendant'), f0 = await oid(0);
        if (a2 !== f0) v.push(`K6 reset act=${a2} first=${f0}`);
        rows.push({key: `${theme}|${mod}|k4k6`, nOpt, a1, o1, a2, f0});
        await p.keyboard.press('Escape'); await p.waitForTimeout(100); }
      // [P2-2] K1 keyboard: open, type, ArrowDown/ArrowUp, Enter adds the active option
      await p.locator(`${LO} [data-comfy-add]`).click(); await p.waitForTimeout(150);
      const cb = p.locator(`${LO} [data-add-node-menu] [role=combobox]`);
      if (!(await cb.count())) v.push('K1 no combobox'); else {
        await cb.fill('ksampler'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowUp');
        const act = await cb.getAttribute('aria-activedescendant'); const actType = act ? await p.locator(`[id="${act}"]`).getAttribute('data-node-type') : null;
        const before = await p.locator(`${LO} [data-node-class]`).count(); await p.keyboard.press('Enter'); await p.waitForTimeout(150);
        const after = await p.locator(`${LO} [data-node-class]`).count();
        if (actType !== 'KSampler' || after !== before + 1 || await p.locator(`${LO} [data-add-node-menu]`).count()) v.push(`K1 kbd act=${actType} ${before}->${after}`);
        rows.push({key: `${theme}|${mod}|kbd`, actType, before, after});
        // [VERA-3 P2] F1 focus returns to「＋ 节点」after Enter adds
        if (!(await p.evaluate(() => document.activeElement?.hasAttribute('data-comfy-add') ?? false))) v.push('F1 focus not on add button after Enter');
      }
      await p.keyboard.press('Escape'); }
    await addNode('CheckpointLoaderSimple', 200); await addNode('KSampler', 600);
    // [PARAMS] selected KSampler exposes editable widgets; edited values must reach the draft PUT.
    { const seed = p.locator(`${LO} [data-comfy-params] [data-widget-name="seed"]`);
      if (await seed.count()) { await seed.fill('77'); await p.waitForTimeout(900);
        const samplers = lower.get(mod.toLowerCase())?.graph?.nodes?.filter(n => n.t === 'KSampler') ?? [];
        const ok = samplers.some(n => n.params?.seed === 77);
        rows.push({key: `${theme}|${mod}|params`, seeds: samplers.map(n => n.params?.seed)});
        if (!ok) v.push(`P params seed not persisted: ${JSON.stringify(samplers.map(n => n.params))}`);
      } else v.push('P params inspector missing for KSampler'); }
    const idOf = c => p.locator(`${LO} [data-node-class="${c}"]`).first().getAttribute('data-node-id');
    const ids = [await idOf('CheckpointLoaderSimple'), await idOf('KSampler')].filter(Boolean);
    const drag = async (a, bsel) => { const s = await p.locator(`${LO} [data-out="${a}"]`).boundingBox(), t = await p.locator(`${LO} [data-in="${bsel}"]`).boundingBox();
      if (process.env.DBG) console.log('DBG', JSON.stringify(s), JSON.stringify(t), await p.evaluate(([x, y, x2, y2]) => [document.elementFromPoint(x, y)?.outerHTML.slice(0, 90).replace(/\n/g, ' '), document.elementFromPoint(x2, y2)?.outerHTML.slice(0, 90).replace(/\n/g, ' ')], [s.x + s.width / 2, s.y + s.height / 2, t.x + t.width / 2, t.y + t.height / 2]));
      await p.mouse.move(s.x + s.width / 2, s.y + s.height / 2); await p.mouse.down(); await p.mouse.move(t.x + t.width / 2, t.y + t.height / 2, {steps: 6}); await p.mouse.up(); await p.waitForTimeout(150); };
    const edges = () => p.locator(`${LO} .cfy-edge`).count();
    // [P3] H1 the transparent rect.hit row is the drop target: a point at 80% of its width (far from the port dot) resolves to the same input port, and dropping there links
    const dragHit = async (a, bsel) => { const s = await p.locator(`${LO} [data-out="${a}"]`).boundingBox(), hb = await p.locator(`${LO} [data-in="${bsel}"] rect.hit`).boundingBox();
      const tx = hb.x + hb.width * 0.8, ty = hb.y + hb.height / 2;
      const hit = await p.evaluate(([x, y, k]) => { const e = document.elementFromPoint(x, y); return {hit: !!e && e.matches('rect.hit'), port: e?.closest('[data-in]')?.getAttribute('data-in') === k}; }, [tx, ty, bsel]);
      await p.mouse.move(s.x + s.width / 2, s.y + s.height / 2); await p.mouse.down(); await p.mouse.move(tx, ty, {steps: 6}); await p.mouse.up(); await p.waitForTimeout(150); return hit; };
    if (ids.length >= 2) { await drag(`${ids[0]}:1`, `${ids[1]}:0`); const e0 = await edges(); const h = await dragHit(`${ids[0]}:0`, `${ids[1]}:0`); const e1 = await edges();
      if (!h.hit || !h.port) v.push('H1 rect.hit not the drop target ' + JSON.stringify(h)); rows.push({key: `${theme}|${mod}|hit`, ...h});
      if (e0 !== 0 || e1 !== 1) { v.push(`C2 edges ${e0}->${e1} ids=${ids} st=${await p.locator(`${LO} [data-comfy-status]`).textContent()}`); if (SHOTS) await p.screenshot({path: `${SHOTS}/FAIL-${theme}-${mod}-link.png`}); } rows.push({key: `${theme}|${mod}|link`, e0, e1}); } else v.push('C2 nodes not added ' + ids.length);
    for (const w of [1024, 1440, 1920]) {
      await p.setViewportSize({width: w, height: 900}); await p.waitForTimeout(250);
      const bg = await p.evaluate(`(${lum})(getComputedStyle(document.querySelector('${LO} [role=application]').closest('.cfy, .rcv') || document.querySelector('${LO}')).backgroundColor)`);
      if (theme === 'light' && bg != null && bg < 0.5) v.push(`T1 ${w} lower dark ${bg}`); if (theme === 'dark' && bg != null && bg > 0.2) v.push(`T1 ${w} lower light ${bg}`);
      rows.push({key: `${theme}|${mod}|${w}`, bg}); if (SHOTS) await p.screenshot({path: `${SHOTS}/${theme}-${mod}-dual-${w}.png`});
    }
    await p.setViewportSize({width: 1440, height: 900});
    // C5 splitter
    const sp = p.locator('[data-dual-splitter]'); const a0 = await sp.getAttribute('aria-valuenow'); await sp.focus(); await p.keyboard.press('ArrowDown'); await p.keyboard.press('ArrowDown');
    const a1 = await sp.getAttribute('aria-valuenow'); if (!(Number(a1) > Number(a0))) v.push(`C5 splitter ${a0}->${a1}`); rows.push({key: `${theme}|${mod}|split`, a0, a1});
    // C3 swap
    await p.locator('[data-pane-swap]').first().click(); await p.waitForTimeout(250);
    const pos = await p.evaluate(() => Object.fromEntries([...document.querySelectorAll('[data-canvas-layer]')].map(e => [e.getAttribute('data-canvas-layer'), Math.round(e.getBoundingClientRect().top)])));
    const lowStill = await p.locator(`${LO} [data-comfy-status]`).count();
    if (!(pos.lower < pos.upper) || lowStill !== 1) v.push('C3 swap ' + JSON.stringify(pos)); if (SHOTS) await p.screenshot({path: `${SHOTS}/${theme}-${mod}-swapped-1440.png`});
    await p.locator('[data-pane-swap]').first().click(); await p.waitForTimeout(150);
    // C4 max
    await p.locator('[data-pane-max="lower"]').first().click(); await p.waitForTimeout(250);
    const upVis = await p.locator('[data-canvas-layer="upper"]').isVisible(); if (upVis) v.push('C4 upper visible while lower maximized');
    if (SHOTS) await p.screenshot({path: `${SHOTS}/${theme}-${mod}-lowerMax-1440.png`});
    await p.locator('[data-pane-max="lower"]').first().click(); await p.waitForTimeout(150);
    if (!(await p.locator('[data-canvas-layer="upper"]').isVisible())) v.push('C4 restore failed');
    const chip = await p.locator('[data-layout-identity]').first().textContent(); rows.push({key: `${theme}|${mod}|identity`, chip});
    if (v.length) fails.push(`${theme}|${mod} :: ` + v.join('; '));
  }
  if (errs.length) fails.push(`${theme} pageerror: ${errs.slice(0, 3).join(' | ')}`);
  await ctx.close();
}
await b.close();
rows.push({key: 'nonGET', nonGet, lowerWrites}); if (nonGet !== 0) fails.push(`N1 non-GET requests attempted: ${nonGet}`); if (lowerWrites < 1) fails.push('N2 lower-canvas draft was never persisted');
if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify({rows, fails}, null, 1));
console.log(JSON.stringify(rows)); console.log(`rows=${rows.length} fails=${fails.length}`); for (const f of fails) console.log(' ✗ ' + f);
process.exit(fails.length ? 1 : 0);
