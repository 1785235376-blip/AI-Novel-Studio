import { expect, test, type APIRequestContext, type APIResponse, type Page, type TestInfo } from '@playwright/test';
import { createHash } from 'node:crypto';
import { createPageQuiescer } from './r3-fixture-lifecycle';

/** U13 real-browser contracts. Authored tests are NOT_RUN until CI executes them.
 * No generated/model text, intercepted business API, fake timers or OS IME claim.
 * Browser event-to-two-rAF timings are rendering opportunities, not physical
 * display/OS keystroke latency; CSS zoom is explicitly a layout simulation.
 */
const API = process.env.R4_API_URL || 'http://127.0.0.1:8019/api';
const OFF_API = process.env.R4_OFF_API_URL || 'http://127.0.0.1:8020/api';
const OFF_UI = process.env.R4_OFF_UI_URL || 'http://127.0.0.1:5180';
const WARMUPS = 3, SAMPLES = 30;
const owned = new WeakMap<Page, Array<{ api: string; id: string }>>();
const quiescers = new WeakMap<Page, ReturnType<typeof createPageQuiescer>>();
const modelRequests = new WeakMap<Page, string[]>();
const original = [
  '阿澄在月港修理星桥灯塔。乔岚把旧信放进木盒，沈墨守在门外。',
  '作者知道沈墨藏着铜钥，阿澄尚不知道这个秘密。乔岚误以为旧桥已经封闭。',
  '记录说船在昨日离港，另一页却写它明日才造好；这个时间冲突还没有解决。',
  '约定第三章揭开的旧信一直没有打开，这条伏笔已经过期。',
  '月港既是城镇名称，也是同名船只；阿澄在月港望着月港号。',
  '北岸路线保留灯塔，南岸路线拆除旧桥。两个分支只是规划，没有替换正文。',
  '乔岚说：“灯塔照亮归途。”乔岚再次解释，灯塔照亮归途。',
  '三人核对潮汐，沿石阶慢慢返回；清风吹动纸页，远处传来钟声。\n',
];
function hanCount(value: string) { return [...value.matchAll(/\p{Unified_Ideograph}/gu)].length; }
function chapterText(target: number, index: number) {
  const unit = [...original.slice(index % original.length), ...original.slice(0, index % original.length)].join('');
  const repeated = unit.repeat(Math.floor(target / hanCount(unit)) + 1);
  let count = 0;
  for (const match of repeated.matchAll(/\p{Unified_Ideograph}/gu)) {
    if (++count === target) return repeated.slice(0, match.index! + match[0].length);
  }
  throw new Error('Synthetic generator did not meet exact Han target');
}
async function json(response: APIResponse) {
  expect(response.ok(), `Fixture request HTTP ${response.status()}`).toBeTruthy();
  return response.json();
}
async function fixture(page: Page, request: APIRequestContext, size: number, api = API, ui = '/') {
  expect(await json(await request.get(`${api}/novels`)), 'Dedicated browser profile must be empty; never delete unknown projects').toHaveLength(0);
  const novel = await json(await request.post(`${api}/novels`, { data: { title: `R4 synthetic ${size}`, id: `r4-u13-${size}` } }));
  owned.get(page)!.push({ api, id: novel.id });
  const bodies = [];
  for (let index = 0; index < 12; index++) {
    const content = chapterText(Math.floor(size / 12) + (index < size % 12 ? 1 : 0), index);
    bodies.push(content);
    await json(await request.post(`${api}/novels/${novel.id}/chapters`, { data: { title: `R4 Synthetic Chapter ${String(index + 1).padStart(2, '0')}`, content } }));
  }
  for (const [id, name] of [['acheng', '阿澄'], ['qiaolan', '乔岚'], ['shenmo', '沈墨']]) {
    await json(await request.put(`${api}/novels/${novel.id}/characters/${id}`, { data: { name, privacy_level: 'LOCAL_ONLY' } }));
  }
  for (const [id, title] of [['north', '北岸路线'], ['south', '南岸路线']]) {
    await json(await request.put(`${api}/novels/${novel.id}/story-routes/${id}`, { data: { title, status: 'DRAFT' } }));
  }
  const rows = await json(await request.get(`${api}/novels/${novel.id}/chapters`));
  expect(rows).toHaveLength(12);
  expect(rows.reduce((count: number, row: { content: string }) => count + hanCount(row.content), 0)).toBe(size);
  await page.goto(ui);
  await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toBeVisible();
  await page.evaluate(() => document.fonts.ready);
  return { novel, chapter: rows[0], contentSha256: createHash('sha256').update(bodies.join('')).digest('hex') };
}
async function save(page: Page) {
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('已保存');
}
async function attach(info: TestInfo, name: string, value: unknown) {
  await info.attach(name, { body: JSON.stringify(value, null, 2), contentType: 'application/json' });
}
function percentile(values: number[], fraction: number) {
  return [...values].sort((a, b) => a - b)[Math.ceil(values.length * fraction) - 1];
}

test.beforeEach(({ page }) => {
  owned.set(page, []);
  quiescers.set(page, createPageQuiescer(page));
  const calls: string[] = [];
  modelRequests.set(page, calls);
  page.on('request', request => {
    const path = new URL(request.url()).pathname;
    if (/\/generate\/|\/execute$|\/runtimes\/[^/]+\/start$/.test(path) && request.method() !== 'GET') calls.push(path);
  });
  test.info().annotations.push({ type: 'boundary', description: 'Synthetic real File API + Chromium. Real Windows IME, screen reader, physical input latency, native browser/OS zoom and multi-monitor behavior are NOT_RUN.' });
});
test.afterEach(async ({ page, request }, info) => {
  if (info.status !== info.expectedStatus && !page.isClosed()) {
    try { await page.screenshot({ path: info.outputPath('u13-failure-before-cleanup.png'), fullPage: true }); }
    catch { info.annotations.push({ type: 'diagnostic', description: 'Screenshot unavailable; inspect retained trace.' }); }
  }
  const quiesce = quiescers.get(page)!;
  try { await quiesce(); }
  catch (error) {
    await attach(info, 'fixture-drain-blocked.json', quiesce.diagnostics());
    info.annotations.push({ type: 'cleanup-blocked', description: 'Owned fixture retained: an API request has no verified completion. Inspect sanitized drain diagnostics.' });
    throw error;
  }
  await attach(info, 'fixture-drain-completed.json', quiesce.diagnostics());
  for (const row of owned.get(page) || []) {
    const response = await request.delete(`${row.api}/novels/${encodeURIComponent(row.id)}`);
    expect([200, 204, 404], 'Delete only exact fixture IDs created by this test').toContain(response.status());
  }
  expect(modelRequests.get(page), 'No model/start/execute business requests in U13 benchmarks').toEqual([]);
  quiescers.delete(page); owned.delete(page); modelRequests.delete(page);
});

for (const size of [100_000, 500_000, 1_000_000]) {
  test(`U13 ${size} Han project input rendering samples and warm indexed API search`, async ({ page, request }, info) => {
    test.setTimeout(300_000);
    const { novel, contentSha256 } = await fixture(page, request, size);
    const editor = page.getByRole('textbox', { name: '章节正文', exact: true });
    await editor.focus(); await page.keyboard.press('Control+End');
    await page.evaluate(() => {
      const element = document.querySelector<HTMLElement>('.ProseMirror')!;
      type InputSample = { duration_ms: number; trusted: boolean; input_type: string; composing: boolean };
      const state = { samples: [] as InputSample[], before: 0, element, replacements: 0 };
      (window as unknown as { r4Input: typeof state }).r4Input = state;
      element.addEventListener('beforeinput', () => { state.before = performance.now(); });
      element.addEventListener('input', event => {
        const input = event as InputEvent, start = state.before;
        requestAnimationFrame(() => requestAnimationFrame(() => {
          if (document.querySelector('.ProseMirror') !== element) state.replacements++;
          state.samples.push({ duration_ms: performance.now() - start, trusted: event.isTrusted,
            input_type: input.inputType, composing: input.isComposing });
        }));
      });
    });
    for (let index = 0; index < WARMUPS + SAMPLES; index++) {
      await page.keyboard.insertText('文');
      await expect.poll(() => page.evaluate(() => (window as unknown as { r4Input: { samples: unknown[] } }).r4Input.samples.length)).toBe(index + 1);
    }
    const input = await page.evaluate(() => {
      const state = (window as unknown as { r4Input: { samples: Array<{ duration_ms: number; trusted: boolean; input_type: string; composing: boolean }>; replacements: number } }).r4Input;
      return { samples: state.samples, replacements: state.replacements, browser: navigator.userAgent };
    });
    const measured = input.samples.slice(WARMUPS), times = measured.map(sample => sample.duration_ms);
    const inputReport = { size_han: size, chapter_count: 12, active_chapter_han: Math.ceil(size / 12), content_sha256: contentSha256,
      method: 'Trusted Chromium beforeinput to second requestAnimationFrame after input; rendering opportunity proxy, not OS/physical-display latency',
      warmup_count: WARMUPS, sample_count: SAMPLES, percentile: 'nearest rank ceil(p*n)', samples: measured, warmups: input.samples.slice(0, WARMUPS),
      p50_ms: percentile(times, .5), p95_ms: percentile(times, .95), target_ms: 100,
      target_status: percentile(times, .95) <= 100 ? 'PASS' : 'MISS', browser: input.browser,
      editor_replacements: input.replacements, whole_project_resident: 'API fixture; editor opens one chapter, not the entire novel' };
    await attach(info, `input-latency-${size}.json`, inputReport);
    info.annotations.push({ type: 'input-target', description: `${size} Han: ${inputReport.target_status}, p95 ${inputReport.p95_ms.toFixed(2)} ms (proxy)` });
    expect(measured).toHaveLength(SAMPLES);
    expect(measured.every(sample => sample.trusted && !sample.composing && sample.duration_ms >= 0)).toBe(true);
    expect(input.replacements).toBe(0);
    await save(page);
    const saved = await json(await request.get(`${API}/chapters/${novel.id}:1`));
    expect(saved.content).toContain('文'.repeat(WARMUPS + SAMPLES));
    const queries = ['星桥灯塔', '阿澄', '旧信', '月港', '不存在的线索', '.*'];
    const searchSamples: Array<{ duration_ms: number; status: number; query: string; item_count: number; updated_documents: number; truncated: boolean }> = [];
    for (let index = 0; index < WARMUPS + SAMPLES; index++) {
      const query = queries[index % queries.length];
      const sample = await page.evaluate(async ({ api, nid, query }) => {
        const started = performance.now();
        const response = await fetch(`${api}/novels/${nid}/experimental/workspace/search?q=${encodeURIComponent(query)}`);
        const value = await response.json();
        return { duration_ms: performance.now() - started, status: response.status, query,
          item_count: value.items?.length ?? 0, updated_documents: value.updated_documents,
          truncated: value.truncated, model_called: value.model_called };
      }, { api: API, nid: novel.id, query });
      searchSamples.push(sample);
    }
    const searches = searchSamples.slice(WARMUPS), searchTimes = searches.map(row => row.duration_ms);
    const searchReport = { size_han: size, method: 'Browser fetch start through JSON parse, real loopback File API', warmups: searchSamples.slice(0, WARMUPS),
      samples: searches, sample_count: SAMPLES, p50_ms: percentile(searchTimes, .5), p95_ms: percentile(searchTimes, .95), target_ms: 500,
      target_status: searches.some(row => row.status !== 200 || row.truncated) ? 'PARTIAL' : percentile(searchTimes, .95) <= 500 ? 'PASS' : 'MISS' };
    await attach(info, `search-latency-${size}.json`, searchReport);
    expect(searches.every(row => row.status === 200 && !row.truncated)).toBe(true);
    expect(searches.filter(row => ['不存在的线索', '.*'].includes(row.query)).every(row => row.item_count === 0)).toBe(true);
  });
}

test('U13 Chromium composition, Chinese punctuation, Unicode, undo/redo and multiline paste survive save/reopen', async ({ page, request }, info) => {
  const { chapter } = await fixture(page, request, 4_000);
  const editor = page.getByRole('textbox', { name: '章节正文', exact: true });
  await editor.fill('中文原文。'); await save(page);
  await editor.focus(); await page.keyboard.press('Control+End');
  const session = await page.context().newCDPSession(page);
  await session.send('Input.imeSetComposition', { text: '中文候选', selectionStart: 4, selectionEnd: 4 });
  await expect(editor).toContainText('中文候选');
  await session.send('Input.insertText', { text: '中文候选' });
  await session.detach();
  const unicode = '，“标点”！👩🏽‍💻 e\u0301 𠀀';
  await page.keyboard.insertText(unicode);
  await expect(editor).toContainText('中文原文。中文候选' + unicode);
  await page.keyboard.press('Control+z');
  await page.keyboard.press('Control+Shift+z');
  await expect(editor).toContainText('中文原文。中文候选' + unicode);
  // Dispatch a browser ClipboardEvent with original synthetic Unicode text.
  // This tests editor paste handling without requesting system clipboard access.
  const pasted = '\n跨段落粘贴第一行。\n第二行保留组合字 e\u0301 与表情 👨‍👩‍👧‍👦。';
  await editor.evaluate((element, text) => {
    const data = new DataTransfer(); data.setData('text/plain', text);
    element.dispatchEvent(new ClipboardEvent('paste', { clipboardData: data, bubbles: true, cancelable: true }));
  }, pasted);
  await expect(editor).toContainText('跨段落粘贴第一行。');
  await expect(editor).toContainText('第二行保留组合字 e\u0301 与表情 👨‍👩‍👧‍👦。');
  await save(page);
  const persisted = await json(await request.get(`${API}/chapters/${chapter.id}`));
  expect(persisted.content).toContain('中文候选' + unicode);
  expect(persisted.content).toContain('👨‍👩‍👧‍👦');
  await quiescers.get(page)!.drain(); await page.reload(); await expect(editor).toContainText('中文候选' + unicode);
  await attach(info, 'unicode-composition-boundaries.json', {
    chromium_cdp_composition: 'REAL_BROWSER_PROTOCOL_VERIFIED', clipboard_event: 'SYNTHETIC_EVENT_REAL_EDITOR',
    saved_and_reopened: true, os_clipboard: 'NOT_RUN', windows_native_ime: 'NOT_RUN',
    screen_reader: 'NOT_RUN', asynchronous_model_suggestion: 'NOT_RUN: no model invoked',
  });
});

test('U13 keyboard dialog focus, reduced motion, high contrast and viewport/CSS zoom matrix', async ({ page, request }, info) => {
  await fixture(page, request, 4_000);
  await page.emulateMedia({ reducedMotion: 'reduce' });
  const trigger = page.getByRole('button', { name: '新建章节', exact: true });
  await trigger.focus(); await page.keyboard.press('Enter');
  await expect(page.getByLabel('章节标题')).toBeFocused();
  await page.keyboard.press('Escape');
  await expect(page.getByLabel('章节标题')).toHaveCount(0);
  await expect(trigger).toBeFocused();
  const editor = page.getByRole('textbox', { name: '章节正文', exact: true });
  await editor.focus(); await expect(editor).toBeFocused();
  const matrix = [];
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    for (const scale of [1, 1.25, 1.5, 2]) {
      await page.setViewportSize({ width, height });
      await page.evaluate(value => { document.documentElement.style.zoom = String(value); }, scale);
      await page.evaluate(() => document.fonts.ready);
      await editor.focus();
      const geometry = await page.evaluate(() => {
        const editor = document.querySelector<HTMLElement>('.ProseMirror')!;
        const rect = editor.getBoundingClientRect();
        const style = getComputedStyle(editor);
        return { document_width: document.documentElement.scrollWidth, viewport_width: innerWidth,
          editor: { x: rect.x, y: rect.y, width: rect.width, height: rect.height },
          focused: document.activeElement === editor, font_size: style.fontSize,
          horizontal_overflow: Math.max(0, document.documentElement.scrollWidth - innerWidth),
          reduced_motion: matchMedia('(prefers-reduced-motion: reduce)').matches };
      });
      matrix.push({ width, height, css_zoom: scale, method: 'CSS zoom simulation; not native browser or OS zoom', ...geometry });
      await page.screenshot({ path: info.outputPath(`u13-${width}x${height}-css-${Math.round(scale * 100)}.png`), fullPage: true });
    }
  }
  await attach(info, 'viewport-css-zoom-matrix.json', matrix);
  await page.evaluate(() => { document.documentElement.style.zoom = ''; });
  await page.setViewportSize({ width: 1440, height: 900 });
  await page.emulateMedia({ reducedMotion: 'reduce', forcedColors: 'active' });
  await editor.focus(); await expect(editor).toBeFocused();
  await expect(page.getByRole('button', { name: '保存', exact: true })).toBeVisible();
  await page.screenshot({ path: info.outputPath('u13-forced-colors-reduced-motion.png'), fullPage: true });
  expect(matrix.every(row => row.focused && row.reduced_motion && row.editor.width > 0)).toBe(true);
  // Preserve every geometry measurement before failing any clipping assertion.
  expect(matrix.filter(row => row.horizontal_overflow > 1), 'Any observed zoom overflow is a genuine unresolved layout defect').toEqual([]);
});

test('U13 no-model flags-off 100k baseline preserves Chinese editing and blocks index creation', async ({ page, request }, info) => {
  const { chapter } = await fixture(page, request, 100_000, OFF_API, OFF_UI);
  const flags = await json(await request.get(`${OFF_API}/experimental/features`));
  expect(Object.values(flags.features).every(value => value === false)).toBe(true);
  expect((await request.get(`${OFF_API}/novels/r4-u13-100000/experimental/workspace/search?q=阿澄`)).status()).toBe(404);
  const editor = page.getByRole('textbox', { name: '章节正文', exact: true });
  await editor.focus(); await page.keyboard.press('Control+End'); await page.keyboard.insertText('关闭实验功能仍能写中文。');
  await save(page); await quiescers.get(page)!.drain(); await page.reload(); await expect(editor).toContainText('关闭实验功能仍能写中文。');
  const persisted = await json(await request.get(`${OFF_API}/chapters/${chapter.id}`));
  expect(persisted.content).toContain('关闭实验功能仍能写中文。');
  await attach(info, 'flags-off-browser-baseline.json', { flags: 'ALL_OFF', real_file_save_reopen: true, model_execution_requests: modelRequests.get(page), windows_ime: 'NOT_RUN' });
});
