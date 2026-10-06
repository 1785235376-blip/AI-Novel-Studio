import { expect, test, type APIResponse } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API = 'http://127.0.0.1:8022/api', UI = 'http://127.0.0.1:5182';
const headers = { 'X-Session-Token': 'r4-broker-test-session' };
async function body(r: APIResponse) { expect(r.ok(), `HTTP ${r.status()}: ${await r.text()}`).toBeTruthy(); return r.json(); }

test('Task Center reopens exact original Judge receipt after reload without model replay', async ({ page, request }, info) => {
  const quiet = createPageQuiescer(page); let nid = '', jobId = '';
  info.annotations.push({ type: 'verification', description: 'Original File owner/AuthorPreparer/Broker/JobManager and real React task navigation. One explicitly created shipped synthetic fixture; no response mocks, paid inference or real model quality claim.' });
  try {
    const novel = await body(await request.post(`${API}/novels`, { headers, data: { title: `Exact original Judge ${Date.now()}` } })); nid = novel.id;
    const created = await body(await request.post(`${API}/novels/${nid}/chapters`, { headers, data: { title: 'Synthetic evidence', content: '合成灯塔照亮门口。\n\n合成灯塔照亮门口。' } }));
    // Capture the original versioned document, not the legacy creation response.
    const chapter = await body(await request.get(`${API}/chapters/${created.id}`, { headers }));
    expect(Number.isInteger(chapter.version)).toBe(true); expect(chapter.version).toBeGreaterThanOrEqual(1);
    const base = `${API}/novels/${nid}/experimental`;
    const run = await body(await request.post(`${base}/narrative-judge/runs`, { headers, data: { chapter_ids: [chapter.id], expected_versions: { [chapter.id]: chapter.version }, rubric_id: 'narrative-rules-v1' } }));
    const catalog = await body(await request.get(`${base}/narrative-judge/model/catalog`, { headers }));
    const route = catalog.routes.find((r: any) => r.provider_id === 'mock' && r.synthetic && r.available); expect(route).toBeTruthy();
    const prepared = await body(await request.post(`${base}/narrative-judge/runs/${run.id}/model/preview`, { headers, data: { expected_version: run.version, route_id: route.route_id } }));
    const started = await body(await request.post(`${base}/narrative-judge/runs/${run.id}/model/dispatch`, { headers, data: { expected_version: prepared.version, reviewed_preview_digest: prepared.model_preview.preview_digest } }));
    jobId = started.model_execution.job_id;
    await expect.poll(async () => (await body(await request.get(`${base}/model-broker/jobs/${started.model_execution.reservation_id}`, { headers }))).ledger.status, { timeout: 90000 }).toBe('SETTLED');
    await body(await request.post(`${base}/narrative-judge/runs/${run.id}/model/refresh`, { headers, data: { expected_version: started.version } }));
    const task = (await body(await request.get(`${base}/workspace/tasks`, { headers }))).items.find((r: any) => r.id === jobId);
    expect(task.owner_navigation).toMatchObject({ id: jobId, task_authority: 'judge_model_job', feature: 'narrative_quality_judge_v2' });
    const sends: string[] = [];
    page.on('request', r => { if (r.method() === 'POST' && /\/model\/dispatch|\/author-context\/generate|\/generate\//.test(r.url())) sends.push(r.url()); });
    await page.setExtraHTTPHeaders(headers); await page.goto(UI);
    await page.getByRole('button', { name: '切换本机作品', exact: true }).click(); await page.getByRole('button', { name: novel.title, exact: true }).click();
    for (let visit = 0; visit < 2; visit++) {
      await page.keyboard.press('Control+k');
      await page.getByRole('navigation', { name: '工作现场工具分类' }).getByRole('button', { name: '任务中心', exact: true }).click();
      const card = page.getByRole('region', { name: '任务中心 · 原服务实时读取', exact: true }).locator('article.experimental-record').filter({ hasText: jobId });
      await card.getByRole('button', { name: '打开来源工具', exact: true }).click();
      const owner = page.getByRole('region', { name: '叙事证据审阅', exact: true });
      await expect(owner.getByLabel('查看审阅记录', { exact: true })).toHaveValue(run.id);
      await expect(owner.getByRole('region', { name: '原始模型任务状态', exact: true })).toContainText(jobId);
      if (!visit) { await quiet.drain(); await page.reload(); }
    }
    expect(sends).toEqual([]); expect((await body(await request.get(`${base}/model-broker/history`, { headers }))).ledger).toHaveLength(1);
    const afterReopening = await body(await request.get(`${API}/chapters/${chapter.id}`, { headers }));
    expect(afterReopening.version).toBe(chapter.version); expect(afterReopening.content).toBe(chapter.content);
    await page.screenshot({ path: info.outputPath('exact-judge-task-after-reload.png'), fullPage: true });
  } finally {
    if (jobId) await request.post(`${API}/generation/${jobId}/cancel`, { headers }).catch(() => {});
    await quiet(); if (nid) expect([200, 204, 404]).toContain((await request.delete(`${API}/novels/${nid}`, { headers })).status());
  }
});
