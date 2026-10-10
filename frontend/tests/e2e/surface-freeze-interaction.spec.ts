import { test, expect, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8047/api';
async function body(value: APIResponse) { expect(value.ok(), `HTTP ${value.status()}`).toBeTruthy(); return value.json(); }

test('surface interaction persists preferences, rejects stale CAS and preserves dirty navigation', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '';
  info.annotations.push({ type: 'verification', description: 'Real File persistence and original workspace UI; synthetic text, no model/production service.' });
  try {
    const novel = await body(await request.post(`${API}/novels`, { data: { title: `Surface interaction ${Date.now()}` } })); nid = novel.id;
    await body(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: '合成功能验收', content: '合成正文，不能被键盘命令修改。' } }));
    await page.goto('/');
    await page.getByRole('button', { name: '切换本机作品', exact: true }).click();
    await page.getByRole('button', { name: novel.title, exact: true }).click();
    await expect(page.locator('.ProseMirror')).toBeVisible();
    await page.keyboard.press('Control+k');
    const panel = page.getByRole('region', { name: '工作现场工具', exact: true });
    await panel.getByText('键盘与无障碍偏好', { exact: true }).click();
    await panel.getByLabel('启用当前工具内的快捷键').check();
    await panel.getByLabel('工作现场动态效果').selectOption('reduce');
    await panel.getByRole('button', { name: '保存操作偏好', exact: true }).click();
    await expect(panel.getByText('操作偏好已保存', { exact: true })).toBeVisible();
    const endpoint = `${API}/novels/${nid}/experimental/workspace/interaction`;
    const saved = await body(await request.get(endpoint));
    expect(saved.version).toBe(1); expect(saved.preferences.keyboard_enabled).toBe(true);
    expect((await request.put(endpoint, { data: { expected_version: 0, preferences: {} } })).status()).toBe(409);
    await page.reload(); await expect(page.locator('.ProseMirror')).toBeVisible();
    await page.keyboard.press('Control+k');
    await panel.getByText('键盘与无障碍偏好', { exact: true }).click();
    await expect(panel.getByLabel('启用当前工具内的快捷键')).toBeChecked();
    await expect(panel).toHaveAttribute('data-workspace-reduced-motion', 'true');
    await panel.getByRole('button', { name: '继续工作', exact: true }).click();
    await panel.getByLabel('停止点与下次要做的事').fill('未保存的合成工作现场笔记。');
    await panel.getByRole('button', { name: '搜索与命令命令', exact: true }).click();
    await expect(panel.getByRole('region', { name: '切换工作现场前确认', exact: true })).toBeVisible();
    await panel.getByRole('button', { name: '留在当前工具', exact: true }).click();
    await expect(panel.getByLabel('停止点与下次要做的事')).toHaveValue('未保存的合成工作现场笔记。');
    await panel.getByRole('button', { name: '继续工作', exact: true }).focus();
    await page.keyboard.press('Control+Shift+F');
    await panel.getByRole('button', { name: '继续切换到搜索与命令', exact: true }).click();
    await expect(panel.getByRole('button', { name: '搜索与命令', exact: true })).toHaveAttribute('aria-pressed', 'true');
    await page.screenshot({ path: info.outputPath('workspace-interaction-functional-state.png'), fullPage: true });
    expect((await body(await request.get(endpoint))).version).toBe(1);
  } finally { await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`)).status()); }
});
