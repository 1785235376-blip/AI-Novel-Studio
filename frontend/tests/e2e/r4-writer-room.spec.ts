import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { inflateRawSync } from 'node:zlib';
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
  await page.getByRole('navigation', { name: '实验功能' }).getByRole('button', { name: '团队审阅室', exact: true }).click();
}
function unzip(raw: Buffer) {
  const files = new Map<string, Buffer>(); let offset = 0;
  while (raw.readUInt32LE(offset) === 0x04034b50) {
    const method = raw.readUInt16LE(offset + 8), size = raw.readUInt32LE(offset + 18), nameSize = raw.readUInt16LE(offset + 26), extra = raw.readUInt16LE(offset + 28);
    const name = raw.subarray(offset + 30, offset + 30 + nameSize).toString('utf8'), begin = offset + 30 + nameSize + extra;
    const bytes = raw.subarray(begin, begin + size); files.set(name, method === 8 ? inflateRawSync(bytes) : bytes); offset = begin + size;
  }
  return files;
}

test('B08 real File/React async assignment, independent-client conflict, original comments and selected-only package', async ({ page, request }, info) => {
  const quiesce = createPageQuiescer(page); let nid = ''; const externalCalls: string[] = [];
  page.on('request', req => { if (req.method() === 'POST' && /\/(?:author-context\/generate|generate\/|invite|send)/.test(req.url())) externalCalls.push(req.url()); });
  page.on('dialog', dialog => dialog.type() === 'beforeunload' ? dialog.accept() : dialog.dismiss());
  info.annotations.push({ type: 'verification', description: 'Real File/React browser plus independent API client, no response mocks or models. Distinct trusted-session role/membership tests run in mounted File/PG suite. Local Chromium EPERM not retried; hosted execution remains NOT_RUN until observed.' });
  try {
    await page.goto('/'); await page.getByPlaceholder('小说名称').fill(`B08 synthetic ${info.testId}`);
    const created = page.waitForResponse(r => r.url().endsWith('/api/novels') && r.request().method() === 'POST');
    await page.getByRole('button', { name: '创建小说', exact: true }).click(); nid = (await checked(await created)).id;
    const chapter = await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: '合成审阅章节', content: '阿青🙂来到城门。需要讨论动机。' } }));
    await checked(await request.post(`${API}/novels/${nid}/chapters`, { data: { title: '未选私有章节', content: 'UNSELECTED_REVIEW_MARKER' } }));
    const base = `${API}/novels/${nid}/experimental/writer-room`;
    await page.reload(); await open(page);
    await page.getByLabel('新任务标题', { exact: true }).fill('合成城门审阅');
    await page.getByLabel('新任务说明', { exact: true }).fill('初始合成说明');
    await page.getByLabel('关联章节版本', { exact: true }).selectOption(chapter.id);
    await page.getByRole('button', { name: '创建协作任务', exact: true }).click();
    await expect(page.getByLabel('当前任务说明', { exact: true })).toHaveValue('初始合成说明');
    await page.getByRole('button', { name: '开始处理', exact: true }).click();
    await page.getByRole('button', { name: '提交责任人审阅', exact: true }).click();
    await expect(page.getByRole('button', { name: '请求修改并保留理由', exact: true })).toBeDisabled();
    await page.getByLabel('处理记录或修改理由', { exact: true }).fill('请解释人物为何进入城门。');
    await page.getByRole('button', { name: '请求修改并保留理由', exact: true }).click();
    await expect(page.getByRole('button', { name: '开始处理', exact: true })).toBeVisible();
    // The independent API client updates the same persisted task after this
    // browser has captured its expected version, without response interception.
    const task = (await checked(await request.get(base))).items[0];
    await page.getByLabel('当前任务说明', { exact: true }).fill('浏览器候选🙂é不能丢失');
    await checked(await request.put(`${base}/tasks/${task.id}`, { data: { title: task.title, description: '独立客户端候选', assignee: task.assignee, reviewer: task.reviewer, expected_version: task.version } }));
    await page.getByRole('button', { name: '保存任务修改', exact: true }).click();
    await expect(page.getByText(/WRITER_ROOM_VERSION_CONFLICT/)).toBeVisible();
    await expect(page.getByLabel('当前任务说明', { exact: true })).toHaveValue('浏览器候选🙂é不能丢失');
    const conflicts = (await checked(await request.get(base + '/conflicts'))).items;
    expect(conflicts[0].current_candidate.description).toBe('独立客户端候选'); expect(conflicts[0].submitted_candidate.description).toBe('浏览器候选🙂é不能丢失');
    await page.getByRole('button', { name: '核对后采用提交候选', exact: true }).click();
    await expect(page.getByText('协作任务已保存。', { exact: true })).toBeVisible();
    await page.getByRole('button', { name: '开始处理', exact: true }).click();
    await page.getByRole('button', { name: '提交责任人审阅', exact: true }).click();
    await page.getByRole('button', { name: '完成协作任务', exact: true }).click();
    await expect(page.getByRole('button', { name: '重新打开协作任务', exact: true })).toBeVisible();
    await page.getByLabel('只读审阅章节', { exact: true }).selectOption(chapter.id);
    await expect(page.getByText('阿青🙂来到城门。需要讨论动机。', { exact: true })).toBeVisible();
    await page.getByLabel('批注原文引用', { exact: true }).fill('阿青🙂'); await page.getByLabel('章节批注', { exact: true }).fill('合成版本批注');
    await page.getByRole('button', { name: '保存版本批注', exact: true }).click();
    await expect(page.getByText('local-author：合成版本批注', { exact: true })).toBeVisible();
    const original = await checked(await request.get(`${API}/novels/${nid}/review-threads`)); expect(original.items[0].messages[0].text).toBe('合成版本批注');
    await page.getByLabel(/章节：合成审阅章节 · v/).check();
    await page.getByRole('button', { name: '预览受限审阅包', exact: true }).click();
    await expect(page.getByRole('button', { name: '生成选定内容下载', exact: true })).toBeDisabled();
    await page.getByLabel('我了解下载副本无法远程撤回', { exact: true }).check();
    await page.getByRole('button', { name: '生成选定内容下载', exact: true }).click();
    const link = page.getByRole('link', { name: '下载受限审阅包', exact: true }); await expect(link).toBeVisible();
    const array = await link.evaluate(async node => Array.from(new Uint8Array(await (await fetch((node as HTMLAnchorElement).href)).arrayBuffer())));
    const files = unzip(Buffer.from(array)); expect([...files.keys()]).toEqual(['manifest.json', 'chapters/001.txt']);
    const manifest = JSON.parse(files.get('manifest.json')!.toString('utf8')); expect(manifest.chapters.map((c: any) => c.id)).toEqual([chapter.id]);
    expect(files.get('chapters/001.txt')!.toString('utf8')).toContain('阿青🙂'); expect(Buffer.concat([...files.values()]).toString('utf8')).not.toContain('UNSELECTED_REVIEW_MARKER');
    expect((await checked(await request.get(`${API}/chapters/${chapter.id}`))).version).toBe(chapter.version);
    for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
      await page.setViewportSize({ width, height }); const panel = page.locator('section[aria-label="Writer Room 异步团队审阅"]');
      expect(await panel.evaluate(node => node.scrollWidth <= node.clientWidth + 2)).toBe(true);
      await page.screenshot({ path: info.outputPath(`writer-room-${width}.png`), fullPage: true });
    }
    expect(externalCalls).toEqual([]);
  } finally {
    await quiesce(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${encodeURIComponent(nid)}`)).status());
  }
});
