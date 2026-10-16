import { expect, test } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8047/api';
test('hybrid Search uses original Story sources and fails honestly without a provider', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File API and React; synthetic manuscript only. No model/GPU or mocked business responses.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill(`Hybrid surface ${info.testId}`);
    const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    nid = (await (await creating).json()).id;
    const chapterResponse = await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Synthetic branchless harbor', content: 'A healer speaks to a doctor.' } });
    expect(chapterResponse.status()).toBe(201); const chapter = await chapterResponse.json();
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
    await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '视觉 Embedding', exact: true }).click();
    await expect(page.getByText('NOT_CONFIGURED', { exact: true })).toBeVisible();
    await page.getByLabel('索引实体类型', { exact: true }).selectOption('STORY');
    const picker = page.getByLabel('选择当前范围中的索引来源', { exact: true });
    const option = picker.locator('option').filter({ hasText: 'Synthetic branchless harbor' });
    await expect(option).toHaveCount(1); await picker.selectOption((await option.getAttribute('value'))!);
    await page.getByLabel('向量索引标题', { exact: true }).fill('Hybrid story source');
    const saving = page.waitForResponse(response => response.url().endsWith('/embeddings/indexes') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '保存索引定义', exact: true }).click();
    const index = await (await saving).json();
    expect(index.entities[0].entity_id).toBe(chapter.id); expect(index.status).toBe('NOT_CONFIGURED');
    await page.getByLabel('检索方式', { exact: true }).selectOption('HYBRID');
    await page.getByLabel('视觉向量查询', { exact: true }).fill('healer');
    await expect(page.getByRole('button', { name: '查询向量', exact: true })).toBeDisabled();
    await expect(page.getByText(/未验证语义质量/)).toBeVisible();
    const backend = await request.post(`${API}/novels/${nid}/experimental/embeddings/hybrid-query`, { data: { index_id: index.id, text: 'healer' } });
    expect(backend.status()).toBe(422); expect(await backend.text()).toContain('EMBEDDING_NOT_CONFIGURED');
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`hybrid-surface-${width}.png`) });
    }
    const indexes = await request.get(`${API}/novels/${nid}/experimental/embeddings/indexes`);
    expect((await indexes.json()).items.some((row: { id: string }) => row.id === index.id)).toBe(true);
  } finally {
    await quiet();
    if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
  }
});
