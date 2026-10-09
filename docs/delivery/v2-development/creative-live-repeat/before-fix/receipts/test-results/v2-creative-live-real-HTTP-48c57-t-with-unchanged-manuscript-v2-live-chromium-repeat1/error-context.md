# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-creative-live.spec.ts >> real HTTP File V2 lifecycle persists reviewed direction, order, history and restored content with unchanged manuscript
- Location: tests/e2e/v2-creative-live.spec.ts:282:1

# Error details

```
Error: expect(received).toHaveLength(expected)

Expected length: 1
Received length: 5
Received array:  [{"created_at": "2026-10-09T07:28:44.584681+00:00", "created_by": "local-author", "director_notes": [Array], "history": [Array], "id": "810598a7-2a22-4147-9c50-eaff779da579", "mode": "SCREENPLAY", "novel_id": "v2-http-real-file-lifecycle", "privacy_level": "LOCAL_ONLY", "scenes": [Array], "schema_version": 1, "scope": [Object], "shots": [Array], "source_chapter_ids": [Array], "source_documents": [Object], "source_evidence": [Object], "source_independent": false, "source_privacy": [Object], "status": "DRAFT", "title": "HTTP 合成剧本", "updated_at": "2026-10-09T07:28:44.584681+00:00", "updated_by": "local-author", "version": 1, "video_plan": null}, {"created_at": "2026-10-09T07:28:44.715941+00:00", "created_by": "local-author", "director_notes": [Array], "history": [Array], "id": "d4fdc9a0-2323-4f05-b8cd-3644ac21dae6", "mode": "DIRECTOR", "novel_id": "v2-http-real-file-lifecycle", "privacy_level": "LOCAL_ONLY", "provenance": [Object], "scenes": [Array], "schema_version": 1, "scope": [Object], "shots": [Array], "source_chapter_ids": [Array], "source_documents": [Object], "source_evidence": [Object], "source_independent": false, "source_privacy": [Object], "status": "DRAFT", "title": "HTTP 人工审核导演稿", "updated_at": "2026-10-09T07:28:44.715941+00:00", "updated_by": "local-author", "version": 1, "video_plan": null}, {"created_at": "2026-10-09T07:28:44.796994+00:00", "created_by": "local-author", "director_notes": [Array], "history": [Array], "id": "c06a5411-efac-4b6a-a368-457a3c3dfb28", "mode": "STORYBOARD", "novel_id": "v2-http-real-file-lifecycle", "privacy_level": "LOCAL_ONLY", "provenance": [Object], "scenes": [Array], "schema_version": 1, "scope": [Object], "shots": [Array], "source_chapter_ids": [Array], "source_documents": [Object], "source_evidence": [Object], "source_independent": false, "source_privacy": [Object], "status": "DRAFT", "title": "HTTP 人工审核导演稿 · 分镜", "updated_at": "2026-10-09T07:28:44.842267+00:00", "updated_by": "local-author", "version": 2, "video_plan": null}, {"created_at": "2026-10-09T07:28:44.904530+00:00", "created_by": "local-author", "director_notes": [Array], "history": [Array], "id": "44b2b289-ee4d-449a-8173-c563655fdefe", "mode": "PRODUCTION", "novel_id": "v2-http-real-file-lifecycle", "privacy_level": "LOCAL_ONLY", "provenance": [Object], "restored_from_version": 1, "scenes": [Array], "schema_version": 1, "scope": [Object], "shots": [Array], "source_chapter_ids": [Array], "source_documents": [Object], "source_evidence": [Object], "source_independent": false, "source_privacy": [Object], "status": "DRAFT", "title": "HTTP 人工审核导演稿 · 分镜 · 制作", "updated_at": "2026-10-09T07:28:45.100465+00:00", "updated_by": "local-author", "version": 3, "video_plan": [Object]}, {"created_at": "2026-10-09T07:28:46.501078+00:00", "created_by": "local-author", "director_notes": [Array], "history": [Array], "id": "f038f033-472b-441d-82cf-1dbc6f12b4de", "mode": "SCREENPLAY", "novel_id": "v2-http-real-file-lifecycle", "privacy_level": "LOCAL_ONLY", "scenes": [Array], "schema_version": 1, "scope": [Object], "shots": [Array], "source_chapter_ids": [Array], "source_documents": [Object], "source_evidence": [Object], "source_independent": false, "source_privacy": [Object], "status": "DRAFT", "title": "HTTP 合成剧本", "updated_at": "2026-10-09T07:28:46.501078+00:00", "updated_by": "local-author", "version": 1, "video_plan": null}]
```

# Test source

```ts
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
  231 |   await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(source.title);
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
> 301 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
      |                                                            ^ Error: expect(received).toHaveLength(expected)
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
  332 |   expect(restored.video_plan).toEqual(production.video_plan);
  333 |   const history = await read(request, `${base}/documents/${production.id}/history`);
  334 |   expect(history.items.map((row: Row) => row.version)).toEqual([1, 2, 3]);
  335 |   expect(history.items[1].video_plan.segments[0].duration_seconds).toBe(9);
  336 |   expect(await read(request, `${base}/documents/${production.id}`)).toEqual(restored);
  337 |   const exported = await read(request, `${base}/documents/${production.id}/export`);
  338 |   expect(exported.document.id).toBe(restored.id);
  339 |   expect(exported.document.version).toBe(3);
  340 |   expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  341 |   expect(await read(request, `${base}/documents/${source.id}`)).toEqual(source);
  342 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(4);
  343 |   await info.attach('http-file-lifecycle-receipt', { body: JSON.stringify({ verification: 'HTTP/File only, browser launch verified separately', novel_id: novel.id, chapter_id: chapter.id, manuscript_unchanged: true, created_documents: [source.id, director.id, board.id, production.id], concurrent_review_statuses: reviews.map(row => row.status()), versions: history.items.map((row: Row) => row.version), model_called: false, export: exported }, null, 2), contentType: 'application/json' });
  344 | });
  345 | 
  346 | test('real HTTP File V2 scope, cancel and stale source fences remain authoritative', async ({ request }, info) => {
  347 |   const novel = await write(request, '/api/novels', { title: 'V2 HTTP fence fixture' });
  348 |   const foreign = await write(request, '/api/novels', { title: 'V2 HTTP foreign fixture' });
  349 |   const created = await write(request, `/api/novels/${novel.id}/chapters`, { title: 'Owned chapter', content: manuscript });
  350 |   const chapter = await read(request, `/api/chapters/${created.id}`);
  351 |   const outsider = await write(request, `/api/novels/${foreign.id}/chapters`, { title: 'Foreign chapter', content: 'Not authorized as this project source.' });
  352 |   const base = creative(novel.id);
  353 |   const input = { mode: 'SCREENPLAY', title: 'Fence source', source_chapter_ids: [chapter.id], scenes: [{ id: 's1', sequence: 1, heading: 'Scene', source_chapter_id: chapter.id, action: manuscript }] };
  354 |   const source = await write(request, `${base}/documents`, input);
  355 |   const badBinding = await request.post(`${base}/documents`, { data: { ...input, source_chapter_ids: [outsider.id], scenes: [] } });
  356 |   expect(badBinding.status()).toBe(422);
  357 |   expect(await badBinding.json()).toMatchObject({ code: 'EXPERIMENTAL_INVALID', message: 'chapter belongs to another project' });
  358 |   expect((await request.get(`${creative(foreign.id)}/documents/${source.id}`)).status()).toBe(404);
  359 |   const proposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: 1 });
  360 |   const cancelled = await write(request, `${base}/director-proposals/${proposal.id}/cancel`, { expected_version: proposal.version });
  361 |   expect(cancelled.status).toBe('CANCELLED');
  362 |   const rejectedReview = await request.post(`${base}/director-proposals/${proposal.id}/review`, { data: { expected_version: cancelled.version, reviewed_output_digest: proposal.output_digest, title: 'Must not accept cancelled', director_notes: proposal.director_notes } });
  363 |   expect(rejectedReview.status()).toBe(422);
  364 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
  365 |   expect(await read(request, `/api/chapters/${chapter.id}`)).toEqual(chapter);
  366 |   const simultaneous = await Promise.all(['First', 'Second'].map(title => request.put(`${base}/documents/${source.id}`, { data: { ...input, title, expected_version: 1 } })));
  367 |   expect(simultaneous.map(row => row.status()).sort()).toEqual([200, 409]);
  368 |   const current = await read(request, `${base}/documents/${source.id}`);
  369 |   const pendingProposal = await write(request, `${base}/director-proposals`, { source_document_id: source.id, expected_source_version: current.version });
  370 |   const chapterUpdate = await request.put(`/api/chapters/${chapter.id}`, { data: { version: chapter.version, content: manuscript + '\nExplicit second-client source edit.' } });
  371 |   expect(chapterUpdate.status()).toBe(200);
  372 |   expect((await request.get(`${base}/documents/${source.id}`)).status()).toBe(409);
  373 |   expect((await request.get(`${base}/director-proposals/${pendingProposal.id}`)).status()).toBe(409);
  374 |   expect((await read(request, `${base}/documents`)).items).toEqual([]);
  375 |   expect((await request.post(`${base}/documents/${source.id}/derive`, { data: { expected_version: current.version, mode: 'STORYBOARD' } })).status()).toBe(409);
  376 |   await info.attach('http-source-fence-receipt', { body: JSON.stringify({ foreign_binding: badBinding.status(), cancelled_review: rejectedReview.status(), simultaneous_update_statuses: simultaneous.map(row => row.status()), stale_source_read: 409, stale_source_derive: 409, model_called: false }, null, 2), contentType: 'application/json' });
  377 | });
  378 | 
  379 | test('real HTTP default-off gate advertises disabled capabilities and rejects creative reads and writes', async ({ request }, info) => {
  380 |   const novel = await write(request, '/api/novels', { title: 'HTTP default-off fixture' });
  381 |   const base = creative(novel.id);
  382 |   const capabilities = await read(request, `${base}/capabilities`);
  383 |   expect(capabilities.enabled).toBe(false);
  384 |   expect(capabilities.can_mutate).toBe(false);
  385 |   expect((await request.get(`${base}/documents`)).status()).toBe(404);
  386 |   expect((await request.post(`${base}/documents`, { data: { mode: 'SCREENPLAY', title: 'Blocked', source_independent: true } })).status()).toBe(404);
  387 |   await info.attach('http-default-off-receipt', { body: JSON.stringify(capabilities), contentType: 'application/json' });
  388 | });
  389 | 
```