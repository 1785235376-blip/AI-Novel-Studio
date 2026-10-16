import { expect, test, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8019/api';
async function openPanel(page: Page, name: string) {
  if (!(await page.getByRole('navigation', { name: '实验功能' }).isVisible().catch(() => false))) {
    await page.getByRole('button', { name: /功能导航/ }).first().click();
    const group = page.getByRole('button', { name: /^Experimental/ });
    if (await group.getAttribute('aria-expanded') !== 'true') await group.click();
    await page.getByRole('button', { name: '实验工作台', exact: true }).click();
    await page.keyboard.press('Escape');
  }
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name, exact: true }).click();
}

test('Wave 4: original Shot picker, persisted brief revision, compare, approve original asset and restart view', async ({ page }, info) => {
  const quiesce = createPageQuiescer(page); let nid = '';
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Real File API/React and deterministic synthetic PNG; no image model/GPU/NLE quality claim. Hosted-browser regression, local Chromium remains NOT_RUN.' });
  try {
    await page.goto('/');
    await page.getByPlaceholder('小说名称').fill(`Wave 4 media ${info.testId}`);
    const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click();
    const novel = await (await creating).json(); nid = novel.id;
    expect((await page.request.post(`${API}/novels/${nid}/chapters`, { data: { title: 'Synthetic scene', content: 'A ship approaches the synthetic harbor.' } })).status()).toBe(201);
    let source = await (await page.request.post(`${API}/novels/${nid}/screenplays`, { data: { title: 'Synthetic original screenplay' } })).json();
    source = await (await page.request.post(`${API}/novels/${nid}/screenplays/${source.id}/approve`, { data: { expected_version: source.edit_version } })).json();
    source = await (await page.request.post(`${API}/novels/${nid}/screenplays/${source.id}/shots`, { data: { expected_version: source.edit_version } })).json();
    await openPanel(page, '封面与分镜');
    await page.getByLabel('从原剧本选择分镜来源').selectOption(source.id);
    await page.getByLabel('从原 Shot 选择分镜镜头').selectOption(source.shots[0].id);
    await page.getByLabel('媒体生成说明').fill('An establishing image, synthetic fixture only.');
    const saving = page.waitForResponse(response => response.url().endsWith('/media/storyboard-briefs') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '从 Shot 创建分镜 Brief', exact: true }).click();
    const brief = await (await saving).json(); expect(brief.shot_id).toBe(source.shots[0].id);
    await page.getByLabel('修订分镜图像说明').fill('Keep empty foreground, synthetic fixture only.');
    const revising = page.waitForResponse(response => response.url().includes(`/media/storyboard-briefs/${brief.id}`) && response.request().method() === 'PUT');
    await page.getByRole('button', { name: '保存分镜 Brief 修订', exact: true }).click();
    const revision = await (await revising).json(); expect(revision.version).toBe(2); expect(revision.history[0].version).toBe(1);
    const queueing = page.waitForResponse(response => response.url().endsWith('/media/tasks') && response.request().method() === 'POST');
    await page.getByRole('button', { name: '创建 Mock 图像任务', exact: true }).click();
    const task = await (await queueing).json(); expect(task.brief_version).toBe(2);
    await page.getByRole('button', { name: '执行 Mock 图像任务', exact: true }).click();
    await expect(page.getByRole('article', { name: '媒体候选 1', exact: true })).toBeVisible();
    await page.getByRole('checkbox', { name: 'STORYBOARD 候选 1', exact: true }).check();
    await page.getByRole('checkbox', { name: 'STORYBOARD 候选 2', exact: true }).check();
    await page.getByRole('button', { name: '比较已选媒体候选', exact: true }).click();
    await expect(page.getByRole('region', { name: '媒体候选比较', exact: true })).toContainText('未执行质量评分');
    const approving = page.waitForResponse(response => /\/media\/proposals\/[^/]+\/approve$/.test(response.url()));
    await page.getByRole('article', { name: '媒体候选 1', exact: true }).getByRole('button', { name: '批准媒体为资产', exact: true }).click();
    const approved = await (await approving).json(); expect(approved.lineage.shot_id).toBe(source.shots[0].id); expect(approved.asset_id).toBeTruthy();
    const originalAsset = await page.request.get(`${API}/assets/${approved.asset_id}`, { params: { novel_id: nid } });
    expect(originalAsset.status()).toBe(200);
    expect(await originalAsset.json()).toMatchObject({ id: approved.asset_id, novel_id: nid });
    await page.reload(); await openPanel(page, '封面与分镜');
    await expect(page.getByRole('article', { name: '媒体候选 1', exact: true })).toContainText('APPROVED');
    await expect(page.getByLabel('修订分镜图像说明')).toHaveValue('Keep empty foreground, synthetic fixture only.');
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); await page.evaluate(() => document.fonts.ready);
      expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth)).toBe(true);
      await page.screenshot({ path: info.outputPath(`media-continuation-${width}.png`) });
    }
  } finally {
    await quiesce();
    if (nid) expect([200, 204, 404]).toContain((await page.request.delete(`${API}/novels/${nid}`)).status());
  }
});
