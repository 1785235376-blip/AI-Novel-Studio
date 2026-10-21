// Dedicated local fixture: no build, snapshot baseline updates, external API or model calls.
import { createServer } from 'vite';
import { chromium, expect } from '@playwright/test';
import { mkdir, writeFile } from 'node:fs/promises';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';

const frontend = resolve(dirname(fileURLToPath(import.meta.url)), '../../..');
const evidence = resolve(frontend, '../../evidence/canvas_bulk');
await mkdir(evidence, { recursive: true });
const server = await createServer({ root: frontend, configFile: resolve(frontend, 'vite.config.ts'), cacheDir: resolve(evidence, 'vite-cache'),
  server: { host: '127.0.0.1', port: 5198, strictPort: true },
  plugins: [{ name: 'canvas-bulk-local-fixture', configureServer(server) {
    server.middlewares.use('/canvas-bulk-fixture', async (_request, response, next) => {
      try {
        const html = await server.transformIndexHtml('/canvas-bulk-fixture', '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script type="module">import {mount} from "/src/creative/canvasBulkActions/canvasBulkActions.visual.fixture.tsx";mount();</script></body></html>');
        response.setHeader('Content-Type', 'text/html'); response.end(html);
      } catch (error) { next(error); }
    });
  } }] });
let browser;
const results = [], forbiddenRequests = [], errors = [];
try {
  await server.listen();
  browser = await chromium.launch({ headless: true });
  const context = await browser.newContext({ deviceScaleFactor: 1, locale: 'zh-CN', timezoneId: 'Asia/Shanghai', reducedMotion: 'reduce' });
  const page = await context.newPage();
  page.on('pageerror', error => errors.push(String(error)));
  await page.route('**/*', route => {
    const url = new URL(route.request().url());
    if (url.origin !== 'http://127.0.0.1:5198' || url.pathname.startsWith('/api/')) { forbiddenRequests.push(url.pathname); return route.abort(); }
    return route.continue();
  });
  for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
    await page.setViewportSize(viewport); await page.goto('http://127.0.0.1:5198/canvas-bulk-fixture');
    const panel = page.getByRole('region', { name: '画布多选操作影响预览' });
    await expect(panel).toBeVisible(); await page.evaluate(() => document.fonts.ready);
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
    const checks = panel.getByRole('checkbox'); await expect(checks).toHaveCount(2);
    const apply = panel.getByRole('button', { name: '应用到当前画布草稿（仍需 Save）' }); await expect(apply).toBeDisabled();
    const geometry = await page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, width: r.width, height: r.height }; };
      const main = document.querySelector('.main-workspace');
      return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'),
        pageWidth: document.documentElement.scrollWidth, mainWidth: main.clientWidth, mainScrollWidth: main.scrollWidth };
    });
    expect(geometry.header.height).toBe(56); expect(geometry.context.height).toBe(44); expect(geometry.status.height).toBe(32);
    expect(geometry.sidebar.width).toBe(248); expect(geometry.inspector.width).toBe(340);
    expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width); expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
    await checks.nth(0).focus(); await expect(checks.nth(0)).toBeFocused(); await page.keyboard.press('Space');
    await expect(checks.nth(0)).toBeChecked(); await expect(apply).toBeDisabled();
    await page.keyboard.press('Tab'); await expect(checks.nth(1)).toBeFocused(); await page.keyboard.press('Space');
    await expect(apply).toBeEnabled(); await page.keyboard.press('Tab'); await expect(apply).toBeFocused();
    await page.screenshot({ path: resolve(evidence, `panel-${viewport.width}x${viewport.height}.png`), fullPage: true });
    await page.keyboard.press('Space'); await expect(page.getByTestId('draft-edits')).toContainText('父编辑通知：1'); await expect(apply).toBeDisabled();
    results.push({ viewport, geometry, keyboardConsentAndSingleEdit: 'passed' });
  }
  await page.setViewportSize({ width: 1366, height: 768 }); await page.goto('http://127.0.0.1:5198/canvas-bulk-fixture?capacity=24');
  await expect(page.getByRole('checkbox')).toHaveCount(24);
  const capacity = await page.locator('.main-workspace').evaluate(element => ({ width: element.clientWidth, scrollWidth: element.scrollWidth, height: element.clientHeight, scrollHeight: element.scrollHeight }));
  expect(capacity.scrollWidth).toBeLessThanOrEqual(capacity.width); expect(capacity.scrollHeight).toBeGreaterThan(capacity.height);
  expect(forbiddenRequests).toEqual([]); expect(errors).toEqual([]);
  const result = { status: 'passed', scope: 'real CanvasBulkActionsPanel in synthetic AppShell only; parent undo/save/reopen/CAS not exercised', results, capacity, forbiddenRequests, errors };
  await writeFile(resolve(evidence, 'browser-check.json'), JSON.stringify(result, null, 2), 'utf8'); console.log(JSON.stringify(result));
} catch (error) {
  await writeFile(resolve(evidence, `browser-failure-${Date.now()}.json`), JSON.stringify({ error: String(error), results, forbiddenRequests, errors }, null, 2), 'utf8'); throw error;
} finally { if (browser) await browser.close(); await server.close(); }
