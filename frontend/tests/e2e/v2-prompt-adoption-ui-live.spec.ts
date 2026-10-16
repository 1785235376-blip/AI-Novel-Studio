import { createHash } from 'node:crypto';
import { expect, test, type APIResponse } from '@playwright/test';
import { openPromptWorkspace, promptLibrary } from '../../e2e/promptAcceptanceEntry';

const FIRST = '  采用成功闭环 第一版\n逐字中文与 emoji 🙂  \n';
const NEWER = '  来源家族第二版；不应自动替换已采用修订 🎬\n';
const CONSENT = '我已核对来源正文、修订与当前镜头版本，确认替换画面提示词。';
const canonical = (value: unknown): string => {
  if (Array.isArray(value)) return `[${value.map(canonical).join(',')}]`;
  if (value !== null && typeof value === 'object') {
    const row = value as Record<string, unknown>;
    return `{${Object.keys(row).sort().map(key => `${JSON.stringify(key)}:${canonical(row[key])}`).join(',')}}`;
  }
  const rendered = JSON.stringify(value);
  if (rendered === undefined) throw new Error('Canonical owner data contains undefined.');
  return rendered;
};

test('isolated original button commits bound Prompt and reload preserves its exact source pin', async ({ page, request }, info) => {
  const token = process.env.STUDIO_PROMPT_ADOPTION_UI_BROWSER_TOKEN;
  if (!token) throw new Error('The isolated launcher must obtain an original packaged bootstrap session.');
  const errors: string[] = [], calls: { method: string; path: string; status: number }[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith('/api/')) calls.push({ method: response.request().method(), path, status: response.status() });
  });
  const exact = async (response: APIResponse, status: number) => {
    expect(response.status(), await response.text()).toBe(status);
    return response.json();
  };
  const admin = '/api/collaboration/admin/workspaces/workspace-a';
  const projectGlobalHeaders = { 'X-Session-Token': token };
  let headers: Record<string, string> = projectGlobalHeaders;
  let projectId = '';
  const title = `采用 UI 验收 ${info.project.name}`;
  const boardTitle = `真实分镜 ${info.project.name}`;
  try {
    const project = await exact(await request.post(`${admin}/projects`, { headers,
      data: { title, genre: '' } }), 201);
    projectId = project.id;
    const navigation = await exact(await request.get(`${admin}/navigation`, { headers }), 200);
    const path = navigation.eligible_paths.find((row: { project_id: string }) => row.project_id === projectId);
    expect(path).toBeTruthy(); headers = { ...headers, 'X-Branch-ID': path.branch_id };
    const studio = `/api/projects/${projectId}/studio`;
    await exact(await request.post(`${studio}/activate`, { headers }), 200);
    // These original legacy records are explicitly project-global. Their real
    // route refuses a branch header rather than pretending to be a branch source.
    const character = await exact(await request.put(`/api/novels/${projectId}/characters/ui-bound-character`,
      { headers: projectGlobalHeaders, data: { name: '采用时真实角色目标' } }), 200);
    const characters = await exact(await request.get(`/api/novels/${projectId}/characters`, { headers: projectGlobalHeaders }), 200);
    const originalCharacter = characters.find((row: { id: string }) => row.id === character.id);
    expect(originalCharacter).toBeTruthy();
    const characterDigest = createHash('sha256').update(canonical(originalCharacter)).digest('hex');
    const creative = `/api/novels/${projectId}/experimental/creative/documents`;
    const script = await exact(await request.post(creative, { headers, data: { mode: 'SCREENPLAY',
      title: `真实来源剧本 ${info.project.name}`, source_independent: true,
      scenes: [{ id: 'real-ui-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
    const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers,
      data: { expected_version: script.version, mode: 'STORYBOARD', title: boardTitle, shot_policy: 'SCENE' } }), 201);
    expect(board.shots).toHaveLength(1);
    const shotId = board.shots[0].id;
    const ownerPath = `${creative}/${board.id}`;
    const adoptionPath = `${studio}/documents/${board.id}/shots/${shotId}/prompt-adoption`;
    const projectionPath = `${studio}/documents/${board.id}/prompt-adoption`;

    // Reconnect, project choice and module changes are all existing product UI.
    // A full reload can return to the entry screen or restore the same project.
    const enterProject = async () => {
      await page.goto('/');
      const currentScope = page.getByRole('navigation', { name: '当前创作范围', exact: true }).filter({ hasText: title });
      await expect.poll(async () =>
        await page.getByText('连接已有创作空间', { exact: true }).isVisible()
        || await page.getByLabel('访问凭证', { exact: true }).isVisible()
        || await page.getByRole('button', { name: '我的创作空间', exact: true }).isVisible()
        || await currentScope.isVisible(), { timeout: 30_000 }).toBe(true);
      if (await page.getByText('连接已有创作空间', { exact: true }).isVisible()) {
        await page.getByText('连接已有创作空间', { exact: true }).click();
        await expect(page.getByLabel('访问凭证', { exact: true })).toBeVisible();
      }
      if (await page.getByLabel('访问凭证', { exact: true }).isVisible()) {
        await page.getByLabel('访问凭证', { exact: true }).fill(token);
        await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
        await expect(page.getByRole('button', { name: '我的创作空间', exact: true })).toBeVisible();
      }
      const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
      const projectChoice = page.getByRole('button', { name: new RegExp(title) });
      if (await workspace.isVisible()) {
        await workspace.click();
        await expect(projectChoice).toBeVisible();
      }
      if (await projectChoice.isVisible()) await projectChoice.click();
      await expect(currentScope).toBeVisible();
    };
    const openBoard = async () => {
      await page.getByRole('tab', { name: '小说', exact: true }).click();
      await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
      await page.getByRole('tab', { name: /^分镜/ }).click();
      await page.getByRole('region', { name: '创作文档', exact: true })
        .getByRole('button', { name: new RegExp(boardTitle) }).click();
      await page.getByRole('button', { name: '按需打开镜头工作区', exact: true }).click();
      const shots = page.getByRole('region', { name: '分镜工作区', exact: true });
      await shots.getByRole('button', { name: '读取已保存分镜', exact: true }).click();
      await shots.getByRole('button', { name: `镜头 1（身份 ${shotId}）`, exact: true }).click();
      return shots;
    };
    const pin = async () => {
      const show = page.getByRole('button', { name: '查看 Prompt 采用来源', exact: true });
      if (await show.isVisible()) await show.click();
      const value = page.locator('.prompt-adoption-record');
      await expect(value).toBeVisible();
      return value;
    };

    await enterProject();
    await openPromptWorkspace(page);
    await page.getByRole('button', { name: '新建 Prompt', exact: true }).click();
    await page.getByLabel('正文', { exact: true }).fill(FIRST);
    await page.getByLabel('角色 ID', { exact: true }).fill(character.id);
    const creating = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts`
      && response.request().method() === 'POST');
    await page.getByRole('button', { name: '保存为新 Prompt', exact: true }).click();
    const creation = await creating;
    expect(creation.status(), await creation.text()).toBe(201);
    expect(creation.request().postDataJSON().character_ids).toEqual([character.id]);
    const source = await creation.json();
    await expect(page.locator('.prompt-status')).toContainText('已保存');

    await openBoard();
    await page.getByRole('button', { name: '核对 Prompt 采用条件', exact: true }).click();
    const operation = page.getByRole('region', { name: 'Prompt 采用操作', exact: true });
    await operation.getByRole('combobox', { name: 'Prompt 来源家族', exact: true }).selectOption(source.family_id);
    await operation.getByRole('button', { name: '读取所选 Prompt 修订', exact: true }).click();
    await expect(operation).toContainText('采用成功闭环 第一版');
    const approving = page.waitForResponse(response => new URL(response.url()).pathname
      === `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/approve`
      && response.request().method() === 'POST');
    await operation.getByRole('button', { name: '批准所选 Prompt 修订', exact: true }).click();
    expect((await approving).status()).toBe(200);
    const sourceBodyPath = `${studio}/prompts/${source.family_id}/revisions/${source.asset_id}/body`;
    const body = await exact(await request.get(sourceBodyPath, { headers }), 200);
    expect(body).toMatchObject({ value: FIRST, verified: true, available: true });
    const before = await exact(await request.get(ownerPath, { headers }), 200);
    const target = await exact(await request.get(projectionPath, { headers }), 200);
    expect(target.write_enabled).toBe(true);
    expect(target.version).toBe(before.version);
    await expect(operation).toContainText(source.family_id);
    await expect(operation).toContainText(source.asset_id);
    await expect(operation).toContainText(body.digest);
    const adopt = operation.getByRole('button', { name: '采用到当前镜头', exact: true });
    await expect(adopt).toBeDisabled();
    await operation.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-form.png'), fullPage: true });
    await adopt.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-ui-adoption-before-confirm-checkbox.png'), fullPage: true });
    await operation.getByRole('checkbox', { name: CONSENT, exact: true }).check();
    await expect(adopt).toBeEnabled();
    const adopting = page.waitForResponse(response => new URL(response.url()).pathname === adoptionPath
      && response.request().method() === 'POST');
    // The successful adoption is ONLY this original product button click.
    await adopt.click();
    const response = await adopting;
    expect(response.status(), await response.text()).toBe(200);
    const originalRequest = response.request().postDataJSON();
    const receipt = await response.json();
    expect(originalRequest).toMatchObject({ shot_id: shotId, family_id: source.family_id, asset_id: source.asset_id,
      revision: 1, expected_digest: body.digest, expected_version: before.version, expected_digest_target: target.digest });
    expect(receipt).toMatchObject({ committed: true, replayed: false, document_id: board.id,
      shot_id: shotId, version: before.version + 1 });
    const proof = receipt.adoption;
    expect(proof).toMatchObject({ document_id: board.id, shot_id: shotId, family_id: source.family_id,
      asset_id: source.asset_id, revision: 1, digest: body.digest, target_version: before.version,
      target_digest: target.digest, result_version: before.version + 1, request_id: originalRequest.request_id,
      source_binding_contract: 'prompt-adoption-bindings/1', source_bindings_verified: true });
    expect(proof.source_snapshot).toHaveLength(1);
    expect(proof.source_snapshot[0]).toMatchObject({ kind: 'CHARACTER', id: character.id,
      owner: 'NovelService.characters', digest: characterDigest, resolution: 'KNOWN', verification: 'WRITE_TIME_OWNER_LEASE' });
    expect(proof.source_snapshot[0].project_incarnation).toBeTruthy();
    expect(JSON.stringify(proof)).not.toContain(character.name);
    const committed = await exact(await request.get(ownerPath, { headers }), 200);
    expect(committed.version).toBe(before.version + 1);
    expect(committed.shots.find((row: { id: string }) => row.id === shotId).frame_prompt).toBe(FIRST);
    expect(committed.prompt_adoptions).toHaveLength(1);
    expect(committed.prompt_adoptions[0]).toEqual(proof);
    await expect(page.getByText('已回读确认 Prompt 采用；可查看固定的 Prompt 采用来源。', { exact: true })).toBeVisible();
    await page.locator('.creative-shot-card').first().click();
    await expect(page.getByRole('textbox', { name: '画面描述', exact: true })).toHaveValue(FIRST);
    await page.getByRole('textbox', { name: '画面描述', exact: true }).scrollIntoViewIfNeeded();
    const firstPin = await pin();
    await expect(firstPin).toContainText(source.asset_id);
    await expect(firstPin).toContainText(body.digest);
    await expect(firstPin).toContainText('仍然生效');
    await firstPin.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-ui-adoption-committed-pin.png'), fullPage: true });

    // A captured original DTO is replayed only as an additional idempotency
    // check. It is never presented as the successful UI interaction above.
    const replay = await exact(await request.post(adoptionPath, { headers, data: originalRequest }), 200);
    expect(replay).toMatchObject({ committed: true, replayed: true, version: committed.version });
    expect(replay.adoption).toEqual(proof);
    expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);
    const reused = await request.post(adoptionPath, { headers, data: { ...originalRequest, expected_digest: 'f'.repeat(64) } });
    expect(reused.status(), await reused.text()).toBe(422);
    expect((await reused.json()).detail).toEqual({ code: 'EXPERIMENTAL_INVALID', message: 'PROMPT_ADOPTION_REQUEST_REUSED' });
    expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);

    // A real page reload and existing product navigation must reconstruct the
    // owner state and pinned source. No React state or localStorage is injected.
    await enterProject();
    await openBoard();
    await page.locator('.creative-shot-card').first().click();
    await expect(page.getByRole('textbox', { name: '画面描述', exact: true })).toHaveValue(FIRST);
    const reopenedPin = await pin();
    await expect(reopenedPin).toContainText(source.family_id);
    await expect(reopenedPin).toContainText(`${source.asset_id} · r1`);
    await expect(reopenedPin).toContainText(body.digest);
    await expect(reopenedPin).toContainText('仍然生效');
    const reopened = await exact(await request.get(ownerPath, { headers }), 200);
    expect(reopened).toEqual(committed);
    expect(calls.filter(call => call.method === 'POST' && call.path === adoptionPath)).toHaveLength(1);
    await reopenedPin.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-ui-adoption-reopened-pin.png'), fullPage: true });

    // Advancing the source family cannot silently repin this historical shot.
    await page.getByRole('button', { name: '返回经典工作区', exact: true }).click();
    await page.getByRole('tab', { name: '图片', exact: true }).click();
    await openPromptWorkspace(page);
    await promptLibrary(page).getByRole('button', { name: /IMAGE/ }).filter({ hasText: source.family_id.slice(0, 8) }).click();
    await page.getByLabel('正文', { exact: true }).fill(NEWER);
    const revising = page.waitForResponse(response => new URL(response.url()).pathname === `${studio}/prompts/${source.family_id}/revisions`
      && response.request().method() === 'POST');
    await page.getByRole('button', { name: '保存新版本', exact: true }).click();
    expect((await revising).status()).toBe(201);
    await expect(page.locator('.prompt-status')).toContainText('已保存');
    await openBoard();
    const historicalPin = await pin();
    await expect(historicalPin).toContainText(`${source.asset_id} · r1`);
    await expect(historicalPin).toContainText(body.digest);
    await expect(historicalPin).toContainText('存在更新版本，需要重新采用');
    expect(await exact(await request.get(ownerPath, { headers }), 200)).toEqual(committed);
    await historicalPin.scrollIntoViewIfNeeded();
    await page.screenshot({ path: info.outputPath('real-ui-adoption-historical-source-pin.png'), fullPage: true });
    const geometry = await page.evaluate(() => ({ width: innerWidth,
      scrollWidth: document.documentElement.scrollWidth,
      headerHeight: document.querySelector('.global-header')!.getBoundingClientRect().height }));
    expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.width);
    expect(geometry.headerHeight).toBe(56);
    expect(errors).toEqual([]);
    expect(calls.filter(call => !['GET', 'HEAD', 'OPTIONS'].includes(call.method)
      && /\/(dispatch|generate|graph-runs|media\/tasks|jobs)(\/|$)/.test(call.path))).toEqual([]);
    await info.attach('redacted-original-ui-adoption', { body: JSON.stringify({ isolated_acceptance: true,
      production_literal_gate: false, response_mocks: false, ui_button_post_status: 200,
      request: originalRequest, receipt, owner_before: before, owner_committed: committed,
      owner_reopened: reopened, source_family_advanced_without_repin: true, same_request_replayed_without_revision: true,
      declared_binding_verification: 'write-time observation; not current dependency liveness',
      model_execution: 'NOT_REQUESTED', model_counter: 'NOT_INSTRUMENTED', geometry, calls }), contentType: 'application/json' });
  } finally {
    if (projectId) {
      const cleanup = await request.delete(`${admin}/projects/${projectId}`, { headers });
      expect(cleanup.status(), await cleanup.text()).toBe(204);
    }
  }
});
