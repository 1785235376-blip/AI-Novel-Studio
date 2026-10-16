import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api';
const UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ }); if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '多语言版本与术语', exact: true }).click();
}
test('B05 original local synthetic admission: exact segment preview, recover one job, explicit draft adoption and separate review', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '', jobId = '';
  const dispatches: string[] = []; page.on('request', req => { if (req.method() === 'POST' && /\/translations\/[^/]+\/dispatch$/.test(req.url())) dispatches.push(req.url()); });
  info.annotations.push({ type: 'verification', description: 'Actual React + File + original AuthorPreparer/ModelBroker/JobManager. Explicit shipped synthetic protocol provider. No response mocks, paid inference or language-quality acceptance. Local browser NOT_RUN (known EPERM); hosted browser receipt required.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('B05 original translation synthetic'); const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await body(await creating)).id;
    const made = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '合成翻译章节', content: 'SYNTHETIC_SELECTED_阿青🙂é\n\nEXCLUDED_OTHER_PARAGRAPH' } }));
    const initial = await body(await request.get(`${API}/chapters/${made.id}`, { headers }));
    const chapter = await body(await request.put(`${API}/chapters/${made.id}`, { headers, data: { version: initial.version, document: { type: 'doc', content: ['SYNTHETIC_SELECTED_阿青🙂é', 'EXCLUDED_OTHER_PARAGRAPH'].map(text => ({ type: 'paragraph', content: [{ type: 'text', text }] })) } } }));
    const source = await body(await request.get(`${API}/chapters/${chapter.id}`, { headers })); const history = await body(await request.get(`${API}/chapters/${chapter.id}/history`, { headers }));
    const base = `${API}/novels/${nid}/experimental`; const editions = `${base}/language-editions`;
    let edition = await body(await request.post(editions, { headers, data: { title: 'Arabic synthetic edition', source_language: 'zh-Hant', target_language: 'ar', style_note: 'SYNTHETIC_LOCAL_STYLE', chapters: [{ chapter_id: chapter.id, chapter_version: chapter.version }] } }));
    const route = (await body(await request.get(`${editions}/translation/routes`, { headers }))).items.find((r: any) => r.provider_id === 'mock'); expect(route.available).toBe(true);
    await page.reload(); await open(page); await page.getByRole('button', { name: /Arabic synthetic edition · ar/ }).click();
    await page.getByRole('button', { name: '打开本段模型翻译', exact: true }).click();
    await page.getByLabel('本段翻译本地模型路线', { exact: true }).selectOption(route.route_id);
    await expect(page.getByRole('button', { name: '预览本段翻译请求与费用', exact: true })).toBeDisabled();
    await page.getByLabel('允许合成协议测试路线，不代表真实翻译质量', { exact: true }).check();
    const previewing = page.waitForResponse(r => r.url().endsWith('/translation-preview') && r.request().method() === 'POST'); await page.getByRole('button', { name: '预览本段翻译请求与费用', exact: true }).click();
    const preview = await body(await previewing); expect(preview.preview.request.context).toEqual({}); expect(preview.preview.request.prompt).toContain('SYNTHETIC_SELECTED_阿青🙂é'); expect(preview.preview.request.prompt).not.toContain('EXCLUDED_OTHER_PARAGRAPH');
    expect(preview.preview.request.prompt).toContain('SYNTHETIC_LOCAL_STYLE'); expect(preview.preview.broker.chosen.price.reserve_microusd).toBe(0); expect(dispatches).toHaveLength(0);
    await expect(page.getByRole('button', { name: '明确启动本段翻译', exact: true })).toBeDisabled();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) { await page.setViewportSize({ width, height }); const bounds = await page.getByRole('region', { name: '本段模型翻译', exact: true }).boundingBox(); expect(bounds!.width).toBeGreaterThan(200); await page.screenshot({ path: info.outputPath(`translation-exact-preview-${width}.png`), fullPage: true }); }
    await page.getByLabel('已核对本段原文、术语、目标语言、本地路线和零成本预留', { exact: true }).check();
    const launching = page.waitForResponse(r => r.url().endsWith(`/translations/${preview.id}/dispatch`)); await page.getByRole('button', { name: '明确启动本段翻译', exact: true }).click(); const running = await body(await launching); jobId = running.execution.job_id;
    await page.getByRole('button', { name: '收起本段模型翻译', exact: true }).click(); await page.getByRole('button', { name: '打开本段模型翻译', exact: true }).click();
    await page.getByRole('button', { name: new RegExp(`翻译任务 ${preview.id.slice(0, 8)}`) }).click();
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${running.execution.reservation_id}`, { headers }))).ledger.status).toBe('SETTLED');
    await page.getByRole('button', { name: '刷新原翻译任务并核对候选', exact: true }).click(); await expect(page.getByLabel('本段未审核翻译候选', { exact: true })).toBeVisible();
    await expect(page.getByRole('button', { name: '仅采用到本段译文草稿', exact: true })).toBeDisabled(); await expect(page.getByLabel('第 1 段译文', { exact: true })).toHaveValue('');
    await page.getByLabel('确认将候选替换本段已保存译文为草稿，之后另行审核', { exact: true }).check(); const adopting = page.waitForResponse(r => r.url().endsWith(`/translations/${preview.id}/adopt`));
    await page.getByRole('button', { name: '仅采用到本段译文草稿', exact: true }).click(); edition = await body(await adopting); expect(edition.segments[0].status).toBe('DRAFT'); expect(edition.segments[1].target_text).toBe('');
    await expect(page.getByLabel('第 1 段译文', { exact: true })).toHaveValue(edition.segments[0].target_text); await expect(page.getByRole('button', { name: '提交本段审核', exact: true })).toBeEnabled();
    expect((await request.post(`${API}/generation/${jobId}/accept`, { headers, data: {} })).status()).toBe(409);
    await page.getByRole('button', { name: '提交本段审核', exact: true }).click(); await page.getByRole('button', { name: '预检本段术语与版本', exact: true }).click();
    await expect(page.getByRole('button', { name: '确认仅接受本段译文', exact: true })).toBeDisabled(); await page.getByLabel('已人工核对本段译文、术语与源版本', { exact: true }).check(); await page.getByRole('button', { name: '确认仅接受本段译文', exact: true }).click();
    await expect(page.getByRole('button', { name: '重新打开本段', exact: true })).toBeEnabled(); await page.screenshot({ path: info.outputPath('translation-separate-segment-review.png'), fullPage: true });
    expect(await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }))).toEqual(source); expect(await body(await request.get(`${API}/chapters/${chapter.id}/history`, { headers }))).toEqual(history);
    expect(dispatches).toHaveLength(1); expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(1);
    await quiesce.drain(); await page.reload(); await open(page); await page.getByRole('button', { name: /Arabic synthetic edition · ar/ }).click(); await page.getByRole('button', { name: '打开本段模型翻译', exact: true }).click();
    await page.getByRole('button', { name: new RegExp(`翻译任务 ${preview.id.slice(0, 8)}`) }).click(); await expect(page.getByText('状态 ADOPTED', { exact: true })).toBeVisible();
    await body(await request.put(`${API}/chapters/${chapter.id}`, { headers, data: { version: source.version, content: 'Changed synthetic source' } })); await page.getByRole('button', { name: '刷新当前语言版本', exact: true }).click();
    await expect(page.getByText('原稿版本、段落或隐私已改变。', { exact: false })).toBeVisible(); await expect(page.getByLabel('第 1 段译文', { exact: true })).toHaveCount(0); expect(dispatches).toHaveLength(1);
    await info.attach('translation-original-receipts.json', { body: JSON.stringify({ preview_id: preview.id, request_digest: preview.preview.author.preview_digest, job_id: jobId, reservation_id: running.execution.reservation_id, model_quality: 'NOT_RUN', original_source_unchanged_before_explicit_source_edit: true }, null, 2), contentType: 'application/json' });
  } finally {
    if (!page.isClosed() && info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('translation-journey-failure.png'), fullPage: true }).catch(() => {});
    if (jobId) await request.post(`${API}/generation/${jobId}/cancel`, { headers }).catch(() => {});
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
