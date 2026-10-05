import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function checked(response: APIResponse): Promise<any> {
  expect(response.ok(), `HTTP ${response.status()}: ${await response.text()}`).toBeTruthy(); return response.json();
}
async function open(page: Page) {
  await page.getByRole('button', { name: /功能导航/ }).first().click();
  const group = page.getByRole('button', { name: /^Experimental/ });
  if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
  await page.getByRole('button', { name: '实验工作台', exact: true }).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '多语言版本与术语', exact: true }).click();
}

test('B05 real File/React bilingual edition: approved terms, exact paragraphs, UTF-8 RTL export and stale-source recovery', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  const modelCalls: string[] = [];
  page.on('request', request => { if (request.method() === 'POST' && /\/(?:author-context\/generate|generate\/)/.test(request.url())) modelCalls.push(request.url()); });
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Authored real File/React multilingual manual workflow. No response mocks, translation model, paid calls or language-quality claims. Local browser NOT_RUN where launch EPERM is established; hosted result must be observed separately.' });
  try {
    await page.goto('/'); await page.getByPlaceholder('小说名称').fill(`B05 synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await created)).id;
    const chapter = await checked(await page.request.post(`${API}/novels/${nid}/chapters`, { data: { title: '合成多语章节', content: '阿青🙂é来到港口。\n\n船长保留原位。\n\n第三段：钟声响起。' } }));
    await page.reload(); await open(page);
    await page.getByLabel('语言版本名称', { exact: true }).fill('Arabic synthetic edition');
    await page.getByLabel('目标语言代码', { exact: true }).fill('ar');
    await page.getByLabel(/合成多语章节 · v/).check();
    await page.getByRole('button', { name: '创建语言版本', exact: true }).click();
    await expect(page.getByLabel('第 1 段译文', { exact: true })).toHaveAttribute('dir', 'rtl');
    await expect(page.getByText('未配置已授权的翻译 Adapter。', { exact: false })).toBeVisible();
    await page.getByLabel('源术语', { exact: true }).fill('阿青');
    await page.getByLabel('首选译法', { exact: true }).fill('تشينغ');
    await page.getByLabel('翻译策略', { exact: true }).selectOption('transliteration');
    await page.getByLabel('禁用译法，每行一个', { exact: true }).fill('WrongName');
    await page.getByRole('button', { name: '保存术语草稿', exact: true }).click();
    await page.getByRole('button', { name: '批准此术语规则', exact: true }).click();
    await expect(page.getByText('规则已批准，已接受译文需要重新审核。', { exact: true })).toBeVisible();
    for (let i = 0; i < 3; i++) {
      await page.getByLabel('编辑译文段落', { exact: true }).selectOption(String(i));
      await page.getByLabel(`第 ${i + 1} 段译文`, { exact: true }).fill(i === 0 ? 'تشينغ وصل إلى الميناء 🙂é' : `فقرة عربية ${i + 1} 🙂é`);
      await page.getByRole('button', { name: '保存本段草稿', exact: true }).click();
      await expect(page.getByRole('button', { name: '提交本段审核', exact: true })).toBeEnabled();
      await page.getByRole('button', { name: '提交本段审核', exact: true }).click();
      await expect(page.getByRole('button', { name: '预检本段术语与版本', exact: true })).toBeEnabled();
      await page.getByRole('button', { name: '预检本段术语与版本', exact: true }).click();
      await expect(page.getByRole('button', { name: '确认仅接受本段译文', exact: true })).toBeDisabled();
      await page.getByLabel('已人工核对本段译文、术语与源版本', { exact: true }).check();
      await page.getByRole('button', { name: '确认仅接受本段译文', exact: true }).click();
      await expect(page.getByRole('button', { name: '重新打开本段', exact: true })).toBeEnabled();
    }
    const source = await checked(await page.request.get(`${API}/chapters/${chapter.id}`));
    expect(source.version).toBe(chapter.version); expect(source.content).toContain('阿青🙂é');
    const base = `${API}/novels/${nid}/experimental/language-editions`;
    let edition = (await checked(await page.request.get(base))).items[0];
    expect(edition.checks.can_export).toBe(true); expect(edition.segments.map((s: any) => s.status)).toEqual(['ACCEPTED', 'ACCEPTED', 'ACCEPTED']);
    await page.getByLabel('语言版本导出格式', { exact: true }).selectOption('html');
    await page.getByRole('button', { name: '预检语言版本导出', exact: true }).click();
    await page.getByLabel('已核对全部译文，确认生成本地下载', { exact: true }).check();
    await page.getByRole('button', { name: '生成已审核语言文件', exact: true }).click();
    const link = page.getByRole('link', { name: /^下载 edition-/ }); await expect(link).toBeVisible();
    const text = await link.evaluate(async node => (await fetch((node as HTMLAnchorElement).href)).text());
    expect(text).toContain('lang="ar" dir="rtl"'); expect(text).toContain('تشينغ وصل إلى الميناء 🙂é'); expect(text).toContain('charset="utf-8"');
    const parsed = await page.evaluate(value => { const doc = new DOMParser().parseFromString(value, 'text/html'); return { lang: doc.documentElement.lang, dir: doc.documentElement.dir, paragraphs: doc.querySelectorAll('p').length, scripts: doc.scripts.length }; }, text);
    expect(parsed).toEqual({ lang: 'ar', dir: 'rtl', paragraphs: 3, scripts: 0 });
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height });
      const bounds = await page.locator('section[aria-label="多语言版本与术语"]').boundingBox(); expect(bounds!.width).toBeGreaterThan(200);
      await page.screenshot({ path: info.outputPath(`multilingual-rtl-${width}.png`), fullPage: true });
    }
    const changed = structuredClone(source.document); changed.content[0].content = [{ type: 'text', text: '阿青现在离开港口。' }];
    await checked(await page.request.put(`${API}/chapters/${chapter.id}`, { data: { version: source.version, document: changed } }));
    await page.getByRole('button', { name: '刷新当前语言版本', exact: true }).click();
    await expect(page.getByText('原稿版本、段落或隐私已改变。', { exact: false })).toBeVisible();
    await expect(page.getByLabel('第 3 段译文', { exact: true })).toHaveCount(0);
    await page.getByRole('button', { name: '预览重新对齐', exact: true }).click();
    await expect(page.getByText('保留原位置且内容完全一致的 2 段；', { exact: false })).toBeVisible();
    await page.getByRole('button', { name: '确认重新对齐并重新审核', exact: true }).click();
    edition = (await checked(await page.request.get(base))).items[0];
    expect(edition.segments[0].target_text).toBe(''); expect(edition.segments[1].target_text).toBe('فقرة عربية 2 🙂é');
    expect(edition.segments.every((s: any) => s.status === 'DRAFT')).toBe(true); expect(modelCalls).toEqual([]);
  } finally {
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});
