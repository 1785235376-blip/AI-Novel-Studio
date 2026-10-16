import { expect, test, type APIResponse } from '@playwright/test';
import { countPromptPosts, openPromptWorkspace, promptLibrary } from '../../e2e/promptAcceptanceEntry';

const TEXT1 = '  私有 Prompt 第一版\n逐字中文与 emoji 🙂  \n';
const TEXT2 = '  私有 Prompt 第二版\n保留原始换行 🎬  \n';

test('real Prompt authoring, immutable revision, browser HTTP tombstone, and closed production adoption', async ({ page, request }, info) => {
  const token = process.env.STUDIO_PROMPT_R3_BROWSER_TOKEN;
  if (!token) throw new Error('The original packaged bootstrap launcher must issue the session.');
  const errors: string[] = [], calls: { method: string; path: string; status: number }[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith('/api/')) calls.push({ method: response.request().method(), path, status: response.status() });
  });
  const exact = async (response: APIResponse, status: number) => {
    expect(response.status(), await response.text()).toBe(status); return response.json();
  };
  const admin = '/api/collaboration/admin/workspaces/workspace-a';
  let headers: Record<string, string> = { 'X-Session-Token': token };
  let projectId = '';
  const posts = countPromptPosts(page);
  try {
    const project = await exact(await request.post(`${admin}/projects`, { headers,
      data: { title: `Prompt R3 浏览器 ${info.project.name}`, genre: '' } }), 201);
    projectId = project.id;
    const base = `/api/projects/${encodeURIComponent(projectId)}/studio`;
    const navigation = await exact(await request.get(`${admin}/navigation`, { headers }), 200);
    const scope = navigation.eligible_paths.find((value: { project_id: string }) => value.project_id === projectId);
    expect(scope).toBeTruthy(); headers = { ...headers, 'X-Branch-ID': scope.branch_id };
    await exact(await request.post(`${base}/activate`, { headers }), 200);
    await page.goto('/');
    await page.getByText('连接已有创作空间', { exact: true }).click();
    await page.getByLabel('访问凭证', { exact: true }).fill(token);
    await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
    await page.getByRole('button', { name: '我的创作空间', exact: true }).click();
    await page.getByRole('button', { name: new RegExp(`Prompt R3 浏览器 ${info.project.name}`) }).click();
    await openPromptWorkspace(page);
    await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
    const editor = page.getByLabel('正文', { exact: true });
    await editor.fill(TEXT1);
    expect(posts.value()).toBe(0);
    const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/prompts` && response.request().method() === 'POST');
    await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
    const createdResponse = await creating;
    expect(createdResponse.status(), await createdResponse.text()).toBe(201);
    const first = await createdResponse.json();
    await expect(page.locator('.prompt-status')).toContainText('已保存');
    await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).first().click();
    await expect(editor).toHaveValue(TEXT1);
    const firstBody = `${base}/prompts/${first.family_id}/revisions/${first.asset_id}/body`;
    expect((await exact(await request.get(firstBody, { headers }), 200)).value).toBe(TEXT1);
    await editor.fill(TEXT2);
    const revising = page.waitForResponse(response => new URL(response.url()).pathname === `${base}/prompts/${first.family_id}/revisions` && response.request().method() === 'POST');
    await page.getByRole('button', { name: '保存新版本', exact: true }).click();
    const revisedResponse = await revising;
    expect(revisedResponse.status(), await revisedResponse.text()).toBe(201);
    const second = await revisedResponse.json();
    expect(second.family_id).toBe(first.family_id); expect(second.revision).toBe(2);
    expect(second.asset_id).not.toBe(first.asset_id);
    expect(posts.value()).toBe(2);
    const secondBody = `${base}/prompts/${second.family_id}/revisions/${second.asset_id}/body`;
    expect((await exact(await request.get(firstBody, { headers }), 200)).value).toBe(TEXT1);
    expect((await exact(await request.get(secondBody, { headers }), 200)).value).toBe(TEXT2);
    await page.getByRole('button', { name: '比较正文', exact: true }).click();
    await expect(page.locator('.prompt-diff table')).toContainText('第一版');
    await expect(page.locator('.prompt-diff table')).toContainText('第二版');
    await page.screenshot({ path: info.outputPath('real-private-prompt-two-revisions.png'), fullPage: true });

    // The actual production route remains closed. Build its real source and
    // target through their original routes; never replace or enable the gate.
    // Approval intentionally promotes an asset to shared visibility. Keep the
    // private two-revision family untouched and use a different approved source.
    const gateSource = await exact(await request.post(`${base}/prompts`, { headers,
      data: { text: 'Approved source used only for closed production gate', purpose: 'IMAGE', origin: 'MANUAL',
        request_id: `gate-source-${info.project.name}` } }), 201);
    await exact(await request.post(`${base}/prompts/${gateSource.family_id}/revisions/${gateSource.asset_id}/approve`,
      { headers, params: { expected_version: gateSource.asset_version } }), 200);
    const creative = `/api/novels/${projectId}/experimental/creative/documents`;
    const script = await exact(await request.post(creative, { headers, data: { mode: 'SCREENPLAY',
      title: 'Production gate target', source_independent: true,
      scenes: [{ id: 'real-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
    const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers,
      data: { expected_version: script.version, mode: 'STORYBOARD', title: 'Gate target', shot_policy: 'SCENE' } }), 201);
    const target = await exact(await request.get(`${base}/documents/${board.id}/prompt-adoption`, { headers }), 200);
    const source = await exact(await request.get(`${base}/prompts/${gateSource.family_id}/revisions/${gateSource.asset_id}/body`, { headers }), 200);
    const refusal = await page.evaluate(async ({ url, headers, body }) => {
      const response = await fetch(url, { method: 'POST', headers: { ...headers, 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
      return { status: response.status, body: await response.json() };
    }, { url: `${base}/documents/${board.id}/shots/${board.shots[0].id}/prompt-adoption`, headers,
      body: { shot_id: board.shots[0].id, family_id: gateSource.family_id, asset_id: gateSource.asset_id,
        revision: 1, expected_digest: source.digest, expected_version: target.version,
        expected_digest_target: target.digest, request_id: `closed-${info.project.name}` } });
    expect(refusal.status).toBe(503);
    expect(refusal.body.detail.code).toBe('PROMPT_ADOPTION_WRITE_TIME_UNVERIFIED');
    expect((await exact(await request.get(`${creative}/${board.id}`, { headers }), 200)).version).toBe(board.version);

    // There is no Prompt delete button in the shipped editor. This is an
    // explicitly authorized real browser HTTP action, followed by rendered UI
    // history verification; it is not claimed as a delete-button workflow.
    // Generic discovery remains unable to read this unapproved private asset;
    // the dedicated Prompt receipt supplies its original owner's CAS version.
    const hidden = await request.get(`${base}/assets/${second.asset_id}`, { headers });
    expect(hidden.status()).toBe(404); expect((await hidden.json()).detail.code).toBe('EXPERIMENTAL_NOT_FOUND');
    const deleted = await page.evaluate(async ({ url, headers }) => {
      const response = await fetch(url, { method: 'DELETE', headers });
      return { status: response.status, body: await response.json() };
    }, { url: `${base}/assets/${second.asset_id}?expected_version=${second.asset_version}`, headers });
    expect(deleted.status).toBe(200); expect(deleted.body.deleted_at).toBeTruthy();
    expect(deleted.body.version).toBe(second.asset_version + 1);
    expect(JSON.stringify(deleted.body)).not.toContain('_owner_actor_id');
    const tombstone = await exact(await request.get(secondBody, { headers }), 200);
    expect(tombstone).toMatchObject({ state: 'DELETED', value: null, digest: null, available: false, verified: false });
    expect(JSON.stringify(tombstone)).not.toContain(TEXT2);
    const detail = await exact(await request.get(`${base}/prompts/${second.family_id}`, { headers }), 200);
    expect(detail.versions.find((value: { asset_id: string }) => value.asset_id === second.asset_id).available).toBe(false);
    await promptLibrary(page).getByRole('button', { name: '重新读取', exact: true }).click();
    await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).filter({ hasText: first.family_id.slice(0, 8) }).click();
    const history = page.getByRole('region', { name: '版本历史' });
    await expect(history).toContainText('已删除 / 不可读');
    await history.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-private-prompt-tombstone-history.png'), fullPage: true });
    const repeat = await exact(await request.delete(`${base}/assets/${second.asset_id}`, { headers,
      params: { expected_version: deleted.body.version } }), 200);
    expect(repeat.version).toBe(deleted.body.version);
    const restored = await request.post(`${base}/assets/${second.asset_id}/restore`, { headers,
      data: { expected_version: deleted.body.version } });
    expect(restored.status()).toBe(404); expect((await restored.json()).detail.code).toBe('EXPERIMENTAL_NOT_FOUND');
    const geometry = await page.evaluate(() => ({ width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth, headerHeight: document.querySelector('.global-header')!.getBoundingClientRect().height }));
    expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width); expect(geometry.headerHeight).toBe(56);
    expect(errors).toEqual([]);
    expect(calls.filter(value => !['GET', 'HEAD', 'OPTIONS'].includes(value.method)
      && /\/(dispatch|generate|graph-runs|media\/tasks|jobs)(\/|$)/.test(value.path))).toEqual([]);
    await info.attach('redacted-real-browser-evidence', { body: JSON.stringify({ production_gate: false,
      production_adoption_status: 503, ui_authoring: true, deletion_transport: 'real browser HTTP; no delete UI exists',
      real_persistence: true, response_mocks: false, model_calls_requested: false, geometry, calls }), contentType: 'application/json' });
  } finally {
    posts.dispose();
    if (projectId) {
      const cleanup = await request.delete(`${admin}/projects/${projectId}`, { headers });
      expect(cleanup.status(), await cleanup.text()).toBe(204);
    }
  }
});
