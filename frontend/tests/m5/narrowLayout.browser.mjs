// [HERMIA-FE-20261025 LAYOUT-P3] Real-browser layout assertions for the shell at narrow widths (replaces CSS-text matching).
// Read-only MOCK: every non-GET is aborted; never calls a model or the real backend.
// Usage: BASE=http://127.0.0.1:4799/ node tests/m5/narrowLayout.browser.mjs   (env: WS=widths, SHOTS=dir, AXE=path/to/axe.min.js, OUT=json)
// Exit 1 on any violation. Assertions per (locale × mode × width × module):
//  A1 Settings button fully inside viewport; no header button past the right edge; no horizontal page scroll
//  A2 no vertical text squeeze in the main area (leaf text narrower than 2.2em but taller than 3.2em)
//  A3 empty-state buttons stay inside their workspace container
//  A4 ≤1100: left rail (.mw-left/.vid-rail) hidden AND a narrow-nav alternative entry is visible for IMAGE/ASSETS/VIDEO
//  A5 1181–1280 zh: Ctrl K hint visible (P3)
//  A6 [HERMIA-FE-20261030 VERA-MF] NSFW badge on: settings still in viewport (A1) and a visible search label is not ellipsis-truncated
//  A7 [HERMIA-FE-20261031 VERA-OBS] no visible button/link in the main area (incl. NOVEL assistant rail) extends past the viewport right edge — geometric, so it also catches painted content spilling from a collapsed (aria-hidden/inert) rail
//  Header-fit sweep: NSFW=off,on WS=1024,1280,1366,1440,1441,1460,1500,1540,1600,1680,1720,1800,1920 MODS=NOVEL
import {createRequire} from 'node:module';
import fs from 'node:fs';
const req = createRequire(import.meta.url);
const {chromium} = req('playwright-core');
const {createBackend} = await import(new URL('./mockBackend.mjs', import.meta.url));
const BASE = process.env.BASE || 'http://127.0.0.1:4799/';
const WS = (process.env.WS || '1024,1100,1101,1180,1200,1201,1240,1268,1280,1366').split(',').map(Number);
const NSFW = (process.env.NSFW || 'off').split(',');
const MODS = (process.env.MODS || 'NOVEL,IMAGE,VIDEO,AUDIO,EDIT,ASSETS').split(',');
const SHOTS = process.env.SHOTS; if (SHOTS) fs.mkdirSync(SHOTS, {recursive: true});
const AXE = process.env.AXE ? fs.readFileSync(process.env.AXE, 'utf8') : null;
const b = await chromium.launch({executablePath: process.env.CHROME || '/usr/bin/google-chrome'});
const ch = P => [{id: 'ch-001', novel_id: P, number: 1, title: '第一章', content: '<p>雾</p>', document: {type: 'doc', content: [{type: 'paragraph', content: [{type: 'text', text: '雾从港口漫上来。'}]}]}, version: 3, word_count: 8, status: 'draft'}];
async function session(loc) {
  const be = createBackend(), P = be.d.P;
  const ctx = await b.newContext({viewport: {width: 1366, height: 800}});
  await ctx.route('**/*', async rt => {
    const q = rt.request(), u = new URL(q.url());
    if (!['GET', 'HEAD'].includes(q.method())) return rt.abort();
    if (!u.pathname.startsWith('/api/')) return rt.continue();
    if (/\/chapters$/.test(u.pathname)) return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(ch(P))});
    if (/^\/api\/chapters\/ch-001$/.test(u.pathname)) return rt.fulfill({status: 200, contentType: 'application/json', body: JSON.stringify(ch(P)[0])});
    const [s, j] = be.handle('GET', q.url(), null);
    if (j && j.__bytes) return rt.fulfill({status: s, contentType: j.type, body: j.__bytes});
    return rt.fulfill({status: s, contentType: 'application/json', body: JSON.stringify(j)});
  });
  await ctx.addInitScript(([s, sc, l]) => { if (!sessionStorage.getItem('nl-init')) { sessionStorage.setItem('nl-init', '1'); localStorage.setItem('studio.session', s); localStorage.setItem('studio.scope', JSON.stringify(sc)); localStorage.setItem('studio.locale', l); } }, ['tok-nl', be.d.SCOPE, loc]);
  const p = await ctx.newPage();
  await p.goto(BASE); await p.waitForFunction(() => !document.body.innerText.includes('正在加载…'), null, {timeout: 60000}).catch(() => {});
  await p.waitForTimeout(1500);
  return {ctx, p};
}
const skipGate = async p => { for (const t of ['跳过，直接进入小说写作', 'Skip, go straight to novel writing']) { const l = p.getByRole('button', {name: t, exact: true}).first(); if (await l.count()) { await l.click().catch(() => {}); await p.waitForTimeout(500); } } };
const probe = p => p.evaluate((process_hdr) => {
  const vis = e => { const r = e.getBoundingClientRect(), cs = getComputedStyle(e); return r.width > 0 && r.height > 0 && cs.visibility !== 'hidden' && cs.display !== 'none' && !e.closest('[inert],[aria-hidden=true]'); };
  const T = e => (e.innerText || e.textContent || '').trim().replace(/\s+/g, ' ');
  const out = [];
  const set = document.querySelector('.shell-settings>button');
  if (!set || !vis(set)) out.push('A1 settings missing'); else { const r = set.getBoundingClientRect(); if (r.right > innerWidth + 0.5 || r.left < 0) out.push(`A1 settings right=${Math.round(r.right)} > ${innerWidth}`); }
  if (document.documentElement.scrollWidth > innerWidth) out.push(`A1 hscroll ${document.documentElement.scrollWidth}`);
  const hdr = document.querySelector('.global-header');
  for (const e of hdr.querySelectorAll('button')) if (vis(e)) { const r = e.getBoundingClientRect(); if (r.right > innerWidth + 0.5) out.push('A1 header btn out: ' + (e.getAttribute('aria-label') || T(e)).slice(0, 20)); }
  const vert = [...document.querySelectorAll('main *')].filter(e => vis(e) && e.children.length === 0 && T(e).length >= 4).filter(e => { const r = e.getBoundingClientRect(), fs = parseFloat(getComputedStyle(e).fontSize) || 12; return r.width < fs * 2.2 && r.height > fs * 3.2; });
  if (vert.length) out.push('A2 squeeze: ' + vert.slice(0, 3).map(T).join('|').slice(0, 60));
  for (const c of document.querySelectorAll('.media-ws-main,.main-workspace')) { if (!vis(c)) continue; const cr = c.getBoundingClientRect();
    for (const bt of c.querySelectorAll('.img-empty button,.mw-empty button,[class*=empty] button')) if (vis(bt)) { const r = bt.getBoundingClientRect(); if (r.right > cr.right + 1 || r.left < cr.left - 1) out.push('A3 btn out: ' + T(bt).slice(0, 20)); } }
  for (const e of document.querySelectorAll('main button, main a[href]')) { const r0 = e.getBoundingClientRect(); if (r0.width > 0 && r0.height > 0 && getComputedStyle(e).visibility !== 'hidden' && !e.closest('.global-header')) { const r = e.getBoundingClientRect(); if (r.right > innerWidth + 0.5) out.push(`A7 btn out: ${(e.getAttribute('aria-label') || T(e)).slice(0, 20)} r=${Math.round(r.right)}`); } }
  const rails = [...document.querySelectorAll('.mw-left,.vid-rail')].filter(vis);
  const narrowNav = [...document.querySelectorAll('[data-narrow-nav]')].filter(vis);
  const kbd = document.querySelector('.global-search>kbd'); const kbdVis = !!kbd && vis(kbd) && kbd.getBoundingClientRect().width > 2;
  const hdrKids = process_hdr ? [...hdr.children].map(e => { const r = e.getBoundingClientRect(); return `${String(e.className).slice(0, 24)}:${Math.round(r.width)}`; }).join(' ') : '';
  const sp = document.querySelector('.global-search>span');
  if (sp && vis(sp) && sp.getBoundingClientRect().width > 2 && sp.scrollWidth > sp.clientWidth + 1) out.push(`A6 search label truncated ${sp.scrollWidth}/${sp.clientWidth}`);
  return {out, rails: rails.length, narrowNav: narrowNav.length, kbdVis, hdrKids};
}, !!process.env.HDR);
const fails = [], rows = []; let combos = 0;
const skipTour = async p => { const t = p.locator('[data-onboarding-skip]'); if (await t.count()) { await t.first().click().catch(() => {}); await p.waitForTimeout(300); } };
const nsfwOn = async p => { await p.setViewportSize({width: 1920, height: 800}); await skipTour(p); await p.locator('[data-settings-trigger]').first().click(); await p.waitForSelector('[role=menu]'); await p.locator('[data-nsfw-toggle]').click(); await p.waitForSelector('[data-testid=nsfw-dialog]'); await p.locator('[data-nsfw-ack]').check(); await p.locator('[data-nsfw-confirm]').click(); await p.waitForSelector('[data-nsfw-badge]'); await p.keyboard.press('Escape'); await p.waitForTimeout(300); };
for (const nsfw of NSFW) for (const loc of ['zh-CN', 'en']) for (const mode of ['normal', 'pro']) {
  const {ctx, p} = await session(loc); await skipTour(p); await skipGate(p); await skipTour(p);
  if (nsfw === 'on') await nsfwOn(p);
  if (mode === 'pro') { await p.locator('.shell-mode-toggle button').nth(1).click().catch(() => {}); await p.waitForTimeout(500); }
  for (const id of MODS) {
    await p.setViewportSize({width: 1366, height: 800});
    await p.locator(`[data-module-tab="${id}"]`).click().catch(() => {}); await p.waitForTimeout(700); await skipGate(p);
    for (const w of WS) {
      await p.setViewportSize({width: w, height: 800}); await p.waitForTimeout(120);
      const r = await probe(p); combos++;
      const v = r.out.filter(x => nsfw === 'on' || !x.startsWith('A6')); const notes = r.out.filter(x => nsfw === 'off' && x.startsWith('A6'));
      if (w <= 1100 && ['IMAGE', 'VIDEO', 'AUDIO', 'ASSETS'].includes(id) && r.rails) v.push('A4 left rail still visible');
      if (w <= 1100 && ['IMAGE', 'VIDEO', 'ASSETS'].includes(id) && !r.narrowNav) v.push('A4 no narrow-nav alternative entry');
      if (nsfw === 'off' && w >= 1181 && w <= 1280 && loc === 'zh-CN' && !r.kbdVis) v.push('A5 Ctrl K hint hidden');
      const key = `${nsfw}|${loc}|${mode}|${w}|${id}`; rows.push({key, ...r, v, notes}); if (notes.length) console.log('NOTE(pre-existing, NSFW off) ' + key + ' :: ' + notes.join('; ')); if (process.env.HDR) console.log(key, r.hdrKids);
      if (v.length) fails.push(key + ' :: ' + v.join('; '));
      if (SHOTS && (w === 1024 || w === 1201 || w === 1268)) await p.screenshot({path: `${SHOTS}/${loc}-${mode}-${w}-${id}.png`});
      if (AXE && (w === 1024 || w === 1366)) { await p.addScriptTag({content: AXE}); const ax = await p.evaluate(async () => (await axe.run(document, {resultTypes: ['violations']})).violations.filter(x => ['serious', 'critical'].includes(x.impact)).map(x => x.id + ':' + x.nodes.length)); if (ax.length) fails.push(key + ' :: AXE ' + ax.join(',')); }
    }
  }
  await ctx.close();
}
await b.close();
if (process.env.OUT) fs.writeFileSync(process.env.OUT, JSON.stringify({combos, fails, rows}, null, 1));
console.log(`combos=${combos} violations=${fails.length}`); for (const f of fails) console.log('  ' + f);
process.exit(fails.length ? 1 : 0);
