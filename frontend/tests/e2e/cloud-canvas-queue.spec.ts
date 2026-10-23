import {expect, test, type Locator, type Page} from '@playwright/test';
import {mkdir} from 'node:fs/promises';

const output = '/workspace/cloud-development-20261023/visual';
const jobId = 'fixture-queued-job';
const prompt = '仅前端模拟：雾港码头，冷灰蓝，一盏煤油灯。';
const viewports = [{width: 1366, height: 768}, {width: 1440, height: 900}, {width: 1920, height: 1080}];

async function frontendHttpFixture(page: Page) {
  const state = {created: [] as Record<string, unknown>[], execute: [] as string[], unexpected: [] as string[]};
  const jobs: Record<string, unknown>[] = [];
  await page.route('**/api/**', async route => {
    const request = route.request();
    const pathname = new URL(request.url()).pathname;
    const json = (body: unknown, status = 200) => route.fulfill({status, contentType: 'application/json', body: JSON.stringify(body)});
    if (pathname === '/api/asset-providers' && request.method() === 'GET') return json({items: [{
      provider_id: 'fixture-local', display_name: '前端模拟本地服务', default_model: 'fixture-model',
      configured: true, registered: true, reachable: true, local: true,
    }]});
    if (pathname === '/api/novels/fixture-project/image-jobs') {
      if (request.method() === 'GET') return json({items: jobs});
      if (request.method() === 'POST') {
        const body = request.postDataJSON() as Record<string, unknown>;
        state.created.push(body);
        const job = {...body, id: jobId, status: 'QUEUED', approval_status: 'PENDING', attempt: 0};
        jobs.push(job);
        return json(job, 202);
      }
    }
    if (pathname.endsWith('/execute')) {
      state.execute.push(pathname);
      return json({detail: 'This frontend fixture never executes providers.'}, 409);
    }
    if (request.method() === 'GET' && [
      '/api/novels/fixture-project/image-generations', '/api/novels/fixture-project/visual-references',
    ].includes(pathname)) return json({items: []});
    state.unexpected.push(`${request.method()} ${pathname}`);
    return json({detail: 'Unexpected API in frontend-only fixture.'}, 404);
  });
  return state;
}

async function reachable(control: Locator, viewport: {width: number; height: number}) {
  await control.scrollIntoViewIfNeeded();
  await expect(control).toBeInViewport();
  const box = await control.boundingBox();
  expect(box).not.toBeNull();
  expect(box!.x).toBeGreaterThanOrEqual(-1);
  expect(box!.y).toBeGreaterThanOrEqual(-1);
  expect(box!.x + box!.width).toBeLessThanOrEqual(viewport.width + 1);
  expect(box!.y + box!.height).toBeLessThanOrEqual(viewport.height + 1);
  return box;
}

for (const viewport of viewports) {
  test(`frontend HTTP fixture: node prompt → queued ID, no execution @${viewport.width}x${viewport.height}`, async ({page}, testInfo) => {
    testInfo.annotations.push({type: 'scope', description: 'Frontend component and HTTP simulation only; not File/provider/media execution acceptance.'});
    await page.setViewportSize(viewport);
    const state = await frontendHttpFixture(page);
    await page.goto('/tests/fixtures/cloud-canvas-queue.html', {waitUntil: 'domcontentloaded'});
    await expect(page.getByTestId('frontend-fixture-banner')).toContainText('仅前端模拟接口');
    await page.evaluate(() => document.fonts.ready);
    const canvas = page.getByRole('application', {name: '图片无限画布'});
    await expect(canvas).toBeVisible();
    await canvas.click({button: 'right', position: {x: 140, y: 110}});
    await page.locator('[data-add-node-menu="rebuild"] [data-node-type="image_generate"]').click();
    await canvas.locator('[data-node-id]').click({position: {x: 40, y: 20}});
    const nodePrompt = page.getByLabel('本次提示词', {exact: true});
    await nodePrompt.fill(prompt);
    const geometry: Record<string, unknown> = {nodePrompt: await reachable(nodePrompt, viewport)};
    const prepare = page.getByRole('button', {name: '为此节点准备图片任务', exact: true});
    geometry.prepare = await reachable(prepare, viewport);
    expect(state.created).toHaveLength(0);
    await mkdir(output, {recursive: true});
    await page.screenshot({path: `${output}/canvas-parameters-${viewport.width}x${viewport.height}.png`});
    await prepare.click();
    const drawer = page.getByRole('complementary', {name: '画布图片任务', exact: true});
    await expect(drawer).toBeVisible();
    await expect(drawer.getByLabel('本次节点提示词', {exact: true})).toHaveValue(prompt);
    const service = drawer.getByLabel('画布任务图片服务', {exact: true});
    await expect(service).toBeEnabled();
    geometry.service = await reachable(service, viewport);
    const save = drawer.getByRole('button', {name: '保存到生成队列', exact: true});
    await expect(save).toBeDisabled();
    await service.selectOption('fixture-local');
    const model = drawer.getByLabel('画布任务模型', {exact: true});
    await expect(model).toHaveValue('fixture-model');
    await model.fill('fixture-model-confirmed');
    geometry.model = await reachable(model, viewport);
    await drawer.getByText('生成参数', {exact: true}).click();
    geometry.width = await reachable(drawer.getByLabel('队列图片宽度', {exact: true}), viewport);
    geometry.save = await reachable(save, viewport);
    await expect(save).toBeEnabled();
    await save.click();
    const returnedId = drawer.getByText(`任务 ID：${jobId}`, {exact: true});
    await expect(returnedId).toBeVisible();
    geometry.returnedId = await reachable(returnedId, viewport);
    await reachable(drawer.getByRole('button', {name: '执行任务', exact: true}), viewport);
    expect(state.created).toHaveLength(1);
    expect(state.created[0]).toMatchObject({novel_id: 'fixture-project', provider_id: 'fixture-local', model_id: 'fixture-model-confirmed', prompt, allow_cloud_prompt: false,
      parameters: {width: 1024, height: 1024, steps: 28, seed: 1}});
    expect(state.execute).toHaveLength(0);
    expect(state.unexpected).toEqual([]);
    const overflow = await page.evaluate(() => ({
      viewportWidth: window.innerWidth,
      documentWidth: document.documentElement.scrollWidth,
      drawerWidth: document.querySelector('.rb-drawer')!.clientWidth,
      drawerScrollWidth: document.querySelector('.rb-drawer')!.scrollWidth,
    }));
    expect(overflow.documentWidth).toBeLessThanOrEqual(overflow.viewportWidth + 1);
    expect(overflow.drawerScrollWidth).toBeLessThanOrEqual(overflow.drawerWidth + 1);
    await page.screenshot({path: `${output}/canvas-queued-${viewport.width}x${viewport.height}.png`});
    await testInfo.attach('frontend-fixture-geometry.json', {body: JSON.stringify({viewport, geometry, overflow, created: state.created.length, execute: state.execute.length}, null, 2), contentType: 'application/json'});
  });
}
