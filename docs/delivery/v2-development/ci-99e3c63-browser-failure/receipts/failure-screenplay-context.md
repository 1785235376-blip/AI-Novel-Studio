# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-creative-live.spec.ts >> real File V2 cancel and navigation retain dirty drafts without duplicating accepted or cancelled proposals
- Location: tests/e2e/v2-creative-live.spec.ts:206:1

# Error details

```
Error: expect(locator).toHaveValue(expected) failed

Locator:  getByRole('region', { name: '创作画布', exact: true }).getByLabel('文档标题', { exact: true })
Expected: "云港 · 合成剧本"
Received: ""
Timeout:  15000ms

Call log:
  - Expect "toHaveValue" with timeout 15000ms
  - waiting for getByRole('region', { name: '创作画布', exact: true }).getByLabel('文档标题', { exact: true })
    34 × locator resolved to <input value="" required="" maxlength="240"/>
       - unexpected value ""

```

```yaml
- textbox "文档标题"
```

# Test source

```ts
  131 |   const review = page.getByRole('region', { name: '导演建议审核', exact: true });
  132 |   await review.getByText('场景调度 1', { exact: true }).click();
  133 |   await review.getByLabel('建议 1 表演指导', { exact: true }).fill('人工确认：停顿后看向窗外。');
  134 |   await review.getByLabel('采用后的导演文档标题', { exact: true }).fill('云港 · 人工审核导演稿');
  135 |   await review.getByRole('checkbox', { name: '已核对来源、场面调度与导演建议；创建独立导演文档', exact: true }).check();
  136 |   const approved = await mutate(page, `${base}/director-proposals/${proposal.id}/review`, 'POST', () => clickTwice(review.getByRole('button', { name: '审核并采用', exact: true })));
  137 |   const director = approved.document;
  138 |   expect(approved.proposal.status).toBe('APPROVED');
  139 |   expect(director.director_notes[0].performance).toBe('人工确认：停顿后看向窗外。');
  140 |   expect(director.source_documents[source.id].version).toBe(1);
  141 |   await expect(stage(page, '导演')).toHaveAttribute('aria-selected', 'true');
  142 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(2);
  143 |   expect(requests.filter(row => row.path.endsWith('/review'))).toHaveLength(1);
  144 |   await capture(page, info, 'director-human-reviewed');
  145 | 
  146 |   const board = await mutate(page, `${base}/documents/${director.id}/derive`, 'POST', () => clickTwice(canvas(page).getByRole('button', { name: '建立分镜草稿', exact: true })));
  147 |   await expect(stage(page, '分镜')).toHaveAttribute('aria-selected', 'true');
  148 |   expect(board.shots).toHaveLength(2);
  149 |   expect(board.provenance.model_called).toBe(false);
  150 |   await canvas(page).getByRole('button', { name: '前移镜头 2', exact: true }).click();
  151 |   await canvas(page).getByLabel('画面描述', { exact: true }).fill('海港窗框里的人工镜头构图');
  152 |   await canvas(page).getByLabel('镜头与焦距', { exact: true }).fill('50mm');
  153 |   const editedBoard = await save(page, base, board);
  154 |   expect(editedBoard.version).toBe(2);
  155 |   expect(editedBoard.shots.map((shot: Row) => shot.id)).toEqual([...board.shots].reverse().map((shot: Row) => shot.id));
  156 |   expect(editedBoard.shots.some((shot: Row) => shot.lens === '50mm')).toBe(true);
  157 |   const production = await mutate(page, `${base}/documents/${board.id}/derive`, 'POST', () => clickTwice(canvas(page).getByRole('button', { name: '建立制作计划', exact: true })));
  158 |   await expect(stage(page, '制作')).toHaveAttribute('aria-selected', 'true');
  159 |   expect(production.video_plan.segments.map((row: Row) => row.shot_id)).toEqual(editedBoard.shots.map((row: Row) => row.id));
  160 |   await page.getByRole('button', { name: '后移第 1 段', exact: true }).click();
  161 |   await page.getByLabel('第 1 段时长', { exact: true }).fill('9');
  162 |   await page.getByLabel('制作备注', { exact: true }).fill('人工排序，仅结构化计划，未渲染媒体。');
  163 |   const editedProduction = await save(page, base, production);
  164 |   expect(editedProduction.version).toBe(2);
  165 |   expect(editedProduction.video_plan.segments[0].shot_id).toBe(production.video_plan.segments[1].shot_id);
  166 |   expect(editedProduction.video_plan.segments[0].duration_seconds).toBe(9);
  167 |   for (const [width, height] of [[1366, 768], [1440, 900], [1920, 1080]]) {
  168 |     await page.setViewportSize({ width, height });
  169 |     const geometry = await page.locator('.creative-workspace').evaluate(element => ({ client: element.clientWidth, scroll: element.scrollWidth, body: document.documentElement.scrollWidth, viewport: innerWidth }));
  170 |     expect(geometry.scroll).toBeLessThanOrEqual(geometry.client + 1);
  171 |     expect(geometry.body).toBeLessThanOrEqual(geometry.viewport + 1);
  172 |     await capture(page, info, `production-${width}x${height}`);
  173 |   }
  174 | 
  175 |   await canvas(page).getByRole('button', { name: '历史', exact: true }).click();
  176 |   const history = page.getByRole('region', { name: '创作文档历史', exact: true });
  177 |   await history.locator('summary').filter({ hasText: /^v1 ·/ }).click();
  178 |   await expect(history.getByRole('button', { name: '恢复 v1 为新版本', exact: true })).toBeDisabled();
  179 |   await history.getByRole('checkbox', { name: '已核对 v1 的完整内容；恢复会新建当前版本', exact: true }).check();
  180 |   const restored = await mutate(page, `${base}/documents/${production.id}/restore`, 'POST', () => clickTwice(history.getByRole('button', { name: '恢复 v1 为新版本', exact: true })));
  181 |   expect(restored.version).toBe(3);
  182 |   expect(restored.restored_from_version).toBe(1);
  183 |   expect(restored.video_plan).toEqual(production.video_plan);
  184 |   const persistedHistory = await read(request, `${base}/documents/${production.id}/history`);
  185 |   expect(persistedHistory.items.map((row: Row) => row.version)).toEqual([1, 2, 3]);
  186 | 
  187 |   await page.reload();
  188 |   await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  189 |   await stage(page, '制作').click();
  190 |   await expect(canvas(page)).toContainText('已保存 · v3');
  191 |   await expect(page.getByLabel('制作备注', { exact: true })).toHaveValue(production.video_plan.notes);
  192 |   const downloadEvent = page.waitForEvent('download');
  193 |   await canvas(page).getByRole('button', { name: '导出', exact: true }).click();
  194 |   const download = await downloadEvent;
  195 |   expect(download.suggestedFilename()).toBe(`creative-${production.id}.json`);
  196 |   await download.saveAs(info.outputPath('production-export.json'));
  197 |   await info.attach('production-export', { path: info.outputPath('production-export.json'), contentType: 'application/json' });
  198 |   expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  199 |   expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  200 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(4);
  201 |   expect(requests.filter(row => /\/(dispatch|generate)(\/|$)/.test(row.path))).toEqual([]);
  202 |   expect(errors).toEqual([]);
  203 |   await info.attach('real-file-receipt', { body: JSON.stringify({ novel_id: novel.id, chapter_id: chapter.id, manuscript_unchanged: true, mode_ids: [source.id, director.id, board.id, production.id], current_version: restored.version, model_called: false, requests }, null, 2), contentType: 'application/json' });
  204 | });
  205 | 
  206 | test('real File V2 cancel and navigation retain dirty drafts without duplicating accepted or cancelled proposals', async ({ page, request }, info) => {
  207 |   const { chapter, base } = await fixture(page, request);
  208 |   const source = await screenplay(page, base);
  209 |   const proposal = await mutate(page, `${base}/director-proposals`, 'POST', () => page.getByRole('button', { name: '准备待审导演建议', exact: true }).click());
  210 |   const cancelled = await mutate(page, `${base}/director-proposals/${proposal.id}/cancel`, 'POST', () => clickTwice(page.getByRole('button', { name: '取消建议', exact: true })));
  211 |   expect(cancelled.status).toBe('CANCELLED');
  212 |   await expect(page.getByRole('button', { name: '审核并采用', exact: true })).toBeDisabled();
  213 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  214 |   await canvas(page).getByLabel('文档标题', { exact: true }).fill('尚未保存，离开也不能误写');
  215 |   await stage(page, '分镜').click();
  216 |   await stage(page, '剧本').click();
  217 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('尚未保存，离开也不能误写');
  218 |   await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
  219 |   await expect(page.getByRole('button', { name: '确认离开', exact: true })).toBeDisabled();
  220 |   await page.getByRole('button', { name: '继续编辑', exact: true }).click();
  221 |   await expect(page.getByRole('button', { name: '确认离开', exact: true })).toHaveCount(0);
  222 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('尚未保存，离开也不能误写');
  223 |   await capture(page, info, 'cancelled-proposal-dirty-draft-retained');
  224 |   await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
  225 |   await page.getByRole('checkbox', { name: '确认放弃未保存草稿并离开', exact: true }).check();
  226 |   await page.getByRole('button', { name: '确认离开', exact: true }).click();
  227 |   await expect(page.getByRole('tablist', { name: '创作模式', exact: true })).toHaveCount(0);
  228 |   await expect(page.locator('.ProseMirror')).toContainText(manuscript);
  229 |   await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  230 |   await stage(page, '剧本').click();
> 231 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(source.title);
      |                                                                  ^ Error: expect(locator).toHaveValue(expected) failed
  232 |   expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  233 |   expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  234 | });
  235 | 
  236 | test('real File V2 scope and stale-write fencing keeps the browser draft and rejects foreign sources', async ({ page, request }, info) => {
  237 |   const { chapter, base } = await fixture(page, request);
  238 |   const source = await screenplay(page, base);
  239 |   const foreignNovel = await write(request, '/api/novels', { title: 'Foreign synthetic project' });
  240 |   const foreignChapter = await write(request, `/api/novels/${foreignNovel.id}/chapters`, { title: 'Foreign source', content: 'Other project manuscript.' });
  241 |   const payload = { mode: 'SCREENPLAY', title: 'Must reject foreign binding', source_chapter_ids: [foreignChapter.id], scenes: [{ id: 'foreign-scene', sequence: 1, heading: 'Foreign', source_chapter_id: foreignChapter.id }] };
  242 |   const foreign = await request.post(`${base}/documents`, { data: payload });
  243 |   expect(foreign.status()).toBe(422);
  244 |   expect(await foreign.json()).toMatchObject({ code: 'EXPERIMENTAL_INVALID', message: 'chapter belongs to another project' });
  245 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  246 |   expect((await request.get(`${creative(foreignNovel.id)}/documents/${source.id}`)).status()).toBe(404);
  247 |   await canvas(page).getByLabel('文档标题', { exact: true }).fill('保留这份本地冲突草稿');
  248 |   const input = Object.fromEntries(['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'shots', 'director_notes', 'video_plan'].map(key => [key, source[key]]));
  249 |   const serverChange = await request.put(`${base}/documents/${source.id}`, { data: { ...input, title: '另一客户端保存的标题', expected_version: source.version } });
  250 |   expect(serverChange.ok()).toBeTruthy();
  251 |   const conflicting = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/documents/${source.id}` && response.request().method() === 'PUT');
  252 |   await canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click();
  253 |   expect((await conflicting).status()).toBe(409);
  254 |   await expect(page.getByText('需要核对版本 · 本地草稿仍保留', { exact: true })).toBeVisible();
  255 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('保留这份本地冲突草稿');
  256 |   await expect(canvas(page).getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled();
  257 |   await page.getByRole('button', { name: '核对服务端版本', exact: true }).click();
  258 |   const reconciliation = page.getByRole('region', { name: '服务端版本核对', exact: true });
  259 |   await expect(reconciliation).toContainText('另一客户端保存的标题');
  260 |   await reconciliation.getByRole('button', { name: '保留本地草稿', exact: true }).click();
  261 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue('保留这份本地冲突草稿');
  262 |   await capture(page, info, 'stale-write-preserves-draft');
  263 |   expect((await read(request, `${base}/documents/${source.id}`)).title).toBe('另一客户端保存的标题');
  264 |   expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  265 | });
  266 | 
  267 | test('V1 default-off backend and browser never expose the V2 workbench or accept creative writes', async ({ page, request }, info) => {
  268 |   ownedPages.set(request, page);
  269 |   await page.goto('/');
  270 |   await expect(page.getByPlaceholder('小说名称')).toBeVisible();
  271 |   await expect(page.getByRole('button', { name: '打开 V2 创作工作台', exact: true })).toHaveCount(0);
  272 |   const novel = await write(request, '/api/novels', { title: 'V1 gate synthetic fixture' });
  273 |   const base = creative(novel.id);
  274 |   const capabilities = await read(request, `${base}/capabilities`);
  275 |   expect(capabilities.enabled).toBe(false);
  276 |   expect(capabilities.can_mutate).toBe(false);
  277 |   expect((await request.get(`${base}/documents`)).status()).toBe(404);
  278 |   expect((await request.post(`${base}/documents`, { data: { mode: 'SCREENPLAY', title: 'Blocked', source_independent: true } })).status()).toBe(404);
  279 |   await capture(page, info, 'v1-default-off-workbench-hidden');
  280 | });
  281 | 
  282 | test('real HTTP File V2 lifecycle persists reviewed direction, order, history and restored content with unchanged manuscript', async ({ request }, info) => {
  283 |   test.info().annotations.push({ type: 'verification', description: 'Real uvicorn HTTP/File test; no browser fixture; synthetic local rule-assisted data, no model inference.' });
  284 |   const novel = await write(request, '/api/novels', { title: 'V2 HTTP real File lifecycle' });
  285 |   const createdChapter = await write(request, `/api/novels/${novel.id}/chapters`, { title: '合成海港', content: manuscript });
  286 |   const chapter = await read(request, `/api/chapters/${createdChapter.id}`);
  287 |   const base = creative(novel.id);
  288 |   const capabilities = await read(request, `${base}/capabilities`);
  289 |   expect(capabilities.enabled).toBe(true);
  290 |   expect(capabilities.can_mutate).toBe(true);
  291 |   const source = await write(request, `${base}/documents`, {
  292 |     mode: 'SCREENPLAY', title: 'HTTP 合成剧本', source_chapter_ids: [chapter.id],
  293 |     scenes: [
  294 |       { id: 'scene-port', sequence: 1, source_chapter_id: chapter.id, heading: 'EXT. 云港', action: manuscript, dialogue: [{ speaker: '林默', text: '下一幕由我们自己决定。' }] },
  295 |       { id: 'scene-room', sequence: 2, source_chapter_id: chapter.id, heading: 'INT. 灯塔', action: '她在窗边整理航海图。' },
  296 |     ],
  297 |   });
  298 |   const proposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: source.version });
  299 |   expect(proposal.status).toBe('NEEDS_REVIEW');
  300 |   expect(proposal.provenance.model_called).toBe(false);
  301 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  302 |   const notes = structuredClone(proposal.director_notes);
  303 |   notes[0].performance = 'Human-reviewed blocking and performance';
  304 |   const reviewBody = { expected_version: proposal.version, reviewed_output_digest: proposal.output_digest, title: 'HTTP 人工审核导演稿', director_notes: notes };
  305 |   const reviews = await Promise.all([request.post(`${base}/director-proposals/${proposal.id}/review`, { data: reviewBody }), request.post(`${base}/director-proposals/${proposal.id}/review`, { data: reviewBody })]);
  306 |   expect(reviews.map(row => row.status()).sort()).toEqual([200, 409]);
  307 |   const accepted = await reviews.find(row => row.ok())!.json();
  308 |   const director = accepted.document;
  309 |   expect(director.director_notes[0].performance).toBe(notes[0].performance);
  310 |   expect(director.source_documents[source.id].version).toBe(source.version);
  311 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(2);
  312 |   const board = await write(request, `${base}/documents/${director.id}/derive`, { expected_version: director.version, mode: 'STORYBOARD' });
  313 |   expect(board.shots).toHaveLength(2);
  314 |   expect(board.provenance.model_called).toBe(false);
  315 |   const content = (row: Row) => Object.fromEntries(['mode', 'title', 'source_chapter_ids', 'source_independent', 'scenes', 'shots', 'director_notes', 'video_plan'].map(key => [key, row[key]]));
  316 |   const boardContent = content(board);
  317 |   boardContent.shots = [...board.shots].reverse().map((shot: Row, index: number) => ({ ...shot, number: index + 1, lens: index === 0 ? '50mm' : '35mm' }));
  318 |   const boardResponse = await request.put(`${base}/documents/${board.id}`, { data: { ...boardContent, expected_version: board.version } });
  319 |   expect(boardResponse.status()).toBe(200);
  320 |   const editedBoard = await boardResponse.json();
  321 |   expect(editedBoard.shots.map((shot: Row) => shot.id)).toEqual([...board.shots].reverse().map((shot: Row) => shot.id));
  322 |   const production = await write(request, `${base}/documents/${board.id}/derive`, { expected_version: editedBoard.version, mode: 'PRODUCTION' });
  323 |   expect(production.source_documents[board.id].version).toBe(editedBoard.version);
  324 |   const productionContent = content(production);
  325 |   productionContent.video_plan = { ...production.video_plan, notes: 'No rendered media. Human production plan.', segments: [...production.video_plan.segments].reverse().map((segment: Row, index: number) => ({ ...segment, duration_seconds: index === 0 ? 9 : segment.duration_seconds })) };
  326 |   const saveResponse = await request.put(`${base}/documents/${production.id}`, { data: { ...productionContent, expected_version: 1 } });
  327 |   expect(saveResponse.status()).toBe(200);
  328 |   expect((await saveResponse.json()).version).toBe(2);
  329 |   const restored = await write(request, `${base}/documents/${production.id}/restore`, { expected_version: 2, restore_version: 1 });
  330 |   expect(restored.version).toBe(3);
  331 |   expect(restored.restored_from_version).toBe(1);
```