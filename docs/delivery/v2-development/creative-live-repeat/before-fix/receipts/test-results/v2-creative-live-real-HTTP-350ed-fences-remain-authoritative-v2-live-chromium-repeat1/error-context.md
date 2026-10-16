# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: v2-creative-live.spec.ts >> real HTTP File V2 scope, cancel and stale source fences remain authoritative
- Location: tests/e2e/v2-creative-live.spec.ts:346:1

# Error details

```
Error: expect(received).toHaveLength(expected)

Expected length: 1
Received length: 2
Received array:  [{"created_at": "2026-10-09T07:28:45.510039+00:00", "created_by": "local-author", "director_notes": [], "history": [{"created_at": "2026-10-09T07:28:45.510039+00:00", "created_by": "local-author", "director_notes": [], "id": "008a3993-63fa-42f4-880e-fc85782a5f98", "mode": "SCREENPLAY", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "scenes": [{"action": "合成验收正文：林默走到云港。她说：“下一幕由我们自己决定。”", "characters": [], "dialogue": [], "director_notes": [], "emotion": "", "heading": "Scene", "id": "s1", "location": "", "sequence": 1, "source_chapter_id": "v2-http-fence-fixture:1", "time": ""}], "schema_version": 1, "scope": {"mode": "local", "novel_id": "v2-http-fence-fixture"}, "shots": [], "source_chapter_ids": ["v2-http-fence-fixture:1"], "source_documents": {}, "source_evidence": {"v2-http-fence-fixture:1": {"digest": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "version": 1}}, "source_independent": false, "source_privacy": {"v2-http-fence-fixture:1": {"branch_id": null, "chapter_id": "v2-http-fence-fixture:1", "chapter_version": 1, "content_sha256": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "reviewed": false, "reviewed_at": null, "reviewed_by": null, "stale": false}}, "status": "DRAFT", "title": "Fence source", "updated_at": "2026-10-09T07:28:45.510039+00:00", "updated_by": "local-author", "version": 1, "video_plan": null}], "id": "008a3993-63fa-42f4-880e-fc85782a5f98", "mode": "SCREENPLAY", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "scenes": [{"action": "合成验收正文：林默走到云港。她说：“下一幕由我们自己决定。”", "characters": [], "dialogue": [], "director_notes": [], "emotion": "", "heading": "Scene", "id": "s1", "location": "", "sequence": 1, "source_chapter_id": "v2-http-fence-fixture:1", "time": ""}], "schema_version": 1, "scope": {"mode": "local", "novel_id": "v2-http-fence-fixture"}, "shots": [], "source_chapter_ids": ["v2-http-fence-fixture:1"], "source_documents": {}, "source_evidence": {"v2-http-fence-fixture:1": {"digest": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "version": 1}}, "source_independent": false, "source_privacy": {"v2-http-fence-fixture:1": {"branch_id": null, "chapter_id": "v2-http-fence-fixture:1", "chapter_version": 1, "content_sha256": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "reviewed": false, "reviewed_at": null, "reviewed_by": null, "stale": false}}, "status": "DRAFT", "title": "First", "updated_at": "2026-10-09T07:28:45.683192+00:00", "updated_by": "local-author", "version": 2, "video_plan": null}, {"created_at": "2026-10-09T07:28:47.249418+00:00", "created_by": "local-author", "director_notes": [], "history": [], "id": "00e1d85d-6364-4eb6-8125-ce05e95f8dba", "mode": "SCREENPLAY", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "scenes": [{"action": "合成验收正文：林默走到云港。她说：“下一幕由我们自己决定。”", "characters": [], "dialogue": [], "director_notes": [], "emotion": "", "heading": "Scene", "id": "s1", "location": "", "sequence": 1, "source_chapter_id": "v2-http-fence-fixture:1", "time": ""}], "schema_version": 1, "scope": {"mode": "local", "novel_id": "v2-http-fence-fixture"}, "shots": [], "source_chapter_ids": ["v2-http-fence-fixture:1"], "source_documents": {}, "source_evidence": {"v2-http-fence-fixture:1": {"digest": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "version": 1}}, "source_independent": false, "source_privacy": {"v2-http-fence-fixture:1": {"branch_id": null, "chapter_id": "v2-http-fence-fixture:1", "chapter_version": 1, "content_sha256": "1790ab9ac5e517cddce83fcc5034de488de38f7d3c69072796163f3b52a44a7a", "novel_id": "v2-http-fence-fixture", "privacy_level": "LOCAL_ONLY", "reviewed": false, "reviewed_at": null, "reviewed_by": null, "stale": false}}, "status": "DRAFT", "title": "Fence source", "updated_at": "2026-10-09T07:28:47.249418+00:00", "updated_by": "local-author", "version": 1, "video_plan": null}]
```

# Test source

```ts
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
> 364 |   expect((await read(request, `${base}/documents`)).items).toHaveLength(1);
      |                                                            ^ Error: expect(received).toHaveLength(expected)
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