import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function open(page: Page, label: string, first = false) {
  if (first) {
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click();
    await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: label, exact: true }).click();
}
test('Wave3 real research revision restoration, note editing and unconfigured vector source picker', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File API and React. Synthetic local files; no business-response mocks, cloud/model calls, or local browser claim. Hosted Chromium verification required.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill(`Wave3 references ${info.testId}`);
    const creation = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    nid = (await (await creation).json()).id;
    await open(page, '创作资料库', true);
    const panel = page.getByRole('region', { name: '分层研究资料库' });
    await panel.getByLabel('资料标题', { exact: true }).fill('Wave3 合成资料');
    await panel.getByLabel('选择本地资料文件', { exact: true }).setInputFiles({ name: 'archive.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic tide gates close at dusk.') });
    const importing = page.waitForResponse(r => r.url().endsWith('/sources/import') && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '导入所选本地文件', exact: true }).click();
    const original = await (await importing).json(); expect(original.version).toBe(1);
    await panel.getByRole('button', { name: '打开来源 Wave3 合成资料', exact: true }).click();
    await panel.getByLabel('选择引用：第 1 段', { exact: true }).check();
    await panel.getByLabel('研究笔记标题', { exact: true }).fill('Wave3 原创笔记');
    await panel.getByLabel('研究笔记内容', { exact: true }).fill('A fictional gate waits for a blue lantern.');
    await panel.getByRole('button', { name: '保存带引用的研究笔记', exact: true }).click();
    await panel.getByRole('button', { name: '编辑研究笔记 Wave3 原创笔记', exact: true }).click();
    await panel.getByLabel('研究笔记内容', { exact: true }).fill('A revised original annotation.');
    await panel.getByRole('button', { name: '保存研究笔记新版本', exact: true }).click();
    await expect(panel.getByText('A revised original annotation.', { exact: true })).toBeVisible();
    await panel.getByRole('button', { name: '编辑来源元数据', exact: true }).click();
    await panel.getByLabel('选择本地资料文件', { exact: true }).setInputFiles({ name: 'archive-v2.txt', mimeType: 'text/plain', buffer: Buffer.from('Synthetic version two closes at sunrise.') });
    const replacing = page.waitForResponse(r => r.url().endsWith(`/sources/${original.id}/file`) && r.request().method() === 'PUT');
    await panel.getByRole('button', { name: '保存资料新文件版本', exact: true }).click();
    const revised = await (await replacing).json(); expect(revised.version).toBe(2); expect(revised.content_sha256).not.toBe(original.content_sha256);
    await expect(panel.getByRole('button', { name: '修复笔记引用 Wave3 原创笔记', exact: true })).toBeVisible();
    await panel.getByRole('button', { name: '核对来源历史版本', exact: true }).click();
    await expect(panel.getByRole('button', { name: '恢复来源版本 1', exact: true })).toBeDisabled();
    await panel.getByLabel('已核对版本，恢复为新的私有来源版本并使旧引用失效', { exact: true }).check();
    const restoring = page.waitForResponse(r => r.url().endsWith(`/sources/${original.id}/restore`) && r.request().method() === 'POST');
    await panel.getByRole('button', { name: '恢复来源版本 1', exact: true }).click();
    const restored = await (await restoring).json(); expect(restored.version).toBe(3); expect(restored.access).toBe('PRIVATE'); expect(restored.content_sha256).toBe(original.content_sha256);
    const staleCitation = await request.post(`${API}/novels/${nid}/experimental/research-library/citation`, { data: original.paragraphs[0].citation });
    expect(staleCitation.status()).toBe(409);
    await open(page, '视觉 Embedding');
    await expect(page.getByText('NOT_CONFIGURED', { exact: true })).toBeVisible();
    await page.getByLabel('索引实体类型', { exact: true }).selectOption('RESEARCH');
    const picker = page.getByLabel('选择当前范围中的索引来源', { exact: true });
    const option = picker.locator('option').filter({ hasText: 'Wave3 合成资料' });
    const value = await option.getAttribute('value'); expect(value).toBeTruthy();
    await picker.selectOption(value!);
    await page.getByLabel('向量索引标题', { exact: true }).fill('Wave3 vector definition');
    const indexing = page.waitForResponse(r => r.url().endsWith('/embeddings/indexes') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '保存索引定义', exact: true }).click();
    const index = await (await indexing).json(); expect(index.status).toBe('NOT_CONFIGURED');
    await expect(page.getByRole('button', { name: '重建向量索引', exact: true })).toBeDisabled();
    await expect(page.getByRole('button', { name: '查询向量', exact: true })).toBeDisabled();
    await page.reload();
    await open(page, '视觉 Embedding', true);
    await expect(page.getByRole('heading', { name: 'Wave3 vector definition', exact: true })).toBeVisible();
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`wave3-${width}.png`) });
    }
  } finally {
    await quiet();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
  }
});
