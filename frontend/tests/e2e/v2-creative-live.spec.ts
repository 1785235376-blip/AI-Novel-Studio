import { test, expect, type APIRequestContext, type Locator, type Page, type TestInfo } from '@playwright/test';

type Row = Record<string, any>;
// The enabled tests share one real File server. Own only IDs returned by this
// test's successful create responses; never infer ownership from an inventory.
const ownedNovels = new WeakMap<APIRequestContext, Set<string>>();
const ownedPages = new WeakMap<APIRequestContext, Page>();
const manuscript = '合成验收正文：林默走到云港。她说：“下一幕由我们自己决定。”';
const creative = (novelId: string) => `/api/novels/${novelId}/experimental/creative`;
const canvas = (page: Page) => page.getByRole('region', { name: '创作画布', exact: true });
const stage = (page: Page, name: string) => page.getByRole('tablist', { name: '创作模式', exact: true }).getByRole('tab', { name: new RegExp(`^${name}`) });

async function read(request: APIRequestContext, url: string): Promise<Row> {
  const response = await request.get(url);
  expect(response.ok(), `${url}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json();
}
async function write(request: APIRequestContext, url: string, data: Row): Promise<Row> {
  const response = await request.post(url, { data });
  expect(response.ok(), `${url}: ${response.status()} ${await response.text()}`).toBeTruthy();
  const row = await response.json();
  if (url === '/api/novels') {
    expect(response.status()).toBe(201);
    rememberNovel(request, row);
  }
  return row;
}
function rememberNovel(request: APIRequestContext, novel: Row) {
  expect(typeof novel.id, 'A successful synthetic novel create must return its exact ID.').toBe('string');
  expect(novel.id.length).toBeGreaterThan(0);
  const owned = ownedNovels.get(request);
  expect(owned, 'Synthetic novel ownership must be initialized by the fixture.').toBeDefined();
  owned!.add(novel.id);
}
test.beforeEach(async ({ request }) => {
  expect(await read(request, '/api/novels'), 'V2 live tests require an empty isolated server; unexpected novels are unowned and must not be deleted.').toEqual([]);
  ownedNovels.set(request, new Set());
});
test.afterEach(async ({ request }, info) => {
  const page = ownedPages.get(request);
  if (page && !page.isClosed()) {
    if (info.status !== info.expectedStatus) await page.screenshot({ path: info.outputPath('failure-before-owned-cleanup.png'), fullPage: true }).catch(() => {});
    // Stop the mounted UI before deleting fixtures, after all business assertions.
    await page.close();
  }
  const owned = ownedNovels.get(request);
  for (const id of owned || []) {
    const response = await request.delete(`/api/novels/${encodeURIComponent(id)}`);
    expect(response.status(), `Delete only this test's confirmed synthetic novel ${id}: ${await response.text()}`).toBe(204);
    expect(await response.text()).toBe('');
  }
  if (owned) expect(await read(request, '/api/novels'), 'Owned synthetic fixtures must be removed; any unowned inventory is preserved and reported.').toEqual([]);
});
async function fixture(page: Page, request: APIRequestContext) {
  ownedPages.set(request, page);
  await page.goto('/');
  await page.getByPlaceholder('小说名称').fill(`V2 浏览器合成验收 ${Date.now()}`);
  const creating = page.waitForResponse(response => response.url().endsWith('/api/novels') && response.request().method() === 'POST');
  await page.getByRole('button', { name: '创建小说', exact: true }).click();
  const created = await creating;
  expect(created.status()).toBe(201);
  const novel = await created.json();
  rememberNovel(request, novel);
  await page.getByRole('button', { name: '新建章节', exact: true }).click();
  await page.getByLabel('章节标题', { exact: true }).fill('第一章 合成海港');
  await page.getByRole('button', { name: '创建章节', exact: true }).click();
  await page.locator('.ProseMirror').fill(manuscript);
  await page.getByRole('button', { name: '保存', exact: true }).click();
  await expect(page.locator('.editorbar')).toContainText('已保存');
  const chapters = await read(request, `/api/novels/${novel.id}/chapters`);
  const chapter = await read(request, `/api/chapters/${chapters[0].id}`);
  await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  await expect(stage(page, '小说')).toHaveAttribute('aria-selected', 'true');
  await stage(page, '剧本').click();
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toBeEnabled();
  return { novel, chapter, base: creative(novel.id) };
}
async function clickTwice(locator: Locator) {
  // Native browser double-click: two actual click events while the mutation guard is active.
  await locator.dblclick({ delay: 10 });
}
async function mutate(page: Page, url: string, method: string, action: () => Promise<void>) {
  const pending = page.waitForResponse(response => new URL(response.url()).pathname === url && response.request().method() === method);
  await action();
  const response = await pending;
  expect(response.ok(), `${method} ${url}: ${response.status()} ${await response.text()}`).toBeTruthy();
  return response.json() as Promise<Row>;
}
async function save(page: Page, base: string, document?: Row, repeat = false) {
  return mutate(page, `${base}/documents${document ? `/${document.id}` : ''}`, document ? 'PUT' : 'POST',
    () => repeat ? clickTwice(canvas(page).getByRole('button', { name: '保存草稿', exact: true })) : canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click());
}
async function screenplay(page: Page, base: string) {
  await canvas(page).getByLabel('文档标题', { exact: true }).fill('云港 · 合成剧本');
  await page.getByRole('button', { name: '从当前已保存章节建立场景底稿', exact: true }).click();
  await canvas(page).getByLabel('场景标题', { exact: true }).fill('EXT. 云港 · 清晨');
  await canvas(page).getByLabel('场景地点', { exact: true }).fill('云港码头');
  await canvas(page).getByRole('button', { name: '添加对白', exact: true }).click();
  await canvas(page).getByLabel('对白 1 人物', { exact: true }).fill('林默');
  await canvas(page).getByLabel('对白 1 内容', { exact: true }).fill('下一幕由我们自己决定。');
  await canvas(page).getByRole('button', { name: '添加场景', exact: true }).click();
  await canvas(page).getByLabel('场景标题', { exact: true }).fill('INT. 灯塔 · 日');
  await canvas(page).getByLabel('动作与叙事', { exact: true }).fill('她在窗边整理航海图。');
  return save(page, base, undefined, true);
}
async function capture(page: Page, info: TestInfo, name: string) {
  await page.screenshot({ path: info.outputPath(`${name}.png`), fullPage: true });
  await info.attach(name, { path: info.outputPath(`${name}.png`), contentType: 'image/png' });
}

test('real File V2 authoring: reviewed direction, ordered storyboard, production history and restore preserve the manuscript', async ({ page, request }, info) => {
  test.info().annotations.push({ type: 'verification', description: 'Real uvicorn + File persistence + Vite + Chromium; synthetic manuscript; rule-assisted direction; no model inference or paid provider calls.' });
  const errors: string[] = [], requests: Row[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('request', req => { if (req.url().includes('/experimental/creative') && req.method() !== 'GET') requests.push({ path: new URL(req.url()).pathname, method: req.method() }); });
  const { novel, chapter, base } = await fixture(page, request);
  const source = await screenplay(page, base);
  expect(source.version).toBe(1);
  expect(source.source_chapter_ids).toEqual([chapter.id]);
  expect(source.scenes).toHaveLength(2);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  expect(requests.filter(row => row.path === `${base}/documents` && row.method === 'POST')).toHaveLength(1);
  await expect(canvas(page)).toContainText('已保存 · v1');
  await capture(page, info, 'screenplay-saved');

  const proposal = await mutate(page, `${base}/director-proposals`, 'POST', () => clickTwice(page.getByRole('button', { name: '准备待审导演建议', exact: true })));
  expect(proposal.status).toBe('NEEDS_REVIEW');
  expect(proposal.provenance.model_called).toBe(false);
  await expect(page.getByRole('button', { name: '审核并采用', exact: true })).toBeDisabled();
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  const review = page.getByRole('region', { name: '导演建议审核', exact: true });
  await review.getByText('场景调度 1', { exact: true }).click();
  await review.getByLabel('建议 1 表演指导', { exact: true }).fill('人工确认：停顿后看向窗外。');
  await review.getByLabel('采用后的导演文档标题', { exact: true }).fill('云港 · 人工审核导演稿');
  await review.getByRole('checkbox', { name: '已核对来源、场面调度与导演建议；创建独立导演文档', exact: true }).check();
  const approved = await mutate(page, `${base}/director-proposals/${proposal.id}/review`, 'POST', () => clickTwice(review.getByRole('button', { name: '审核并采用', exact: true })));
  const director = approved.document;
  expect(approved.proposal.status).toBe('APPROVED');
  expect(director.director_notes[0].performance).toBe('人工确认：停顿后看向窗外。');
  expect(director.source_documents[source.id].version).toBe(1);
  await expect(stage(page, '导演')).toHaveAttribute('aria-selected', 'true');
  expect((await read(request, `${base}/documents`)).items).toHaveLength(2);
  expect(requests.filter(row => row.path.endsWith('/review'))).toHaveLength(1);
  await capture(page, info, 'director-human-reviewed');

  const board = await mutate(page, `${base}/documents/${director.id}/derive`, 'POST', () => clickTwice(canvas(page).getByRole('button', { name: '建立分镜草稿', exact: true })));
  await expect(stage(page, '分镜')).toHaveAttribute('aria-selected', 'true');
  expect(board.shots).toHaveLength(2);
  expect(board.provenance.model_called).toBe(false);
  await canvas(page).getByRole('button', { name: '前移镜头 2', exact: true }).click();
  await canvas(page).getByLabel('画面描述', { exact: true }).fill('海港窗框里的人工镜头构图');
  await canvas(page).getByLabel('镜头与焦距', { exact: true }).fill('50mm');
  const editedBoard = await save(page, base, board);
  expect(editedBoard.version).toBe(2);
  expect(editedBoard.shots.map((shot: Row) => shot.id)).toEqual([...board.shots].reverse().map((shot: Row) => shot.id));
  expect(editedBoard.shots.some((shot: Row) => shot.lens === '50mm')).toBe(true);
  const production = await mutate(page, `${base}/documents/${board.id}/derive`, 'POST', () => clickTwice(canvas(page).getByRole('button', { name: '建立制作计划', exact: true })));
  await expect(stage(page, '制作')).toHaveAttribute('aria-selected', 'true');
  expect(production.video_plan.segments.map((row: Row) => row.shot_id)).toEqual(editedBoard.shots.map((row: Row) => row.id));
  await page.getByRole('button', { name: '后移第 1 段', exact: true }).click();
  await page.getByLabel('第 1 段时长', { exact: true }).fill('9');
  await page.getByLabel('制作备注', { exact: true }).fill('人工排序，仅结构化计划，未渲染媒体。');
  const editedProduction = await save(page, base, production);
  expect(editedProduction.version).toBe(2);
  expect(editedProduction.video_plan.segments[0].shot_id).toBe(production.video_plan.segments[1].shot_id);
  expect(editedProduction.video_plan.segments[0].duration_seconds).toBe(9);
  for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
    await page.setViewportSize({ width, height });
    const geometry = await page.locator('.creative-workspace').evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth, body: document.documentElement.scrollWidth, viewport: innerWidth }));
    expect(geometry.scroll).toBeLessThanOrEqual(geometry.client + 1);
    expect(geometry.body).toBeLessThanOrEqual(geometry.viewport + 1);
    await capture(page, info, `production-${width}x${height}`);
  }

  await canvas(page).getByRole('button', { name: '历史', exact: true }).click();
  const history = page.getByRole('region', { name: '创作文档历史', exact: true });
  await history.locator('summary').filter({ hasText: /^v1 ·/ }).click();
  await expect(history.getByRole('button', { name: '恢复 v1 为新版本', exact: true })).toBeDisabled();
  await history.getByRole('checkbox', { name: '已核对 v1 的完整内容；恢复会新建当前版本', exact: true }).check();
  const restored = await mutate(page, `${base}/documents/${production.id}/restore`, 'POST', () => clickTwice(history.getByRole('button', { name: '恢复 v1 为新版本', exact: true })));
  expect(restored.version).toBe(3);
  expect(restored.restored_from_version).toBe(1);
  expect(restored.video_plan).toEqual(production.video_plan);
  const persistedHistory = await read(request, `${base}/documents/${production.id}/history`);
  expect(persistedHistory.items.map((row: Row) => row.version)).toEqual([1, 2, 3]);

  await page.reload();
  await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  await stage(page, '制作').click();
  await expect(canvas(page)).toContainText('已保存 · v3');
  await expect(page.getByLabel('制作备注', { exact: true })).toHaveValue(production.video_plan.notes);
  const downloadEvent = page.waitForEvent('download');
  await canvas(page).getByRole('button', { name: '导出', exact: true }).click();
  const download = await downloadEvent;
  expect(download.suggestedFilename()).toBe(`creative-${production.id}.json`);
  await download.saveAs(info.outputPath('production-export.json'));
  await info.attach('production-export', { path: info.outputPath('production-export.json'), contentType: 'application/json' });
  expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(4);
  expect(requests.filter(row => /\/(dispatch|generate)(\/|$)/.test(row.path))).toEqual([]);
  expect(errors).toEqual([]);
  await info.attach('real-file-receipt', { body: JSON.stringify({ novel_id: novel.id, chapter_id: chapter.id, manuscript_unchanged: true, mode_ids: [source.id, director.id, board.id, production.id], current_version: restored.version, model_called: false, requests }, null, 2), contentType: 'application/json' });
});

test('real File V2 cancel and navigation retain dirty drafts without duplicating accepted or cancelled proposals', async ({ page, request }, info) => {
  const { chapter, base } = await fixture(page, request);
  const source = await screenplay(page, base);
  const proposal = await mutate(page, `${base}/director-proposals`, 'POST', () => page.getByRole('button', { name: '准备待审导演建议', exact: true }).click());
  const cancelled = await mutate(page, `${base}/director-proposals/${proposal.id}/cancel`, 'POST', () => clickTwice(page.getByRole('button', { name: '取消建议', exact: true })));
  expect(cancelled.status).toBe('CANCELLED');
  await expect(page.getByRole('button', { name: '审核并采用', exact: true })).toBeDisabled();
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  await canvas(page).getByLabel('文档标题', { exact: true }).fill('尚未保存，离开也不能误写');
  await stage(page, '分镜').click();
  await stage(page, '剧本').click();
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('尚未保存，离开也不能误写');
  await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
  await expect(page.getByRole('button', { name: '确认离开', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '继续编辑', exact: true }).click();
  await expect(page.getByRole('button', { name: '确认离开', exact: true })).toHaveCount(0);
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('尚未保存，离开也不能误写');
  await capture(page, info, 'cancelled-proposal-dirty-draft-retained');
  await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
  await page.getByRole('checkbox', { name: '确认放弃未保存草稿并离开', exact: true }).check();
  await page.getByRole('button', { name: '确认离开', exact: true }).click();
  await expect(page.getByRole('tablist', { name: '创作模式', exact: true })).toHaveCount(0);
  await expect(page.locator('.ProseMirror')).toContainText(manuscript);
  await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  await stage(page, '剧本').click();
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(source.title);
  expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
});

test('real File V2 scope and stale-write fencing keeps the browser draft and rejects foreign sources', async ({ page, request }, info) => {
  const { chapter, base } = await fixture(page, request);
  const source = await screenplay(page, base);
  const foreignNovel = await write(request, '/api/novels', { title: 'Foreign synthetic project' });
  const foreignChapter = await write(request, `/api/novels/${foreignNovel.id}/chapters`, { title: 'Foreign source', content: 'Other project manuscript.' });
  const payload = { mode: 'SCREENPLAY', title: 'Must reject foreign binding', source_chapter_ids: [foreignChapter.id], scenes: [{ id: 'foreign-scene', sequence: 1, heading: 'Foreign', source_chapter_id: foreignChapter.id }] };
  const foreign = await request.post(`${base}/documents`, { data: payload });
  expect(foreign.status()).toBe(422);
  expect(await foreign.json()).toMatchObject({ code: 'EXPERIMENTAL_INVALID', message: 'chapter belongs to another project' });
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  expect((await request.get(`${creative(foreignNovel.id)}/documents/${source.id}`)).status()).toBe(404);
  await canvas(page).getByLabel('文档标题', { exact: true }).fill('保留这份本地冲突草稿');
  const input = Object.fromEntries(['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'shots', 'director_notes', 'video_plan'].map(key => [key, source[key]]));
  const serverChange = await request.put(`${base}/documents/${source.id}`, { data: { ...input, title: '另一客户端保存的标题', expected_version: source.version } });
  expect(serverChange.ok()).toBeTruthy();
  const conflicting = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/documents/${source.id}` && response.request().method() === 'PUT');
  await canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click();
  expect((await conflicting).status()).toBe(409);
  await expect(page.getByText('需要核对版本 · 本地草稿仍保留', { exact: true })).toBeVisible();
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('保留这份本地冲突草稿');
  await expect(canvas(page).getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled();
  await page.getByRole('button', { name: '核对服务端版本', exact: true }).click();
  const reconciliation = page.getByRole('region', { name: '服务端版本核对', exact: true });
  await expect(reconciliation).toContainText('另一客户端保存的标题');
  await reconciliation.getByRole('button', { name: '保留本地草稿', exact: true }).click();
  await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('保留这份本地冲突草稿');
  await capture(page, info, 'stale-write-preserves-draft');
  expect((await read(request, `${base}/documents/${source.id}`)).title).toBe('另一客户端保存的标题');
  expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
});

test('V1 default-off backend and browser never expose the V2 workbench or accept creative writes', async ({ page, request }, info) => {
  ownedPages.set(request, page);
  await page.goto('/');
  await expect(page.getByPlaceholder('小说名称')).toBeVisible();
  await expect(page.getByRole('button', { name: '打开 V2 创作工作台', exact: true })).toHaveCount(0);
  const novel = await write(request, '/api/novels', { title: 'V1 gate synthetic fixture' });
  const base = creative(novel.id);
  const capabilities = await read(request, `${base}/capabilities`);
  expect(capabilities.enabled).toBe(false);
  expect(capabilities.can_mutate).toBe(false);
  expect((await request.get(`${base}/documents`)).status()).toBe(404);
  expect((await request.post(`${base}/documents`, { data: { mode: 'SCREENPLAY', title: 'Blocked', source_independent: true } })).status()).toBe(404);
  await capture(page, info, 'v1-default-off-workbench-hidden');
});

test('real HTTP File V2 lifecycle persists reviewed direction, order, history and restored content with unchanged manuscript', async ({ request }, info) => {
  test.info().annotations.push({ type: 'verification', description: 'Real uvicorn HTTP/File test; no browser fixture; synthetic local rule-assisted data, no model inference.' });
  const novel = await write(request, '/api/novels', { title: 'V2 HTTP real File lifecycle' });
  const createdChapter = await write(request, `/api/novels/${novel.id}/chapters`, { title: '合成海港', content: manuscript });
  const chapter = await read(request, `/api/chapters/${createdChapter.id}`);
  const base = creative(novel.id);
  const capabilities = await read(request, `${base}/capabilities`);
  expect(capabilities.enabled).toBe(true);
  expect(capabilities.can_mutate).toBe(true);
  const source = await write(request, `${base}/documents`, {
    mode: 'SCREENPLAY', title: 'HTTP 合成剧本', source_chapter_ids: [chapter.id],
    scenes: [
      { id: 'scene-port', sequence: 1, source_chapter_id: chapter.id, heading: 'EXT. 云港', action: manuscript, dialogue: [{ speaker: '林默', text: '下一幕由我们自己决定。' }] },
      { id: 'scene-room', sequence: 2, source_chapter_id: chapter.id, heading: 'INT. 灯塔', action: '她在窗边整理航海图。' },
    ],
  });
  const proposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: source.version });
  expect(proposal.status).toBe('NEEDS_REVIEW');
  expect(proposal.provenance.model_called).toBe(false);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  const notes = structuredClone(proposal.director_notes);
  notes[0].performance = 'Human-reviewed blocking and performance';
  const reviewBody = { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title: 'HTTP 人工审核导演稿', director_notes: notes };
  const reviews = await Promise.all([request.post(`${base}/director-proposals/${proposal.id}/review`, { data: reviewBody }), request.post(`${base}/director-proposals/${proposal.id}/review`, { data: reviewBody })]);
  expect(reviews.map(row => row.status()).sort()).toEqual([200, 409]);
  const accepted = await reviews.find(row => row.ok())!.json();
  const director = accepted.document;
  expect(director.director_notes[0].performance).toBe(notes[0].performance);
  expect(director.source_documents[source.id].version).toBe(source.version);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(2);
  const board = await write(request, `${base}/documents/${director.id}/derive`, { expected_version: director.version, mode: 'STORYBOARD' });
  expect(board.shots).toHaveLength(2);
  expect(board.provenance.model_called).toBe(false);
  const content = (row: Row) => Object.fromEntries(['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'shots', 'director_notes', 'video_plan'].map(key => [key, row[key]]));
  const boardContent = content(board);
  boardContent.shots = [...board.shots].reverse().map((shot: Row, index: number) => ({ ...shot, number: index + 1, lens: index === 0 ? '50mm' : '35mm' }));
  const boardResponse = await request.put(`${base}/documents/${board.id}`, { data: { ...boardContent, expected_version: board.version } });
  expect(boardResponse.status()).toBe(200);
  const editedBoard = await boardResponse.json();
  expect(editedBoard.shots.map((shot: Row) => shot.id)).toEqual([...board.shots].reverse().map((shot: Row) => shot.id));
  const production = await write(request, `${base}/documents/${board.id}/derive`, { expected_version: editedBoard.version, mode: 'PRODUCTION' });
  expect(production.source_documents[board.id].version).toBe(editedBoard.version);
  const productionContent = content(production);
  productionContent.video_plan = { ...production.video_plan, notes: 'No rendered media. Human production plan.', segments: [...production.video_plan.segments].reverse().map((segment: Row, index: number) => ({ ...segment, duration_seconds: index === 0 ? 9 : segment.duration_seconds })) };
  const saveResponse = await request.put(`${base}/documents/${production.id}`, { data: { ...productionContent, expected_version: 1 } });
  expect(saveResponse.status()).toBe(200);
  expect((await saveResponse.json()).version).toBe(2);
  const restored = await write(request, `${base}/documents/${production.id}/restore`, { expected_version: 2, restore_version: 1 });
  expect(restored.version).toBe(3);
  expect(restored.restored_from_version).toBe(1);
  expect(restored.video_plan).toEqual(production.video_plan);
  const history = await read(request, `${base}/documents/${production.id}/history`);
  expect(history.items.map((row: Row) => row.version)).toEqual([1, 2, 3]);
  expect(history.items[1].video_plan.segments[0].duration_seconds).toBe(9);
  expect(await read(request, `${base}/documents/${production.id}`)).toEqual(restored);
  const exported = await read(request, `${base}/documents/${production.id}/export`);
  expect(exported.document.id).toBe(restored.id);
  expect(exported.document.version).toBe(3);
  expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(4);
  await info.attach('http-file-lifecycle-receipt', { body: JSON.stringify({ verification: 'HTTP/File only, browser launch verified separately', novel_id: novel.id, chapter_id: chapter.id, manuscript_unchanged: true, created_documents: [source.id, director.id, board.id, production.id], concurrent_review_statuses: reviews.map(row => row.status()), versions: history.items.map((row: Row) => row.version), model_called: false, export: exported }, null, 2), contentType: 'application/json' });
});

test('real HTTP File V2 scope, cancel and stale source fences remain authoritative', async ({ request }, info) => {
  const novel = await write(request, '/api/novels', { title: 'V2 HTTP fence fixture' });
  const foreign = await write(request, '/api/novels', { title: 'V2 HTTP foreign fixture' });
  const created = await write(request, `/api/novels/${novel.id}/chapters`, { title: 'Owned chapter', content: manuscript });
  const chapter = await read(request, `/api/chapters/${created.id}`);
  const outsider = await write(request, `/api/novels/${foreign.id}/chapters`, { title: 'Foreign chapter', content: 'Not authorized as this project source.' });
  const base = creative(novel.id);
  const input = { mode: 'SCREENPLAY', title: 'Fence source', source_chapter_ids: [chapter.id], scenes: [{ id: 's1', sequence: 1, heading: 'Scene', source_chapter_id: chapter.id, action: manuscript }] };
  const source = await write(request, `${base}/documents`, input);
  const badBinding = await request.post(`${base}/documents`, { data: { ...input, source_chapter_ids: [outsider.id], scenes: [] } });
  expect(badBinding.status()).toBe(422);
  expect(await badBinding.json()).toMatchObject({ code: 'EXPERIMENTAL_INVALID', message: 'chapter belongs to another project' });
  expect((await request.get(`${creative(foreign.id)}/documents/${source.id}`)).status()).toBe(404);
  const proposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: 1 });
  const cancelled = await write(request, `${base}/director-proposals/${proposal.id}/cancel`, { expected_version: proposal.version });
  expect(cancelled.status).toBe('CANCELLED');
  const rejectedReview = await request.post(`${base}/director-proposals/${proposal.id}/review`, { data: { expected_version: cancelled.version, reviewed_output_digest: proposal.output_digest, title: 'Must not accept cancelled', director_notes: proposal.director_notes } });
  expect(rejectedReview.status()).toBe(422);
  expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  const simultaneous = await Promise.all(['First', 'Second'].map(title => request.put(`${base}/documents/${source.id}`, { data: { ...input, title, expected_version: 1 } })));
  expect(simultaneous.map(row => row.status()).sort()).toEqual([200, 409]);
  const current = await read(request, `${base}/documents/${source.id}`);
  const pendingProposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: current.version });
  const chapterUpdate = await request.put(`/api/chapters/${chapter.id}`, { data: { version: chapter.version, content: manuscript + '\nExplicit second-client source edit.' } });
  expect(chapterUpdate.status()).toBe(200);
  expect((await request.get(`${base}/documents/${source.id}`)).status()).toBe(409);
  expect((await request.get(`${base}/director-proposals/${pendingProposal.id}`)).status()).toBe(409);
  expect((await read(request, `${base}/documents`)).items).toEqual([]);
  expect((await request.post(`${base}/documents/${source.id}/derive`, { data: { expected_version: current.version, mode: 'STORYBOARD' } })).status()).toBe(409);
  await info.attach('http-source-fence-receipt', { body: JSON.stringify({ foreign_binding: badBinding.status(), cancelled_review: rejectedReview.status(), simultaneous_update_statuses: simultaneous.map(row => row.status()), stale_source_read: 409, stale_source_derive: 409, model_called: false }, null, 2), contentType: 'application/json' });
});

test('real HTTP default-off gate advertises disabled capabilities and rejects creative reads and writes', async ({ request }, info) => {
  const novel = await write(request, '/api/novels', { title: 'HTTP default-off fixture' });
  const base = creative(novel.id);
  const capabilities = await read(request, `${base}/capabilities`);
  expect(capabilities.enabled).toBe(false);
  expect(capabilities.can_mutate).toBe(false);
  expect((await request.get(`${base}/documents`)).status()).toBe(404);
  expect((await request.post(`${base}/documents`, { data: { mode: 'SCREENPLAY', title: 'Blocked', source_independent: true } })).status()).toBe(404);
  await info.attach('http-default-off-receipt', { body: JSON.stringify(capabilities), contentType: 'application/json' });
});
