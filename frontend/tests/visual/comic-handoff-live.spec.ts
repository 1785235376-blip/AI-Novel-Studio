import { expect, test, type Page } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';

// This test needs the original app.main runtime and production Vite build.
// The task launcher supplies only isolated data/env; no API or auth is replaced.
const evidence = process.env.COMIC_LIVE_EVIDENCE_DIR;
if (!evidence) throw new Error('COMIC_LIVE_EVIDENCE_DIR must name a real task-private runtime');
const seed = JSON.parse(readFileSync(path.join(evidence, 'seed-result.json'), 'utf8'));
const secret = JSON.parse(readFileSync(path.resolve(evidence, '../../task/studio-v2-comic-live-handoff-browser/.runtime/comic-live-profile/host.private.json'), 'utf8'));

test('real approved whole pages -> real HTTP Assets and Timeline -> refresh recovery -> native Timeline open', async ({ page }, info) => {
  const calls: { method: string; path: string; status: number; request: unknown; response: unknown }[] = [];
  const errors: string[] = [], pending: Promise<void>[] = [];
  const title = 'SYNTHETIC Browser Live Draft';
  const project = seed.project.id as string;
  const base = `/api/projects/${project}/studio/production`;
  let created: any;
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const url = new URL(response.url());
    if (!url.pathname.startsWith('/api/')) return;
    const request = response.request();
    pending.push((async () => {
      let body: unknown = undefined;
      if (url.pathname.includes('/comic-handoffs') || url.pathname.includes('/timelines') || url.pathname === '/api/local-session') {
        try { body = await response.json(); } catch { body = { non_json_bytes: (await response.body()).length }; }
      }
      let input: unknown = undefined;
      try { input = request.postDataJSON(); } catch { /* no request body */ }
      calls.push({ method: request.method(), path: url.pathname, status: response.status(), request: input, response: body });
    })());
  });
  const capture = async (name: string) => {
    await page.evaluate(() => document.fonts.ready);
    await page.screenshot({ path: info.outputPath(name + '.png') });
  };
  const verifyHost = async () => {
    await page.getByRole('tab', { name: '小说', exact: true }).click();
    await page.getByRole('button', { name: '打开功能导航', exact: true }).click();
    const group = page.getByRole('button', { name: /^协作(?:当前)?$/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: 'Agent 团队', exact: true }).click();
    await page.getByRole('button', { name: '关闭功能导航', exact: true }).click();
    await page.getByLabel('本机访问凭证', { exact: true }).fill(secret.token);
    const verified = page.waitForResponse(response => new URL(response.url()).pathname === '/api/local-session');
    await page.getByRole('button', { name: '验证并绑定本机会话', exact: true }).click();
    expect((await verified).status()).toBe(200);
    await expect(page.getByText('已验证本机身份：synthetic-comic-live-host', { exact: true })).toBeVisible();
    await page.getByRole('tab', { name: '图片', exact: true }).click();
  };
  const openComic = async () => {
    await page.getByRole('button', { name: '打开漫画制作', exact: true }).click();
    await expect(page.getByText('整页交接到 Timeline 草稿', { exact: true })).toBeVisible();
  };
  const openNativeTimeline = async (id: string, screenshot: string) => {
    await page.getByRole('button', { name: '制作操作', exact: true }).click();
    await page.getByRole('button', { name: '读取当前素材版本', exact: true }).click();
    const editor = page.locator('[aria-label="Studio 多轨时间线编辑器"]');
    await expect(editor).toBeVisible();
    await editor.getByRole('button', { name: '刷新时间线列表', exact: true }).click();
    const select = editor.getByLabel('读取已保存时间线');
    await expect(select.locator(`option[value="${id}"]`)).toHaveText(title + ' · v1');
    await select.selectOption(id);
    const review = editor.locator('[aria-label="核对服务端时间线"]');
    await expect(review.getByRole('heading', { name: title + ' · v1', exact: true })).toBeVisible();
    await review.getByLabel('已核对服务端内容与本地输入，确认以下选择', { exact: true }).check();
    await review.getByRole('button', { name: '采用服务端时间线', exact: true }).click();
    await expect(editor.getByLabel('名称', { exact: true })).toHaveValue(title);
    await expect(select).toHaveValue(id);
    await capture(screenshot);
  };
  try {
    await page.goto('/', { waitUntil: 'networkidle' });
    await verifyHost();
    await capture('01-host-verified-original-shell');
    await openComic();
    for (const row of seed.pages) {
      expect(row.status).toBe('APPROVED');
      expect(row.document.panels.every((panel: any) => panel.artwork_mode === 'BLANK' && !panel.asset_id)).toBe(true);
      await page.getByLabel(new RegExp(row.id)).check();
    }
    await page.getByLabel('Timeline 草稿标题', { exact: true }).fill(title);
    await page.getByLabel('输出宽度', { exact: true }).fill('640');
    await page.getByLabel('输出高度', { exact: true }).fill('360');
    await page.getByLabel('第 1 页停留时长（毫秒）', { exact: true }).fill('10000');
    await page.getByLabel('第 2 页停留时长（毫秒）', { exact: true }).fill('10000');
    const prepared = page.waitForResponse(response => new URL(response.url()).pathname === base + '/comic-handoffs/preview');
    await page.getByRole('button', { name: '检查并加载整页预览', exact: true }).click();
    expect((await prepared).status()).toBe(200);
    await expect(page.getByLabel('已查看全部整页图片，核对页面版本、顺序和逐页时长', { exact: true })).toBeEnabled();
    expect(await page.locator('img[alt^="交接整页预览"]').evaluateAll(images => images.map(image => [(image as HTMLImageElement).naturalWidth, (image as HTMLImageElement).naturalHeight]))).toEqual([[320,640],[320,640]]);
    await page.getByLabel('已查看全部整页图片，核对页面版本、顺序和逐页时长', { exact: true }).check();
    await page.getByLabel('确认静态整页合并损失，只创建未批准的 Timeline 草稿', { exact: true }).check();
    await page.getByAltText('交接整页预览 2', { exact: true }).scrollIntoViewIfNeeded();
    await capture('02-actual-native-page-preview');
    const confirmed = page.waitForResponse(response => new URL(response.url()).pathname === base + '/comic-handoffs' && response.request().method() === 'POST');
    await page.getByRole('button', { name: '明确创建原 Timeline 草稿', exact: true }).click();
    const response = await confirmed;
    expect(response.status()).toBe(200); created = await response.json();
    expect(created.status).toBe('DRAFT_CREATED'); expect(created.approval_inherited).toBe(false);
    expect(created.model_called).toBe(false); expect(created.video_rendered).toBe(false);
    expect(created.timeline.timeline.duration_ms).toBe(20000); expect(created.steps).toHaveLength(2);
    const id = created.timeline_snapshot.id as string;
    await expect(page.getByText(new RegExp('原 Timeline 草稿 ID：' + id))).toBeVisible();
    await capture('03-real-http-draft-created');
    const stored = await page.evaluate(() => ({ local: Object.values(localStorage), session: Object.values(sessionStorage) }));
    expect(JSON.stringify(stored)).not.toContain(secret.token);
    expect(JSON.stringify(stored.session)).not.toContain('png_base64');
    expect(stored.session.some(value => value.includes(created.request_id))).toBe(true);

    await page.reload({ waitUntil: 'networkidle' });
    await verifyHost(); await openComic();
    await expect(page.getByText('原请求 ID：' + created.request_id, { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '按原 ID 读回交接状态', exact: true }).click();
    await expect(page.getByText(new RegExp('原 Timeline 草稿 ID：' + id))).toBeVisible();
    await capture('04-refresh-same-id-explicit-readback');
    await page.getByRole('button', { name: '关闭交接并保留原记录', exact: true }).click();
    await expect(page.getByRole('button', { name: '新建空白漫画页', exact: true })).toBeEnabled();
    await openNativeTimeline(id, '05-original-timeline-list-adopted');

    await page.reload({ waitUntil: 'networkidle' });
    await verifyHost();
    await openNativeTimeline(id, '06-refresh-native-timeline-reopened');
    await Promise.all(pending);
    expect(calls.filter(call => call.method === 'POST' && call.path === base + '/comic-handoffs')).toHaveLength(1);
    expect(calls.filter(call => call.path.startsWith(base + '/comic-handoffs')).every(call => call.status === 200)).toBe(true);
    expect(calls.some(call => call.method === 'GET' && call.path === base + '/comic-handoffs/' + created.request_id)).toBe(true);
    expect(calls.filter(call => call.method === 'GET' && call.path === base + '/timelines/' + id).length).toBeGreaterThanOrEqual(2);
    expect(calls.filter(call => call.method !== 'GET').some(call => /\/(dispatch|render|execute|generate|resume|cancel)$/.test(call.path))).toBe(false);
    expect(errors).toEqual([]);
    writeFileSync(path.join(evidence, 'live-result.json'), JSON.stringify({ project, created, calls, errors,
      proof: 'ACTUAL_PRODUCTION_BROWSER_HTTP_NOT_FIXTURE', no_api_interception: true, explicit_same_id_refresh: true, native_timeline_opened_twice: true }, null, 2));
  } catch (error) {
    await capture('failure-current-real-ui');
    writeFileSync(path.join(evidence, 'live-failure-dom.txt'), await page.locator('body').innerText());
    throw error;
  } finally {
    await Promise.allSettled(pending);
    writeFileSync(path.join(evidence, 'live-network-attempt.json'), JSON.stringify({ calls, errors }, null, 2));
  }
});
