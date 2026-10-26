// [HERMIA-FE-20261026 THEME-DUAL] Real-browser check: canvas / edit desk follow the theme; IMAGE/VIDEO dual canvas (upper/lower).
// Read-only MOCK in-page: every non-GET is aborted; /api GETs answered by tests/m5/mockBackend.mjs. Never calls a model or real backend.
// Usage: BASE=http://127.0.0.1:4752/ SHOTS=dir PHASE=after AXE=axe.min.js OUT=x.json node tests/m5/themeDualCanvas.browser.mjs
// Assertions:
//  T1 light theme: no large dark surface (bg luminance < .25, area > 2500px²) inside main, incl. svg node boxes; dark theme: canvas stays dark (lum < .1)
//  D1 (PHASE=after, pro) IMAGE/VIDEO dual view renders upper + lower canvases stacked vertically (upper above lower), each with own role=application
//  D2 (PHASE=after) upper canvas adds a node while lower is empty; lower node count unchanged
//  X  axe serious/critical = 0
import {createRequire} from 'node:module';
import fs from 'node:fs';
const req = createRequire(import.meta.url);
const {chromium} = req('playwright-core');
const {createBackend} = await import(new URL('./mockBackend.mjs', import.meta.url));
const BASE = process.env.BASE || 'http://127.0.0.1:4752/';
const PHASE = process.env.PHASE || 'after';
const SHOTS = process.env.SHOTS; if (SHOTS) fs.mkdirSync(SHOTS, {recursive: true});
const AXE = process.env.AXE ? fs.readFileSync(process.env.AXE, 'utf8') : null;
const WS = (process.env.WS || '1366,1024').split(',').map(Number);
const b = await chromium.launch({executablePath: process.env.CHROME || '/usr/bin/google-chrome'});
const ch = P => [{id: 'ch-001', novel_id: P, number: 1, title: '第一章', content: '<p>雾</p>', document: {type: 'doc', content: [{type: 'paragraph', content: [{type: 'text', text: '雾从港口漫上来。'}]}]}, version: 3, word_count: 8, status: 'draft'}];
const plays = [{id: 'sp1', shot_status: 'DRAFT', shots: [{id: 'x1', shot_size: '近景', description: '雾港码头'}, {id: 'x2', shot_size: '远景', description: '灯塔'}, {id: 'x3', shot_size: '特写', description: '煤油灯'}]}];
async function session(theme) {
  const be = createBackend(), P = be.d.P;
  const ctx = await b.newContext({viewport: {width: 1366, height: 800}});
  await ctx.route('**/*', async rt => {
    const q = rt.request(), u = new URL(q.url());
    if (!['GET', 'HEAD'].includes(q.method())) return rt.abort();
    if (!u.pathname.startsWith('/api/')) return rt.continue();
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
  return {ctx, p, errs};
}
const skipGate = async p => { const l = p.getByRole('button', {name: '跳过，直接进入小说写作', exact: true}).first(); if (await l.count()) { await l.click().catch(() => {}); await p.waitForTimeout(500); } };
const probe = (p, theme) => p.evaluate(theme => {
  const lum = c => { const m = c.match(/rgba?\(([^)]+)\)/); if (!m) return null; const [r, g, bb, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number); if (a < 0.5) return null;
    const f = v => { v /= 255; return v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4; }; return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(bb); };
  const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none'; };
  const main = document.querySelector('main') || document.body; const dark = [];
  for (const e of main.querySelectorAll('*')) {
    if (!vis(e) || e.closest('img,video,button,.clip,.comic-cell,.cm-thumb,.bub')) continue;
    const r = e.getBoundingClientRect(); if (r.width * r.height < 2500) continue;
    const cs = getComputedStyle(e); const bg = e instanceof SVGElement ? (e.tagName === 'rect' ? cs.fill : null) : cs.backgroundColor;
    const L = bg ? lum(bg) : null; const img = !(e instanceof SVGElement) && cs.backgroundImage !== 'none' && /gradient/.test(cs.backgroundImage) && !/radial-gradient\(rgb/.test(cs.backgroundImage);
    const gradDark = img && (() => { const cols = cs.backgroundImage.match(/rgba?\([^)]+\)/g) || []; const ls = cols.map(lum).filter(x => x != null); return ls.length && Math.max(...ls) < 0.25; })();
    if ((L != null && L < 0.25) || gradDark) dark.push(`${e.tagName.toLowerCase()}.${String(e.className?.baseVal ?? e.className).split(' ')[0]}:${bg}${gradDark ? ' grad' : ''}`);
  }
  const cv = [...document.querySelectorAll('.rcv')].filter(vis).map(e => lum(getComputedStyle(e).backgroundColor));
  const panes = [...document.querySelectorAll('[data-canvas-layer]')].filter(vis).map(e => { const r = e.getBoundingClientRect(); return {layer: e.getAttribute('data-canvas-layer'), top: Math.round(r.top), left: Math.round(r.left), w: Math.round(r.width), h: Math.round(r.height), apps: e.querySelectorAll('[role=application]').length}; });
  return {dark: [...new Set(dark)].slice(0, 12), darkN: dark.length, cv, panes};
}, theme);
const fails = [], rows = [];
const views = [['NOVEL', null], ['IMAGE', 'canvas'], ['IMAGE', 'dual'], ['VIDEO', 'studio'], ['VIDEO', 'dual'], ['AUDIO', null], ['EDIT', null], ['ASSETS', null]];
for (const theme of ['light', 'dark']) for (const mode of ['normal', 'pro']) {
  const {ctx, p, errs} = await session(theme); await skipGate(p);
  if (mode === 'pro') { await p.locator('.shell-mode-toggle button').nth(1).click().catch(() => {}); await p.waitForTimeout(500); }
  for (const [mod, view] of views) {
    if (view === 'dual' && mode !== 'pro') continue;
    await p.setViewportSize({width: 1366, height: 800});
    await p.locator(`[data-module-tab="${mod}"]`).click().catch(() => {}); await p.waitForTimeout(700); await skipGate(p);
    if (mod === 'IMAGE') { await p.locator(`.nv-tabs__tab[data-view="${view}"]`).first().click().catch(() => {}); await p.waitForTimeout(500); }
    if (mod === 'VIDEO') { if (view === 'dual') { const d = p.locator('[data-open-dual]'); if (await d.count()) await d.first().click(); } else { const back = p.getByRole('button', {name: '回视频工作室'}); if (await back.count()) await back.first().click(); } await p.waitForTimeout(600); }
    for (const w of WS) {
      await p.setViewportSize({width: w, height: 800}); await p.waitForTimeout(250);
      const r = await probe(p, theme); const v = [];
      if (theme === 'light' && r.darkN) v.push('T1 dark surfaces: ' + r.dark.join(' | '));
      if (theme === 'light' && r.cv.some(L => L != null && L < 0.5)) v.push('T1 light canvas too dark ' + r.cv.map(x => x?.toFixed(3)).join(','));
      if (theme === 'dark' && r.cv.some(L => L == null || L > 0.1)) v.push('T1 dark canvas not dark ' + r.cv.join(','));
      if (PHASE === 'after' && view === 'dual') {
        const up = r.panes.find(x => x.layer === 'upper'), lo = r.panes.find(x => x.layer === 'lower');
        if (!up || !lo) v.push('D1 missing upper/lower ' + JSON.stringify(r.panes));
        else { if (!(up.top < lo.top)) v.push('D1 upper not above lower'); if (up.apps !== 1 || lo.apps !== 1) v.push('D1 each layer must own one canvas'); }
      }
      let ax = [];
      if (AXE) { await p.addScriptTag({content: AXE}); ax = await p.evaluate(async () => (await axe.run(document, {resultTypes: ['violations']})).violations.filter(x => ['serious', 'critical'].includes(x.impact)).map(x => `${x.id}:${x.nodes.length}`)); if (ax.length) v.push('X axe ' + ax.join(',')); }
      const key = `${theme}|${mode}|${mod}${view ? ':' + view : ''}|${w}`; rows.push({key, ...r, v});
      if (v.length) fails.push(key + ' :: ' + v.join('; '));
      if (SHOTS && ['IMAGE', 'VIDEO', 'EDIT'].includes(mod)) await p.screenshot({path: `${SHOTS}/${PHASE}-${theme}-${mode}-${mod}${view ? '-' + view : ''}-${w}.png`});
    }
    if (PHASE === 'after' && view === 'dual') { // D2: upper usable while lower empty; lower untouched
      await p.setViewportSize({width: 1366, height: 800}); await p.waitForTimeout(200);
      const upSvg = p.locator('[data-canvas-layer="upper"] [role=application]'), loSvg = p.locator('[data-canvas-layer="lower"] [role=application]');
      const cnt = l => l.locator('xpath=ancestor::*[contains(@class,"rcv")][1]').locator('[data-node-id]').count();
      const lo0 = await cnt(loSvg), up0 = await cnt(upSvg);
      const bb = await upSvg.boundingBox(); await p.mouse.click(bb.x + bb.width - 60, bb.y + 40, {button: 'right'}); await p.waitForTimeout(200);
      const item = p.locator('[data-canvas-layer="upper"] [data-add-node-menu] [data-node-type]').first(); if (await item.count()) await item.click();
      await p.waitForTimeout(200); const lo1 = await cnt(loSvg), up1 = await cnt(upSvg);
      const v = []; if (lo0 !== 0) v.push(`D2 lower not empty (${lo0})`); if (up1 !== up0 + 1) v.push(`D2 upper add failed ${up0}->${up1}`); if (lo1 !== lo0) v.push('D2 lower mutated');
      rows.push({key: `${theme}|${mode}|${mod}:D2`, up0, up1, lo0, lo1, v}); if (v.length) fails.push(`${theme}|${mode}|${mod}:D2 :: ` + v.join('; '));
    }
  }
  if (errs.length) fails.push(`${theme}|${mode} pageerror: ${errs.slice(0, 3).join(' | ')}`);
  await ctx.close();
}
await b.close();
if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify({rows, fails}, null, 1));
console.log(`rows=${rows.length} fails=${fails.length}`); for (const f of fails) console.log(' ✗ ' + f);
process.exit(fails.length ? 1 : 0);
