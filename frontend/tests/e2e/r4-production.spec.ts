import { expect, test, type APIResponse, type Page } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function body(response: APIResponse) { expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json(); }
async function openProduction(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '资产来源与复现', exact: true }).click();
}

test('R4 asset lineage and manifest replay use real API, existing media review and redacted export', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File API and React UI; actual deterministic synthetic PNG bytes only. No real image model, paid API, external service or automatic approval.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill('R4 synthetic production');
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    nid = (await body(await created)).id;
    const base = `${API}/novels/${nid}/experimental`;
    const upload = async (filename: string) => body(await page.request.post(`${API}/novels/${nid}/assets`, { data: { novel_id: nid, filename, content_base64: Buffer.from(`synthetic-${filename}`).toString('base64'), media_type: 'application/octet-stream' } }));
    const parent = await upload('original-fixture.bin'), child = await upload('derived-fixture.bin');
    await openProduction(page);
    await page.getByRole('button', { name: 'derived-fixture.bin · v1', exact: true }).click();
    await page.getByLabel('资产来源类型', { exact: true }).selectOption('DERIVED_PROCESSING');
    await page.getByRole('checkbox', { name: 'original-fixture.bin · v1', exact: true }).check();
    await page.getByLabel('许可声明', { exact: true }).fill('Synthetic author declaration');
    await page.getByLabel('许可来源', { exact: true }).fill('Synthetic browser fixture');
    await page.getByRole('button', { name: '保存来源声明', exact: true }).click();
    await expect(page.getByRole('region', { name: '资产来源关系图' })).toContainText('当前有效');
    const row = await body(await page.request.get(`${base}/production/assets/${child.id}`));
    expect(row.parents[0].id).toBe(parent.id); expect(row.parents[0].state).toBe('CURRENT');
    expect((await page.request.put(`${base}/production/assets/${parent.id}/lineage`, { data: { expected_version: 1, origin: 'DERIVED_PROCESSING', parent_asset_ids: [child.id] } })).status()).toBe(422);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      await expect(page.getByRole('region', { name: '资产来源关系图' })).toBeVisible();
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`production-lineage-${width}.png`) });
    }
    await body(await page.request.delete(`${API}/assets/${parent.id}?novel_id=${nid}`));
    await page.getByRole('button', { name: '重新读取资产详情', exact: true }).click();
    await expect(page.getByRole('region', { name: '资产来源关系图' })).toContainText('已删除，可恢复');
    await expect(page.getByRole('button', { name: '保存来源声明', exact: true })).toBeDisabled();
    const brief = await body(await page.request.post(`${base}/media/cover-briefs`, { data: { title: 'Synthetic source', prompt: 'PRIVATE_PROMPT_CANARY /private/local/path sk-no-real-key' } }));
    let task = await body(await page.request.post(`${base}/media/tasks`, { data: { brief_id: brief.id, expected_brief_version: 1, adapter_id: 'mock-image-v1', candidate_count: 2 } }));
    task = await body(await page.request.post(`${base}/media/tasks/${task.id}/execute`, { data: { expected_version: 1 } }));
    await page.getByRole('button', { name: '刷新清单与重放状态', exact: true }).click();
    await page.getByLabel('已完成的媒体任务', { exact: true }).selectOption(task.id);
    await page.getByRole('button', { name: '记录所选任务清单', exact: true }).click();
    await page.getByRole('button', { name: '检查重放条件', exact: true }).click();
    await expect(page.getByRole('region', { name: '重放预检' })).toContainText('可以创建新的重放任务');
    await expect(page.getByRole('region', { name: '重放预检' })).toContainText('输出逐字节一致：尚未比较');
    const replayed = page.waitForResponse(r => r.url().includes('/production/manifests/') && r.url().endsWith('/replay'));
    await page.getByRole('button', { name: '创建新的重放任务', exact: true }).click();
    const replay = await body(await replayed); expect(replay.task_id).not.toBe(task.id); expect(replay.status).toBe('QUEUED');
    await page.getByRole('button', { name: '执行这次合成重放', exact: true }).click();
    await expect(page.getByRole('region', { name: '重放历史' })).toContainText('输出逐字节一致：是');
    await expect(page.getByRole('region', { name: '重放历史' })).toContainText('PENDING_REVIEW');
    expect((await body(await page.request.get(`${API}/novels/${nid}/assets`))).length).toBe(1); // Only the pre-existing child; generated proposals were not promoted.
    const download = page.waitForEvent('download');
    await page.getByRole('button', { name: '下载脱敏生产清单', exact: true }).click();
    const file = await download, filename = await file.path(); expect(filename).toBeTruthy();
    const exported = await fs.readFile(filename!, 'utf8');
    expect(exported).not.toContain('PRIVATE_PROMPT_CANARY'); expect(exported).not.toContain('/private/'); expect(exported).not.toContain('sk-no-real-key');
    expect(JSON.parse(exported).schema).toBe('production-public-manifest-v2');
    await page.screenshot({ path: info.outputPath('production-replay-byte-equal-pending-review.png') });
    await page.reload(); await openProduction(page);
    await expect(page.getByRole('region', { name: '重放历史' })).toContainText('输出逐字节一致：是');
    await page.getByRole('button', { name: '审核重放产物', exact: true }).click();
    await expect(page.getByRole('heading', { name: /封面与分镜/ }).first()).toBeVisible();
  } finally {
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
  }
});
