// Run against this worktree's Vite dev server. A local synthetic component check,
// not backend, packaged-app or full Image-workspace acceptance.
import assert from 'node:assert/strict';
import { mkdir, writeFile } from 'node:fs/promises';
import path from 'node:path';
import { chromium } from '@playwright/test';

const baseURL = process.argv[2] || 'http://127.0.0.1:5187';
const output = path.resolve(process.argv[3] || 'test-results/mask-redo-browser');
await mkdir(output, { recursive: true });
const browser = await chromium.launch({ executablePath: process.env.PLAYWRIGHT_CHROMIUM_EXECUTABLE || undefined });
const report = { kind: 'local synthetic real-component browser check', browser: browser.version(), results: [] };
try {
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    const page = await browser.newPage({ viewport: { width, height }, locale: 'zh-CN', timezoneId: 'Asia/Shanghai', deviceScaleFactor: 1, colorScheme: 'light' });
    const errors = [], apiRequests = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.route('**/api/**', route => { apiRequests.push(route.request().url()); return route.abort(); });
    await page.goto(`${baseURL}/ui-fixture?module=IMAGE`);
    await page.locator('.app-shell').waitFor();
    await page.evaluate(async () => { const fixture = await import('/tests/visual/studio-mask-redo.fixture.tsx'); await fixture.mount(); });
    const redo = page.getByRole('button', { name: '重做蒙版编辑', exact: true });
    await redo.waitFor(); await page.evaluate(() => document.fonts.ready);
    await page.addStyleTag({ content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}' });
    assert.equal(await redo.isDisabled(), true);
    const pixels = () => page.getByRole('application', { name: '二值蒙版绘图区' }).evaluate(canvas => Array.from(canvas.getContext('2d').getImageData(0, 0, canvas.width, canvas.height).data));
    const initial = await pixels();
    await page.getByRole('button', { name: '应用精确矩形', exact: true }).click();
    const edited = await pixels(); assert.notDeepEqual(edited, initial);
    await page.getByRole('button', { name: '撤销蒙版编辑', exact: true }).click();
    assert.deepEqual(await pixels(), initial); assert.equal(await redo.isEnabled(), true);
    await redo.click(); assert.deepEqual(await pixels(), edited); assert.equal(await redo.isDisabled(), true);
    await page.locator('.main-workspace').evaluate(element => { element.scrollTop = 0; });
    const geometry = await page.evaluate(() => {
      const rect = selector => { const r = document.querySelector(selector).getBoundingClientRect(); return { x: r.x, y: r.y, width: r.width, height: r.height, right: r.right, bottom: r.bottom }; };
      const controls = [...document.querySelectorAll('[aria-label="蒙版笔刷工具"] button')].map(element => {
        const r = element.getBoundingClientRect(); return { label: element.textContent, x: r.x, y: r.y, right: r.right, bottom: r.bottom, width: r.width, height: r.height };
      });
      return { header: rect('.global-header'), context: rect('.context-bar'), sidebar: rect('.workspace-sidebar'), main: rect('.main-workspace'), inspector: rect('.workspace-inspector'), status: rect('.status-bar'), controls,
        pageWidth: document.documentElement.scrollWidth, mainScrollWidth: document.querySelector('.main-workspace').scrollWidth, mainClientWidth: document.querySelector('.main-workspace').clientWidth };
    });
    assert.equal(geometry.header.height, 56); assert.equal(geometry.context.height, 44); assert.equal(geometry.status.height, 32);
    assert.equal(geometry.sidebar.width, 248); assert.equal(geometry.inspector.width, 340);
    assert.ok(geometry.pageWidth <= width); assert.ok(geometry.mainScrollWidth <= geometry.mainClientWidth);
    for (const control of geometry.controls) {
      assert.ok(control.width > 0 && control.height >= 32); assert.ok(control.x >= geometry.main.x && control.right <= geometry.main.right);
    }
    for (let i = 0; i < geometry.controls.length; i++) for (let j = i + 1; j < geometry.controls.length; j++) {
      const a = geometry.controls[i], b = geometry.controls[j];
      assert.ok(a.right <= b.x || b.right <= a.x || a.bottom <= b.y || b.bottom <= a.y);
    }
    assert.deepEqual(errors, []); assert.deepEqual(apiRequests, []);
    const screenshot = `mask-redo-${width}x${height}.png`;
    await page.screenshot({ path: path.join(output, screenshot) });
    report.results.push({ viewport: { width, height }, geometry, screenshot, browserErrors: errors, apiRequests, pixelUndoRedo: 'PASS' });
    await page.close();
  }
  await writeFile(path.join(output, 'browser-report.json'), JSON.stringify(report, null, 2));
  console.log(`PASS: exact canvas undo/redo and shell/control geometry at ${report.results.length} desktop viewports; no API requests or browser errors.`);
} finally {
  await browser.close();
}
