import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8047/api';
async function checked(response: APIResponse) {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();
  return response.json();
}
async function openStory(page: Page, kind: string, title: string) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: '创作', exact: true });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '故事资料库', exact: true }).click();
  await page.keyboard.press('Escape');
  await page.getByRole('tab', { name: kind === 'timeline' ? '时间线' : '伏笔', exact: true }).click();
  await page.locator('.novel-story-database .novel-record-list button').filter({ hasText: title }).click();
  await expect(page.getByRole('region', { name: '故事资料版本与恢复', exact: true })).toBeVisible();
}
for (const kind of ['timeline', 'foreshadowing']) {
  test(`original ${kind} editor saves, conflicts, reviews, restores and recovers without a second record store`, async ({ page, request }, info) => {
    let nid = ''; const quiet = createPageQuiescer(page);
    info.annotations.push({ type: 'verification', description: 'Real original File owners and mounted React; synthetic text only. No mocked business responses, models or GPU.' });
    try {
      const novel = await checked(await request.post(`${API}/novels`, { data: { title: `Story versions ${kind} ${info.testId}` } })); nid = novel.id;
      await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Current writing chapter', content: 'CURRENT SYNTHETIC MANUSCRIPT' } }));
      const source = await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Exact retained source', content: 'EXACT SYNTHETIC SOURCE' } }));
      const base = `${API}/novels/${nid}/experimental/story-records/${kind}/record`;
      const title = `Original ${kind}`;
      const original = await checked(await request.put(base, { data: { record: { title, description: 'Synthetic original record', privacy_level: 'LOCAL_ONLY', ...(kind === 'timeline' ? { chapter_id: source.id, sequence: 1 } : { planted_chapter: source.number }) }, expected_digest: null, expected_version: 0 } }));
      await page.goto('/');
      await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
      await page.getByRole('button', { name: novel.title, exact: true }).click();
      await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText('CURRENT SYNTHETIC MANUSCRIPT');
      await openStory(page, kind, title);
      const surface = page.getByRole('region', { name: '故事资料版本与恢复', exact: true });
      const field = surface.getByLabel(kind === 'timeline' ? '事件标题' : '伏笔标题', { exact: true });
      const save = surface.getByRole('button', { name: kind === 'timeline' ? '保存时间线事件' : '保存伏笔', exact: true });
      await field.fill('Saved in original editor');
      const saving = page.waitForResponse(r => r.url().endsWith(`/story-records/${kind}/record`) && r.request().method() === 'PUT');
      await save.click(); const savedResponse = await saving; expect(savedResponse.status()).toBe(200); const saved = await savedResponse.json(); expect(saved.version).toBe(2);
      const publicRows = await checked(await request.get(`${API}/novels/${nid}/${kind}`));
      expect(publicRows.find((row: any) => row.id === 'record')).toEqual(saved.record);
      expect(JSON.stringify(publicRows)).not.toContain('_story_record');
      const { id: _id, privacy_status: _privacy, ...otherPayload } = saved.record;
      const other = await checked(await request.put(base, { data: { record: { ...otherPayload, title: 'Another writer' }, expected_digest: saved.digest, expected_version: saved.version } }));
      await field.fill('Retained conflict draft');
      const conflicting = page.waitForResponse(r => r.url().endsWith(`/story-records/${kind}/record`) && r.request().method() === 'PUT');
      await save.click(); expect((await conflicting).status()).toBe(409);
      await expect(field).toHaveValue('Retained conflict draft'); await expect(save).toBeDisabled();
      await expect(surface.getByRole('button', { name: '核对后保留草稿并采用最新基线' })).toHaveCount(0);
      await surface.getByRole('button', { name: '读取最新版本', exact: true }).click();
      await expect(surface.getByText('Another writer', { exact: true })).toBeVisible();
      await surface.getByRole('button', { name: '核对后保留草稿并采用最新基线', exact: true }).click();
      const retrying = page.waitForResponse(r => r.url().endsWith(`/story-records/${kind}/record`) && r.request().method() === 'PUT');
      await save.click(); const latest = await (await retrying).json(); expect(latest.version).toBe(other.version + 1);
      await surface.getByText('版本历史与人工反馈（最多 20 版）', { exact: true }).click();
      await surface.getByRole('button', { name: '预览恢复 v1', exact: true }).click();
      await surface.getByRole('button', { name: '取消恢复', exact: true }).click();
      expect((await checked(await request.get(base))).version).toBe(4);
      await surface.getByRole('button', { name: '预览恢复 v1', exact: true }).click();
      const restoring = page.waitForResponse(r => r.url().endsWith(`/story-records/${kind}/record/restore`) && r.request().method() === 'POST');
      await surface.getByRole('button', { name: '确认恢复为新版本', exact: true }).click();
      const restored = await (await restoring).json(); expect(restored.version).toBe(5); expect(restored.record).toEqual(original.record);
      await field.fill('Unsent browser recovery');
      await page.reload(); await openStory(page, kind, title);
      await surface.getByRole('button', { name: '恢复本地草稿', exact: true }).click();
      await expect(field).toHaveValue('Unsent browser recovery');
      await surface.getByRole('button', { name: '取消编辑', exact: true }).click();
      await expect(field).toHaveValue(title); expect((await checked(await request.get(base))).version).toBe(5);
      await surface.getByText('版本历史与人工反馈（最多 20 版）', { exact: true }).click();
      await surface.getByLabel('反馈决定', { exact: true }).selectOption('INTENTIONAL');
      await surface.getByLabel('反馈说明', { exact: true }).fill('Deliberate synthetic source');
      await surface.getByLabel('反馈依据', { exact: true }).fill('Exact source chapter');
      const reviewing = page.waitForResponse(r => r.url().endsWith(`/story-records/${kind}/record/feedback`) && r.request().method() === 'POST');
      await surface.getByRole('button', { name: '提交此版本人工反馈', exact: true }).click();
      expect((await reviewing).status()).toBe(200);
      await expect(surface.getByRole('button', { name: '提交此版本人工反馈', exact: true })).toBeDisabled();
      for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
        await page.setViewportSize({ width, height }); await page.emulateMedia({ reducedMotion: 'reduce' });
        await page.evaluate(() => document.fonts.ready); await field.scrollIntoViewIfNeeded();
        const metrics = await field.evaluate(element => {
          const rect = element.getBoundingClientRect(), main = element.closest('.main-workspace')!.getBoundingClientRect();
          return { left: rect.left, right: rect.right, width: rect.width, mainLeft: main.left, mainRight: main.right,
            overflow: document.documentElement.scrollWidth - innerWidth,
            header: document.querySelector('.global-header')!.getBoundingClientRect().height,
            context: document.querySelector('.context-bar')!.getBoundingClientRect().height,
            status: document.querySelector('.status-bar')!.getBoundingClientRect().height };
        });
        expect(metrics.width).toBeGreaterThan(100); expect(metrics.left).toBeGreaterThanOrEqual(metrics.mainLeft);
        expect(metrics.right).toBeLessThanOrEqual(metrics.mainRight); expect(metrics.overflow).toBeLessThanOrEqual(1);
        expect(metrics.header).toBe(56); expect(metrics.context).toBe(44); expect(metrics.status).toBe(32);
        await page.screenshot({ path: info.outputPath(`${kind}-original-owner-${width}.png`) });
      }
      await surface.getByRole('button', { name: `打开来源章节 ${source.id}`, exact: true }).click();
      await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toContainText('EXACT SYNTHETIC SOURCE');
      const receipt = await checked(await request.get(base)); expect(receipt.version).toBe(6); expect(receipt.feedback.decision).toBe('INTENTIONAL');
    } finally {
      await quiet();
      if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());
    }
  });
}
