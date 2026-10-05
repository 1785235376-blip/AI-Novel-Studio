import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182', TOKEN = 'r4-broker-test-session';
const headers = { 'X-Session-Token': TOKEN };
async function checked(response: APIResponse): Promise<any> { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click(); const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '离线同步', exact: true }).click();
}

test('B10 actual File/API/React selected exchange, conflict review, receipt and revocation; distinct from two-process TCP suite', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); const projects: string[] = []; const applies: string[] = [];
  info.annotations.push({ type: 'verification', description: 'Real original File/API/React journey without response mocks, separate from RUN_B10_TCP_SYNC_TEST two-isolated-endpoint test. Local Chromium EPERM is not retried. Hosted execution is not claimed until observed.' });
  page.on('request', req => { if (req.method() === 'POST' && req.url().includes('/offline-sync/') && req.url().endsWith('/apply')) applies.push(req.url()); });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    expect(await page.evaluate(() => [localStorage.getItem('studio.session'), localStorage.getItem('studio.scope')])).toEqual([null, null]);
    await page.getByPlaceholder('小说名称').fill(`B10 synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); const novel = await checked(await created); projects.push(novel.id);
    const chapter = await checked(await request.post(`${API}/novels/${novel.id}/chapters`, { headers, data: { title: '合成交换章节', content: '同一段落基线。' } }));
    const other = await checked(await request.post(`${API}/novels/${novel.id}/chapters`, { headers, data: { title: '未选章节', content: 'MUST_NEVER_APPEAR_IN_ENVELOPE' } }));
    const baseline = await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }));
    const base = `${API}/novels/${novel.id}/experimental/offline-sync`;
    await page.reload(); await open(page); const panel = page.getByRole('region', { name: '离线同步与人工交换', exact: true });
    await panel.getByLabel('交换批次标签', { exact: true }).fill('browser-b10'); await panel.getByLabel('本端标签', { exact: true }).fill('A'); await panel.getByLabel('对端标签', { exact: true }).fill('B');
    await expect(panel.getByRole('button', { name: '保存选定交换范围', exact: true })).toBeDisabled();
    await panel.getByLabel(/同步范围：合成交换章节 · v/).check();
    await panel.getByRole('button', { name: '保存选定交换范围', exact: true }).click();
    await expect(panel.getByRole('button', { name: 'browser-b10 · A → B', exact: true })).toBeVisible();
    await panel.getByLabel('加入发件箱的已选章节', { exact: true }).selectOption(chapter.id);
    await panel.getByRole('button', { name: '保存到本机发件箱', exact: true }).click();
    await panel.getByRole('button', { name: '预览此消息内容', exact: true }).click();
    await expect(panel.getByRole('button', { name: '生成手动交换文件', exact: true })).toBeDisabled();
    await panel.getByLabel('我了解导出的本地副本无法远程撤回', { exact: true }).check();
    await panel.getByRole('button', { name: '生成手动交换文件', exact: true }).click();
    const link = panel.getByRole('link', { name: '下载本地同步消息', exact: true }); await expect(link).toBeVisible();
    const sent = await link.evaluate(async node => (await fetch((node as HTMLAnchorElement).href)).json());
    expect(sent.source_chapter_id).toBe(chapter.id); expect(JSON.stringify(sent)).not.toContain('MUST_NEVER_APPEAR_IN_ENVELOPE'); expect(sent).not.toHaveProperty('credentials');
    const out = (await checked(await request.get(base + '/records', { headers }))).outbox[0];
    const receipt = { protocol: 'AI_NOVEL_SYNC_RECEIPT_1', message_id: sent.message_id, envelope_digest: out.envelope_digest, stream_id: sent.stream_id, source_endpoint: sent.source_endpoint, destination_endpoint: sent.destination_endpoint, sequence: sent.sequence, status: 'RECEIVED' };
    await panel.getByLabel(`接收回执 ${out.id}`, { exact: true }).fill(JSON.stringify(receipt)); await panel.getByRole('button', { name: '核对接收回执', exact: true }).click();
    await expect(panel.getByText(/接收回执已核对，尚不代表已应用/)).toBeVisible();
    // Manual incoming envelope, from an independent test producer, never a
    // network identity claim. Original local write runs through the actual API.
    const local = structuredClone(baseline.document); local.content[1].content[0].text = '本机改文🙂é。';
    await checked(await request.put(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers, data: { version: baseline.version, document: local } }));
    const incoming = structuredClone(baseline.document); incoming.content[1].content[0].text = '对端合成改文。';
    const envelope = { protocol: 'AI_NOVEL_SYNC_1', stream_id: 'browser-b10', source_endpoint: 'B', destination_endpoint: 'A', message_id: 'browser-message-b10', sequence: 1, source_chapter_id: 'peer-project:1', source_version: 2, operation: 'SNAPSHOT', base: { title: baseline.title, document: baseline.document }, snapshot: { title: baseline.title, document: incoming }, privacy_level: 'LOCAL_ONLY' };
    await panel.getByLabel('收到的同步消息 JSON', { exact: true }).fill(JSON.stringify(envelope)); await panel.getByLabel('收到章节的本机目标', { exact: true }).selectOption(chapter.id);
    await panel.getByRole('button', { name: '预览待接收消息', exact: true }).click(); await panel.getByRole('button', { name: '接收到待审核收件箱', exact: true }).click();
    await expect(panel.getByLabel('可复制给发送端的接收回执', { exact: true })).toBeVisible(); expect(applies).toHaveLength(0);
    await panel.getByRole('button', { name: '读取当前三方差异', exact: true }).click();
    const conflictChoice = panel.getByLabel(/冲突选择/).first(); await expect(conflictChoice).toBeVisible();
    await expect(panel.getByRole('button', { name: '应用已核对的候选', exact: true })).toBeDisabled();
    await conflictChoice.selectOption('INCOMING'); await panel.getByRole('button', { name: '读取当前三方差异', exact: true }).click();
    const ack = panel.getByLabel('已核对差异，允许通过原章节权限与版本检查应用', { exact: true }); await expect(ack).toBeEnabled();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); expect(await panel.evaluate(node => node.scrollWidth <= node.clientWidth + 2)).toBe(true);
      await page.screenshot({ path: info.outputPath(`offline-sync-conflict-${width}.png`), fullPage: true });
    }
    await ack.check(); await panel.getByRole('button', { name: '应用已核对的候选', exact: true }).click();
    await expect(panel.getByText(/原章节写入已确认/)).toBeVisible(); expect(applies).toHaveLength(1);
    expect((await checked(await request.get(`${API}/chapters/${encodeURIComponent(chapter.id)}`, { headers }))).document).toEqual(incoming);
    expect((await checked(await request.get(`${API}/chapters/${encodeURIComponent(other.id)}`, { headers }))).content).toContain('MUST_NEVER_APPEAR_IN_ENVELOPE');
    await panel.getByLabel('停止此范围后续交换，已有下载和备份仍可能存在', { exact: true }).check(); await panel.getByRole('button', { name: '撤销此交换范围', exact: true }).click();
    await expect(panel.getByText(/后续导出、接收和应用已停止/)).toBeVisible();
    const state = await checked(await request.get(base + '/records', { headers }));
    expect((await request.post(base + '/channels/' + state.channels[0].id + '/receive', { headers, data: { expected_version: state.channels[0].version, envelope, target_chapter_id: chapter.id } })).status()).toBe(422);
  } finally { await quiet(); for (const id of projects.reverse()) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(id)}`, { headers })).status()); }
});
