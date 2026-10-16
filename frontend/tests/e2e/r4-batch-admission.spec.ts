import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(response: APIResponse) { expect(response.ok(), await response.text()).toBeTruthy(); return response.json(); }
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '安全批处理', exact: true }).click();
}
test('U16 B01 parameters, original broker media receipt, separate review and satisfied-result skip', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File API + React with shipped deterministic image adapter and real broker ledger. No real model, audio endpoint, paid request or credential. Authored here; local Chromium remains NOT_RUN.' });
  try {
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByPlaceholder('小说名称').fill('U16 synthetic admission browser');
    const creating = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await body(await creating)).id;
    const chapter = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: '准入合成章', content: 'the the 原创软件测试，海面很平静。' } }));
    const base = `${API}/novels/${nid}/experimental`;
    const entry = (await body(await request.get(`${base}/template-library`, { headers }))).items.find((x: any) => x.package.manifest.type === 'safe_batch');
    const preset = await body(await request.post(`${base}/template-library/instances`, { headers, data: { package_id: entry.id, package_digest: entry.digest, request_id: 'browser-batch-preset' } }));
    const brief = await body(await request.post(`${base}/media/cover-briefs`, { headers, data: { title: '合成媒体准入简报', chapter_ids: [chapter.id] } }));
    const route = (await body(await request.get(`${base}/model-broker/status`, { headers }))).candidates.find((x: any) => x.adapter_id === 'mock-image-v1');
    const admission = await body(await request.post(`${base}/model-broker/preview`, { headers, data: { capability: 'IMAGE', chapter_ids: [chapter.id], policy: 'CUSTOM', preferred_route: route.route_id, profile: 'LOCAL_ONLY', max_cost_microusd: 0, allow_synthetic: true } }));
    await page.reload(); await open(page);
    const panel = page.getByRole('region', { name: '安全批处理与执行预检', exact: true });
    await panel.getByLabel('本项目批处理参数模板').selectOption(preset.id);
    await panel.getByLabel(/准入合成章 · v/).check();
    await expect(panel.getByLabel('批次导出格式')).toBeDisabled();
    await panel.getByLabel('媒体来源简报').selectOption(brief.id);
    await panel.getByLabel('原 Broker 媒体准入预检').selectOption(admission.id);
    const preflighting = page.waitForResponse(r => r.url().endsWith('/safe-batches/preflight'));
    await panel.getByRole('button', { name: '仅预检所选批次', exact: true }).click(); const preview = await body(await preflighting);
    expect(preview.preset.id).toBe(preset.id); expect(preview.items).toHaveLength(3);
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(0);
    const record = panel.getByRole('article', { name: `批次 ${preview.id}`, exact: true });
    await record.getByLabel('已核对本批次来源版本、权限、资源与 0 USD 预算').check();
    await record.getByRole('button', { name: '确认此批次快照与预算' }).click();
    for (let index = 0; index < 3; index++) {
      const executing = page.waitForResponse(r => r.url().endsWith('/dispatch-next'));
      await record.getByRole('button', { name: '执行下一阶段', exact: true }).click(); const done = await body(await executing);
      expect(done.items[index].status).toBe('COMPLETED');
      if (index < 2) expect(done.items[index + 1].status).toBe('PENDING');
    }
    await record.getByRole('button', { name: '预览媒体候选', exact: true }).click();
    await expect(record.getByRole('img', { name: '实际解码的媒体候选' })).toBeVisible();
    await record.getByLabel('已预览并确认将此媒体候选登记为正式资产').check();
    const accepting = page.waitForResponse(r => r.url().endsWith('/approve-media'));
    await record.getByRole('button', { name: '确认接受此媒体候选', exact: true }).click(); await body(await accepting);
    const ledger = (await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger;
    expect(ledger).toHaveLength(1); expect(ledger[0].status).toBe('SETTLED'); expect(ledger[0].actual_microusd).toBe(0);
    await record.getByText('查看原审批与后续重试审批记录', { exact: true }).click();
    await expect(record).toContainText('approved_version');
    const skipping = page.waitForResponse(r => r.url().endsWith('/safe-batches/preflight'));
    await panel.getByRole('button', { name: '仅预检所选批次', exact: true }).click(); const skipped = await body(await skipping);
    expect(skipped.items.map((x: any) => x.status)).toEqual(['SKIPPED', 'SKIPPED', 'SKIPPED']);
    expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(1);
    await page.screenshot({ path: info.outputPath('batch-original-admission-and-satisfied-skip.png'), fullPage: true });
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status()); }
});
