// [HERMIA-FE-20261022] Real browser + isolated file-mode MOCK_PROVIDER backend.
// H-P0-01: FeatureLauncher + Ctrl+K command search via ActionRegistry.
// H-P0-02: first real chain 版本历史 → 预览 → 恢复 (new server version).
import {expect, test, type Page, type APIRequestContext} from '@playwright/test';

async function seed(request: APIRequestContext, title: string) {
  const novelRes = await request.post('/api/novels', {data: {title}});
  expect(novelRes.ok(), await novelRes.text()).toBeTruthy();
  const novel = await novelRes.json() as {id: string};
  const chRes = await request.post(`/api/novels/${novel.id}/chapters`, {data: {title: '第一章 雾港'}});
  expect(chRes.ok(), await chRes.text()).toBeTruthy();
  const ch = await chRes.json() as {id: string; version: number};
  let cur = await (await request.put(`/api/chapters/${ch.id}`, {data: {content: '第一版：夜里的码头没有灯。', version: ch.version, source: 'USER'}})).json() as {version: number};
  cur = await (await request.put(`/api/chapters/${ch.id}`, {data: {content: '第二版：雾像潮水一样漫上栈桥。', version: cur.version, source: 'USER'}})).json() as {version: number};
  return {novel, ch, version: cur.version};
}

/** File backend may resume last workspace — skip home if already inside a novel. */
async function openNovel(page: Page, title: string) {
  await page.goto('/', {waitUntil: 'domcontentloaded'});
  const home = page.getByRole('heading', {name: '本机作品'});
  const launcher = page.locator('.feature-launcher');
  const switcher = page.getByRole('button', {name: '切换本机作品'});
  await Promise.race([
    home.waitFor({state: 'visible', timeout: 30_000}).catch(() => {}),
    launcher.waitFor({state: 'visible', timeout: 30_000}).catch(() => {}),
  ]);
  if (await launcher.isVisible().catch(() => false)) {
    const crumb = page.getByLabel('当前创作范围');
    if (await crumb.getByText(title, {exact: false}).isVisible().catch(() => false)) return;
    if (await switcher.isVisible().catch(() => false)) {
      await switcher.click();
      await expect(home).toBeVisible({timeout: 15_000});
    }
  }
  if (await home.isVisible().catch(() => false)) {
    await page.getByRole('button', {name: title, exact: true}).click();
  }
  await expect(launcher).toBeVisible({timeout: 30_000});
}

for (const vp of [{width: 1366, height: 768}, {width: 1440, height: 900}, {width: 1920, height: 1080}]) {
  test(`launcher + command search route through registry @${vp.width}x${vp.height}`, async ({page, request}) => {
    await page.setViewportSize(vp);
    const title = `Hermia 工作台 ${vp.width} ${Date.now()}`;
    const {novel} = await seed(request, title);
    await openNovel(page, title);
    await page.getByRole('button', {name: '打开功能导航'}).click();
    await page.getByRole('navigation', {name: '功能面板导航'}).getByRole('button', {name: '一致性检查'}).click();
    await page.getByRole('button', {name: '打开功能导航'}).click();
    await expect(page.getByRole('navigation', {name: '功能面板导航'}).getByRole('button', {name: '一致性检查'})).toHaveAttribute('aria-current', 'page');
    await page.keyboard.press('Escape');
    await page.getByRole('button', {name: /搜索功能/}).click();
    const box = page.getByRole('textbox', {name: '搜索功能'});
    await expect(box).toBeVisible();
    await box.fill('版本');
    await box.press('Enter');
    await expect(page.getByRole('dialog', {name: '搜索功能与命令'})).toHaveCount(0);
    await page.getByRole('button', {name: '打开功能导航'}).click();
    await expect(page.getByRole('navigation', {name: '功能面板导航'}).getByRole('button', {name: '版本历史'})).toHaveAttribute('aria-current', 'page');
    await page.keyboard.press('Escape');
    await page.screenshot({path: `/workspace/hr/hermia_e2e_launcher_${vp.width}x${vp.height}.png`});
    await request.delete(`/api/novels/${novel.id}`);
  });
}

test('first real chain: 版本历史 → 预览 → 恢复 creates a new server version', async ({page, request}) => {
  await page.setViewportSize({width: 1440, height: 900});
  const title = `Hermia 恢复链 ${Date.now()}`;
  const {novel, ch, version} = await seed(request, title);
  await openNovel(page, title);
  await page.getByRole('button', {name: /搜索功能/}).click();
  await page.getByRole('textbox', {name: '搜索功能'}).fill('版本历史');
  await page.getByRole('option', {name: '打开：版本历史'}).click();
  const timeline = page.getByRole('navigation', {name: '版本记录时间线'});
  await expect(timeline).toBeVisible({timeout: 20_000});
  const buttons = timeline.getByRole('button');
  expect(await buttons.count()).toBeGreaterThanOrEqual(2);
  await buttons.last().click();
  await expect(page.getByRole('button', {name: '预览并恢复此版本'})).toBeVisible();
  await page.getByRole('button', {name: '预览并恢复此版本'}).click();
  const reqs: string[] = [];
  page.on('request', r => { if (r.method() === 'POST' && /\/history\/\d+\/restore/.test(r.url())) reqs.push(r.url()); });
  await page.getByRole('button', {name: '恢复此版本'}).click();
  await expect(page.getByText('恢复完成，所选内容已成为新的当前版本。')).toBeVisible({timeout: 15_000});
  expect(reqs.length).toBe(1);
  expect(reqs[0]).toContain(`expected_version=${version}`);
  const after = await (await request.get(`/api/chapters/${ch.id}`)).json() as {version: number};
  expect(after.version).toBeGreaterThan(version);
  await page.screenshot({path: '/workspace/hr/hermia_e2e_restore_1440x900.png'});
  await request.delete(`/api/novels/${novel.id}`);
});
