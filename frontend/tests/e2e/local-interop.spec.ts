import { expect, test, type Locator, type Page } from '@playwright/test';
const session = 'interop-browser-mock-session';
const scope = { workspaceId: 'interop-browser-workspace', projectId: 'interop-browser-book', storylineId: 'interop-browser-story', branchId: 'interop-browser-branch' };
const headers = { 'X-Session-Token': session, 'X-Branch-Id': scope.branchId };
const tutor = 'http://127.0.0.1:8052';
async function enableIntegration(page: Page, dialog: Locator) {
  const toggle = dialog.getByRole('checkbox', { name: 'Enable Local Tutor Integration' });
  await expect(toggle).not.toBeChecked();
  // This controlled switch deliberately waits for Host acknowledgment. A check()
  // action incorrectly requires optimistic state before the network roundtrip.
  const acknowledged = page.waitForResponse(response => response.url().endsWith('/api/local-interop/settings') && response.request().method() === 'POST');
  await toggle.click();
  const receipt = await acknowledged; expect(receipt.ok()).toBe(true); expect((await receipt.json()).enabled).toBe(true);
  await expect(toggle).toBeChecked();
}
async function enabledConnection(page: Page) {
  await page.getByRole('button', { name: '问助手', exact: true }).click();
  const dialog = page.getByRole('dialog', { name: '问助手 · Local Tutor' });
  await enableIntegration(page, dialog);
  await dialog.getByRole('textbox', { name: '开发用本机 Tutor 地址' }).fill(tutor);
  await dialog.getByRole('button', { name: '连接本机 Tutor', exact: true }).click();
  await expect(dialog.getByText('Synthetic Tutor (MOCK_ONLY)', { exact: true })).toBeVisible();
  return dialog;
}
test.beforeEach(async ({ page }) => {
  await page.addInitScript(({ scope, session }) => { localStorage.setItem('studio.session', session); localStorage.setItem('studio.scope', JSON.stringify(scope)); }, { scope, session });
  const result = await page.request.post('/api/local-interop/settings', { headers, data: { enabled: false } });
  expect(result.ok()).toBe(true);
  await page.goto('/'); await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toBeVisible();
});

test('real App → host → synthetic Tutor metadata, explicit send and host-authorized read-only navigation', async ({ page }, info) => {
  info.annotations.push({ type: 'boundary', description: 'MOCK_ONLY peer, real Studio App and host, real two-process loopback handshake. Actual Tutor Desktop/Windows Named Pipe LOCAL_REQUIRED.' });
  const requests: string[] = []; page.on('request', request => { if (request.method() !== 'GET') requests.push(new URL(request.url()).pathname); });
  const before = await page.getByRole('textbox', { name: '章节正文', exact: true }).innerText();
  const dialog = await enabledConnection(page);
  await expect(dialog.getByRole('checkbox', { name: '选中文本', exact: true })).not.toBeChecked();
  await expect(dialog.getByRole('checkbox', { name: '当前章节', exact: true })).not.toBeChecked();
  await expect(dialog.getByRole('checkbox', { name: '其他资料（明确选择章节）', exact: true })).not.toBeChecked();
  const receipt = page.waitForResponse(response => response.url().endsWith('/context/preview'));
  await dialog.getByRole('button', { name: '生成共享预览', exact: true }).click();
  const capsule = (await (await receipt).json()).capsule;
  expect(capsule.content.level).toBe('NONE'); expect(capsule.content.text).toBeNull();
  expect(JSON.stringify(capsule)).not.toContain(before);
  expect(requests).not.toContain('/api/local-interop/ask');
  await page.screenshot({ path: info.outputPath('metadata-confirmation.png'), fullPage: true });
  await dialog.getByRole('button', { name: '确认并发送给 Tutor', exact: true }).click();
  await expect(dialog.getByText('MOCK_ONLY: structured local guidance', { exact: true })).toBeVisible();
  expect(requests).not.toContain('/api/local-interop/handoff');
  await page.screenshot({ path: info.outputPath('readonly-guidance.png'), fullPage: true });
  await dialog.getByRole('button', { name: '核对并打开目标', exact: true }).click();
  await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.locator('.app-shell[data-module="CONTROL"]')).toBeVisible();
  await expect(page.getByRole('tab', { name: '模型中心', exact: true })).toHaveAttribute('aria-selected', 'true');
  expect(requests.filter(path => /\/generate\/|\/accept$|\/execute$|\/start$/.test(path))).toEqual([]);
});

test('actual TipTap selection produces exact saved text and Unicode offset preview', async ({ page }, info) => {
  const editor = page.getByRole('textbox', { name: '章节正文', exact: true });
  await expect(editor).toContainText('合成😀选区');
  let selected = '';
  // The editor may be rehydrated after first becoming visible. Re-select through
  // actual keyboard input until the CURRENT editor owns the observed range.
  await expect(async () => {
    await editor.click();
    expect(await editor.evaluate(element => element.contains(document.activeElement))).toBe(true);
    await page.keyboard.press('Control+Home'); await page.keyboard.down('Shift');
    try { for (let i = 0; i < 5; i++) await page.keyboard.press('ArrowRight'); }
    finally { await page.keyboard.up('Shift'); }
    selected = await page.evaluate(() => window.getSelection()?.toString() ?? '');
    expect(selected.length).toBeGreaterThan(0);
    expect(selected).toBe('合成😀选区');
    expect(await editor.evaluate(element => {
      const range = window.getSelection();
      return !!range && !range.isCollapsed && element.contains(range.anchorNode) && element.contains(range.focusNode);
    })).toBe(true);
  }).toPass({ timeout: 10_000, intervals: [100, 250, 500] });
  const dialog = await enabledConnection(page);
  await dialog.getByRole('checkbox', { name: '选中文本', exact: true }).check();
  await expect(dialog.getByLabel('当前编辑器选区')).toHaveText(selected!);
  const response = page.waitForResponse(response => response.url().endsWith('/context/preview'));
  await dialog.getByRole('button', { name: '生成共享预览', exact: true }).click();
  const preview = await (await response).json();
  expect(preview.capsule.content.level).toBe('SELECTED_TEXT'); expect(preview.capsule.content.text).toBe(selected);
  expect(preview.capsule.selection_hash).toMatch(/^[0-9a-f]{64}$/);
  await page.screenshot({ path: info.outputPath('selection-confirmation.png'), fullPage: true });
  await dialog.getByRole('button', { name: '取消共享', exact: true }).click();
  await expect(dialog.getByRole('button', { name: '确认并发送给 Tutor', exact: true })).toHaveCount(0);
  await dialog.getByRole('button', { name: '关闭并断开', exact: true }).click();
  await expect(editor).toHaveText(/合成😀选区与上下文/);
});

test('diagnostic removal preview shares no hidden project context and remains explicitly confirmed', async ({ page }) => {
  const dialog = await enabledConnection(page); await dialog.getByRole('button', { name: '共享诊断', exact: true }).click();
  await dialog.getByRole('checkbox', { name: '软件 ID', exact: true }).uncheck();
  await dialog.getByRole('checkbox', { name: '当前功能', exact: true }).uncheck();
  const response = page.waitForResponse(response => response.url().endsWith('/diagnostics/preview'));
  await dialog.getByRole('button', { name: '生成诊断预览', exact: true }).click();
  const value = await (await response).json();
  expect(value.diagnostic.software_id).toBeNull(); expect(value.diagnostic.feature).toBeNull();
  expect(value.capsule.project_id).toBeNull(); expect(value.capsule.chapter_id).toBeNull();
  await expect(dialog.getByLabel('待确认的 Diagnostic Capsule')).toContainText('"context"');
  await dialog.getByRole('button', { name: '确认并发送给 Tutor', exact: true }).click();
  await expect(dialog.getByText('MOCK_ONLY: structured local guidance', { exact: true })).toBeVisible();
});

test('Tutor absent leaves Studio usable and close restores the shared entry', async ({ page }) => {
  await page.getByRole('button', { name: '问助手', exact: true }).click();
  const dialog = page.getByRole('dialog'); await enableIntegration(page, dialog);
  await dialog.getByRole('textbox', { name: '开发用本机 Tutor 地址' }).fill('http://127.0.0.1:9');
  await dialog.getByRole('button', { name: '连接本机 Tutor', exact: true }).click();
  await expect(dialog.getByRole('alert')).toBeVisible();
  await page.keyboard.press('Escape'); await expect(page.getByRole('dialog')).toHaveCount(0);
  await expect(page.getByRole('textbox', { name: '章节正文', exact: true })).toBeVisible();
  await expect(page.getByRole('button', { name: '问助手', exact: true })).toBeFocused();
});

for (const viewport of [{ width: 1366, height: 768 }, { width: 1440, height: 900 }, { width: 1920, height: 1080 }]) {
  test(`Tutor dialog geometry and keyboard focus ${viewport.width}x${viewport.height}`, async ({ page }, info) => {
    await page.setViewportSize(viewport); const dialog = await enabledConnection(page);
    await dialog.getByRole('button', { name: '集成设置', exact: true }).click();
    const bounds = await dialog.boundingBox(); expect(bounds).toBeTruthy();
    expect(bounds!.x).toBeGreaterThanOrEqual(0); expect(bounds!.y).toBeGreaterThanOrEqual(0);
    expect(bounds!.x + bounds!.width).toBeLessThanOrEqual(viewport.width);
    expect(bounds!.y + bounds!.height).toBeLessThanOrEqual(viewport.height);
    await expect(page.locator('.global-header')).toHaveCSS('height', '56px');
    await expect(page.locator('.context-bar')).toHaveCSS('height', '44px');
    await expect(page.locator('.status-bar')).toHaveCSS('height', '32px');
    await dialog.getByRole('button', { name: '关闭本机 Tutor', exact: true }).focus(); await page.keyboard.press('Shift+Tab');
    await expect(dialog.getByRole('button', { name: '关闭并断开', exact: true })).toBeFocused();
    await page.screenshot({ path: info.outputPath('integration-settings.png'), fullPage: true });
  });
}


test('ongoing metadata events require their own preview and confirmation, preserve exclusions, and stop for diagnostics', async ({ page }, info) => {
  const connectedResponse = page.waitForResponse(response => response.url().endsWith('/api/local-interop/connect'));
  const dialog = await enabledConnection(page);
  const connected = await (await connectedResponse).json();
  const eventState = async () => (await page.request.get(`/api/local-interop/events?session_id=${encodeURIComponent(connected.session_id)}`, { headers })).json();
  await expect(dialog.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）', exact: true })).not.toBeChecked();
  expect(await eventState()).toMatchObject({ events: [], subscription_active: false });
  await dialog.getByRole('button', { name: '生成共享预览', exact: true }).click();
  await dialog.getByRole('button', { name: '确认并发送给 Tutor', exact: true }).click();
  await expect(dialog.getByText('MOCK_ONLY: structured local guidance', { exact: true })).toBeVisible();
  expect(await eventState()).toMatchObject({ events: [], subscription_active: false });
  await dialog.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）', exact: true }).check();
  await dialog.getByRole('checkbox', { name: '持续共享：错误代码', exact: true }).uncheck();
  await dialog.getByRole('checkbox', { name: '持续共享：当前模型元数据', exact: true }).uncheck();
  await dialog.getByRole('checkbox', { name: '持续共享：当前模型运行状态', exact: true }).uncheck();
  await dialog.getByRole('button', { name: '预览持续状态共享', exact: true }).click();
  await expect(dialog.getByLabel('持续状态共享预览')).toBeVisible();
  expect(await eventState()).toMatchObject({ events: [], subscription_active: false });
  await dialog.getByRole('button', { name: '确认开启本次会话持续共享', exact: true }).click();
  await expect(dialog.getByLabel('正在共享的状态类别')).toContainText('当前任务状态');
  await expect(dialog.getByLabel('正在共享的状态类别')).not.toContainText('错误代码');
  const received = await eventState(); expect(received.subscription_active).toBe(true); expect(received.events.length).toBeGreaterThan(0);
  for (const event of received.events) {
    expect(event.context.content.level).toBe('NONE');
    for (const field of ['error_code', 'model_id', 'runtime_id', 'runtime_status']) expect(event.context[field] ?? null).toBeNull();
  }
  await page.screenshot({ path: info.outputPath('explicit-ongoing-consent.png'), fullPage: true });
  await dialog.getByRole('button', { name: '共享诊断', exact: true }).click();
  await dialog.getByRole('checkbox', { name: '软件 ID', exact: true }).uncheck();
  const diagnosticResponse = page.waitForResponse(response => response.url().endsWith('/diagnostics/preview'));
  await dialog.getByRole('button', { name: '生成诊断预览', exact: true }).click();
  const diagnostic = await (await diagnosticResponse).json(); expect(diagnostic.event_subscription_paused).toBe(true); expect(diagnostic.diagnostic.software_id).toBeNull();
  await expect(dialog.getByText('持续共享关闭', { exact: true })).toBeVisible();
  expect(await eventState()).toMatchObject({ events: [], subscription_active: false });
  await dialog.getByRole('button', { name: '确认并发送给 Tutor', exact: true }).click();
  await expect(dialog.getByText('MOCK_ONLY: structured local guidance', { exact: true })).toBeVisible();
  expect(await eventState()).toMatchObject({ events: [], subscription_active: false });
});

test('explicit ongoing-sharing Stop revokes the grant and reconnect never restores it', async ({ page }) => {
  const connectResponse = page.waitForResponse(response => response.url().endsWith('/api/local-interop/connect'));
  const dialog = await enabledConnection(page); const connected = await (await connectResponse).json();
  await dialog.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）', exact: true }).check();
  await dialog.getByRole('button', { name: '预览持续状态共享', exact: true }).click();
  await dialog.getByRole('button', { name: '确认开启本次会话持续共享', exact: true }).click();
  await expect(dialog.getByLabel('正在共享的状态类别')).toBeVisible();
  await dialog.getByRole('button', { name: '停止持续状态共享', exact: true }).click();
  await expect(dialog.getByText('持续共享关闭', { exact: true })).toBeVisible();
  const events = await (await page.request.get(`/api/local-interop/events?session_id=${encodeURIComponent(connected.session_id)}`, { headers })).json();
  expect(events).toMatchObject({ events: [], subscription_active: false });
  await dialog.getByRole('button', { name: '断开连接', exact: true }).click();
  await dialog.getByRole('button', { name: '连接本机 Tutor', exact: true }).click();
  await expect(dialog.getByText('Synthetic Tutor (MOCK_ONLY)', { exact: true })).toBeVisible();
  await expect(dialog.getByRole('checkbox', { name: '准备持续共享状态（需另行预览和确认）', exact: true })).not.toBeChecked();
  await expect(dialog.getByText('持续共享关闭', { exact: true })).toBeVisible();
});
