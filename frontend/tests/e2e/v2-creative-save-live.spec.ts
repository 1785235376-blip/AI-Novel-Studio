import { createHash, randomUUID } from 'node:crypto';
import { expect, test, type APIRequestContext, type APIResponse, type Page, type Request, type Route, type TestInfo } from '@playwright/test';

type Row = Record<string, any>;
type Project = { id: string; title: string; path: Row; headers: Record<string, string> };
type Document = { project: Project; id: string; title: string; mode: 'SCREENPLAY' | 'STORYBOARD'; path: string; body: Row; owner: Row };
const sha = (raw: string) => createHash('sha256').update(raw).digest('hex');
const admin = '/api/collaboration/admin/workspaces/workspace-a';
const tabs = (page: Page, name: string) => page.getByRole('tab', { name, exact: true });
const canvas = (page: Page) => page.getByRole('region', { name: '创作画布', exact: true });
const frame = (page: Page) => page.evaluate(() => new Promise<void>(resolve =>
  requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));
async function exact(response: APIResponse, status: number) {
  expect(response.status(), await response.text()).toBe(status);
  return status === 204 ? null : response.json();
}

class Dispatch {
  readonly evidence: Row = {};
  private releaseHeld!: () => void;
  private ready = new Promise<void>(resolve => { this.releaseHeld = resolve; });
  private request?: Request;
  constructor(readonly page: Page, readonly document: Document, readonly method: 'GET' | 'PUT', readonly suffix: string,
      readonly phase: string, readonly token: string) {}
  private failed = (request: Request) => {
    if (request === this.request) this.evidence.request_failed = request.failure()?.errorText;
  };
  private handler = async (route: Route) => {
    const request = route.request();
    if (request.method() !== this.method) return route.fallback();
    expect(this.request).toBeUndefined(); this.request = request;
    const headers = request.headers();
    expect(headers['x-session-token']).toBe(this.token);
    expect(headers['x-branch-id']).toBe(this.document.project.path.branch_id);
    Object.assign(this.evidence, { phase: this.phase, url: request.url(), method: request.method(),
      project_id: this.document.project.id, document_id: this.document.id,
      branch_id: headers['x-branch-id'], token_sha256: sha(this.token), held_at: Date.now(),
      original_request_body: this.method === 'PUT' ? request.postDataJSON() : null,
      request_not_dispatched_until_release: true, response_fabricated: false });
    await this.ready; this.evidence.continue_at = Date.now();
    try {
      await route.continue(); this.evidence.continue_returned = true;
      const response = await request.response();
      if (response) {
        const failure = await response.finished();
        if (failure) this.evidence.finished_error = String(failure);
        const raw = await response.text();
        Object.assign(this.evidence, { status: response.status(), response_raw_body: raw,
          response_body_sha256: sha(raw), response_body: JSON.parse(raw), response_at: Date.now() });
      }
    } catch (error) { this.evidence.transport_error = String(error); }
  };
  async install() {
    this.page.on('requestfailed', this.failed);
    await this.page.route(`**${this.document.path}${this.suffix}`, this.handler);
  }
  async held() { await expect.poll(() => this.evidence.held_at ?? null).not.toBeNull(); }
  release() { this.releaseHeld(); }
  async delivered(status: number) {
    await expect.poll(() => this.evidence.status ?? this.evidence.request_failed ?? null).toBe(status);
    await frame(this.page); return this.evidence.response_body;
  }
  async dispose() {
    this.release(); await this.page.unroute(`**${this.document.path}${this.suffix}`, this.handler);
    this.page.off('requestfailed', this.failed);
  }
}

function rig(page: Page, request: APIRequestContext, info: TestInfo) {
  const token = process.env.STUDIO_CREATIVE_SAVE_BROWSER_TOKEN;
  if (!token) throw new Error('Use the ordinary LocalSessionBootstrap Creative save-state launcher.');
  const globalHeaders = { 'X-Session-Token': token };
  const projects: Project[] = [], documents: Document[] = [], gates: Dispatch[] = [];
  const records: Row[] = [], calls: Row[] = [], errors: string[] = [], failures: Row[] = [];
  page.on('pageerror', error => errors.push(error.message));
  page.on('response', response => {
    const path = new URL(response.url()).pathname;
    if (path.startsWith('/api/')) calls.push({ path, method: response.request().method(), status: response.status() });
  });
  page.on('requestfailed', request => failures.push({ path: new URL(request.url()).pathname,
    method: request.method(), failure: request.failure()?.errorText }));
  const project = async (suffix: string, extraBranch = false): Promise<Project> => {
    const title = `真实创作保存 ${info.project.name} ${suffix}`;
    const created = await exact(await request.post(`${admin}/projects`, { headers: globalHeaders, data: { title, genre: '' } }), 201);
    let navigation = await exact(await request.get(`${admin}/navigation`, { headers: globalHeaders }), 200);
    let path = navigation.eligible_paths.find((row: Row) => row.project_id === created.id);
    const owned: Project = { id: created.id, title, path, headers: { ...globalHeaders, 'X-Branch-ID': path.branch_id } };
    projects.push(owned);
    if (extraBranch) {
      const branch = await exact(await request.post(`${admin}/projects/${created.id}/storylines/${path.storyline_id}/branches`,
        { headers: globalHeaders, data: { name: '真实保存另一分支' } }), 201);
      navigation = await exact(await request.get(`${admin}/navigation`, { headers: globalHeaders }), 200);
      path = navigation.eligible_paths.find((row: Row) => row.project_id === created.id && row.branch_id === branch.id);
      expect(path).toBeTruthy(); owned.path = path; owned.headers['X-Branch-ID'] = path.branch_id;
    }
    await exact(await request.post(`/api/projects/${owned.id}/studio/activate`, { headers: owned.headers }), 200);
    return owned;
  };
  const document = async (owned: Project, suffix: string, mode: Document['mode'] = 'STORYBOARD'): Promise<Document> => {
    const scene = randomUUID();
    const body = { mode, title: `手动文档 ${suffix}`, source_independent: true,
      scenes: [{ id: scene, sequence: 1, heading: 'INT. SAVE ROOM - DAY', action: `原始手动内容 ${suffix}` }],
      shots: mode === 'STORYBOARD' ? [{ id: randomUUID(), number: 1, scene_id: scene, frame_prompt: `原始手动画面 ${suffix}` }] : [] };
    const base = `/api/novels/${owned.id}/experimental/creative/documents`;
    const owner = await exact(await request.post(base, { headers: owned.headers, data: body }), 201);
    expect(owner.version).toBe(1); expect(owner.scope.branch_id).toBe(owned.path.branch_id);
    const value = { project: owned, id: owner.id, title: owner.title, mode, path: `${base}/${owner.id}`, body, owner };
    documents.push(value);
    if (mode === 'STORYBOARD') await gateFalse(value);
    records.push({ phase: 'original_manual_document_created', source: 'original_api', project_id: owned.id,
      branch_id: owned.path.branch_id, owner });
    return value;
  };
  const gateFalse = async (value: Document) => {
    const projection = await exact(await request.get(`/api/projects/${value.project.id}/studio/documents/${value.id}/prompt-adoption`,
      { headers: value.project.headers }), 200);
    expect(projection.write_enabled).toBe(false);
    records.push({ phase: 'ordinary_production_adoption_gate', write_enabled: false, document_id: value.id });
  };
  const owner = async (value: Document, phase: string) => {
    const row = await exact(await request.get(value.path, { headers: value.project.headers }), 200);
    const overview = await exact(await request.get(`/api/projects/${value.project.id}/studio`, { headers: value.project.headers }), 200);
    expect(row.novel_id).toBe(value.project.id); expect(row.scope.branch_id).toBe(value.project.path.branch_id);
    expect(row.project_incarnation).toBe(overview.project.incarnation);
    records.push({ phase, source: 'standalone_original_owner_readback', owner: row, overview,
      project_id: value.project.id, branch_id: value.project.path.branch_id });
    return row;
  };
  const choose = async (owned: Project) => {
    const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
    const choice = page.getByRole('button').filter({ hasText: owned.title }).filter({ hasText: owned.path.branch_name });
    await expect.poll(async () => await workspace.isVisible() || await choice.isVisible()).toBe(true);
    if (await workspace.isVisible()) await workspace.click();
    await choice.click();
    await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true })).toContainText(owned.title);
    await expect(tabs(page, '图片')).toHaveAttribute('aria-selected', 'true');
    await expect(page.locator('[aria-label="独立工作区内容"]')).toBeVisible();
  };
  const connect = async (owned: Project) => {
    await page.goto('/');
    await page.getByText('连接已有创作空间', { exact: true }).click();
    await page.getByLabel('访问凭证', { exact: true }).fill(token);
    await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
    await choose(owned);
  };
  const open = async (value: Document, enter = true) => {
    if (enter) {
      await tabs(page, '小说').click();
      await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
    }
    await page.getByRole('tab', { name: value.mode === 'SCREENPLAY' ? /^剧本/ : /^分镜/ }).click();
    await page.getByRole('region', { name: '创作文档', exact: true }).getByRole('button').filter({ hasText: value.title }).click();
    await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(value.title);
  };
  const gate = async (value: Document, method: 'GET' | 'PUT', suffix: string, phase: string) => {
    const dispatch = new Dispatch(page, value, method, suffix, phase, token);
    gates.push(dispatch); await dispatch.install(); return dispatch;
  };
  const screenshot = async (name: string) => {
    records.push({ phase: name, source: 'original_browser_dom_read_only',
      canvas_text: await canvas(page).innerText(), footer_text: await page.locator('.status-bar').innerText(),
      title: await canvas(page).getByLabel('文档标题', { exact: true }).inputValue(),
      action: await canvas(page).getByLabel('动作与叙事', { exact: true }).inputValue() });
    const path = info.outputPath(name + '.png'); await page.screenshot({ path, fullPage: true });
    await info.attach(name, { path, contentType: 'image/png' });
  };
  const finish = async () => {
    const cleanupErrors: string[] = [];
    await page.context().setOffline(false);
    for (const value of gates) try { await value.dispose(); } catch (error) { cleanupErrors.push(String(error)); }
    for (const owned of projects.reverse()) try {
      const response = await request.delete(`${admin}/projects/${owned.id}`, { headers: globalHeaders });
      records.push({ phase: 'owned_project_cleanup', project_id: owned.id, status: response.status() });
      expect(response.status(), await response.text()).toBe(204);
    } catch (error) { cleanupErrors.push(String(error)); }
    await info.attach('creative-save-state-evidence', { body: Buffer.from(JSON.stringify({ token_sha256: sha(token),
      response_fabrication: false, identity_or_state_injection: false, production_gate_override: false,
      model_execution: 'NOT_REQUESTED', model_counter: 'NOT_INSTRUMENTED',
      records, dispatches: gates.map(gate => gate.evidence), calls, failures, errors, cleanupErrors }, null, 2)),
    contentType: 'application/json' });
    expect(errors).toEqual([]); expect(cleanupErrors).toEqual([]);
    expect(calls.filter(call => call.method === 'POST' && call.path.endsWith('/prompt-adoption'))).toEqual([]);
    expect(calls.filter(call => call.method === 'POST' && /\/(dispatch|generate|generation|inference)(\/|$)/.test(call.path))).toEqual([]);
  };
  return { project, document, records, calls, failures, token, owner, choose, connect, open, gate, gateFalse, screenshot, finish };
}

const CURRENT_STATUS = '当前创作文档保存状态';
const state = (page: Page) => page.getByRole('status', { name: CURRENT_STATUS, exact: true });
async function saved(page: Page, version: number) {
  await expect(state(page)).toHaveText(`当前分镜：已保存 · v${version}`);
  await expect(canvas(page).getByText(`已保存 · v${version}`, { exact: true })).toBeVisible();
  await expect(canvas(page).getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled();
  await expect(page.locator('.status-bar')).not.toContainText('正在打开章节');
}
async function dirty(page: Page, version: number) {
  await expect(state(page)).toHaveText(`当前分镜：未保存更改 · 基于 v${version}`);
  await expect(canvas(page).getByText('未保存', { exact: true })).toBeVisible();
}
async function uncertain(page: Page, version: number) {
  await expect(state(page)).toHaveText(`当前分镜：需核对保存结果 · 本地草稿保留 · 基于 v${version}`);
  await expect(canvas(page).getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled();
}

test('manual persisted v1, exact edits, real save CAS v2 and refresh agree; other-stage dirty remains separate',
  async ({ page, request }, info) => {
    const r = rig(page, request, info);
    try {
      const owned = await r.project('保存主线');
      const first = await r.document(owned, '保存 A');
      const cleanOther = await r.document(owned, '已保存 B');
      const screenplay = await r.document(owned, '剧本 C', 'SCREENPLAY');
      await r.connect(owned); await r.open(first); await saved(page, 1);
      await r.screenshot('manual-v1-initial-current-saved');
      const action = canvas(page).getByLabel('动作与叙事', { exact: true });
      const original = first.owner.scenes[0].action;
      await action.fill(original); await saved(page, 1);
      await action.fill(original + ' '); await dirty(page, 1);
      await action.fill(original); await saved(page, 1);
      expect(r.calls.filter(call => call.path === first.path && call.method === 'PUT')).toEqual([]);
      const edited = '  真实手动保存正文 🙂\n首尾空格与换行保留  \n';
      const editedTitle = first.title + ' 已修改';
      await action.fill(edited); await canvas(page).getByLabel('文档标题', { exact: true }).fill(editedTitle);
      await dirty(page, 1); await r.screenshot('manual-v1-dirty-real-input');
      const dispatch = await r.gate(first, 'PUT', '', 'original_manual_save_put_v1_to_v2');
      await canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click();
      await dispatch.held();
      await expect(state(page)).toHaveText('当前分镜：保存中… · 基于 v1');
      await expect(canvas(page).getByRole('button', { name: '保存中…', exact: true })).toBeDisabled();
      await expect(action).toBeDisabled();
      await page.getByRole('tab', { name: /^剧本/ }).click();
      await expect(page.getByRole('tab', { name: /^分镜/ })).toHaveAttribute('aria-selected', 'true');
      await tabs(page, '图片').click();
      await expect(tabs(page, '小说')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('.creative-navigation-confirm')).toHaveCount(0);
      dispatch.evidence.busy_navigation_and_inputs_refused_at = Date.now();
      await r.screenshot('manual-real-put-held-saving-and-navigation-fenced');
      expect(dispatch.evidence.original_request_body.expected_version).toBe(1);
      expect(dispatch.evidence.original_request_body.scenes[0].action).toBe(edited);
      dispatch.release(); const receipt = await dispatch.delivered(200);
      expect(receipt).toMatchObject({ id: first.id, version: 2, title: editedTitle });
      first.title = editedTitle;
      await saved(page, 2); await expect(action).toHaveValue(edited);
      const committed = await r.owner(first, 'real_save_put_owner_version_two');
      expect(committed.version).toBe(2); expect(committed.scenes[0].action).toBe(edited);
      expect(committed.title).toBe(editedTitle); expect(committed.history).toHaveLength(1);
      expect(r.calls.filter(call => call.path === first.path && call.method === 'PUT')).toEqual([
        { path: first.path, method: 'PUT', status: 200 },
      ]);
      await r.screenshot('manual-v2-save-receipt-and-original-owner-readback');
      await page.reload();
      await expect(tabs(page, '图片')).toHaveAttribute('aria-selected', 'true');
      await expect(page.locator('[aria-label="独立工作区内容"]')).toBeVisible();
      await r.open(first); await saved(page, 2); await expect(canvas(page).getByLabel('动作与叙事', { exact: true })).toHaveValue(edited);
      expect(await r.owner(first, 'reload_original_owner_version_two')).toEqual(committed);
      await r.screenshot('manual-v2-refresh-reopen-saved');
      await r.open(screenplay, false);
      const otherDirty = '其他阶段真实未保存剧本，不能被当前干净分镜状态清除';
      await canvas(page).getByLabel('动作与叙事', { exact: true }).fill(otherDirty);
      await r.open(cleanOther, false); await saved(page, 1);
      await expect(page.locator('[aria-label="其他创作草稿状态"]'))
        .toHaveText('· 其他阶段未保存：剧本（仅本页内存）');
      await r.screenshot('current-saved-v1-and-other-stage-real-dirty');
      await r.open(screenplay, false);
      await expect(canvas(page).getByLabel('动作与叙事', { exact: true })).toHaveValue(otherDirty);
      expect(await r.owner(screenplay, 'other_stage_dirty_remains_unpersisted')).toEqual(screenplay.owner);
    } finally { await r.finish(); }
  });

test('real offline transport uncertainty and real original CAS409 retain the local draft and explicit reconciliation',
  async ({ page, context, request }, info) => {
    const r = rig(page, request, info);
    try {
      const owned = await r.project('不确定与冲突'), doc = await r.document(owned, '故障保留');
      const cleanPeer = await r.document(owned, '核对期间的 B');
      await r.connect(owned); await r.open(doc); await saved(page, 1);
      const action = canvas(page).getByLabel('动作与叙事', { exact: true });
      const pending = '网络故障必须保留的本地草稿 🙂';
      await action.fill(pending); await dirty(page, 1);
      await context.setOffline(true);
      try {
        await canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click();
        await uncertain(page, 1);
        await expect.poll(() => r.failures.some(row => row.path === doc.path && row.method === 'PUT'
          && row.failure === 'net::ERR_INTERNET_DISCONNECTED')).toBe(true);
      } finally { await context.setOffline(false); }
      expect(await r.owner(doc, 'offline_before_dispatch_owner_unchanged')).toEqual(doc.owner);
      await expect(action).toHaveValue(pending);
      r.records.push({ phase: 'offline_transport_failure', backend_response_fabricated: false,
        failure_before_dispatch: true, post_commit_receipt_loss_claimed: false });
      await r.screenshot('offline-unknown-keeps-local-draft-and-current-status');
      const checking = page.waitForResponse(response => new URL(response.url()).pathname === doc.path && response.request().method() === 'GET');
      await page.getByRole('button', { name: '核对服务端版本', exact: true }).click();
      expect((await checking).status()).toBe(200);
      const review = page.getByRole('region', { name: '服务端版本核对', exact: true });
      await expect(review).toContainText('服务端 v1');
      await expect(action).toHaveValue(pending);
      await review.getByRole('checkbox', { name: '已核对并确认用服务端版本替换当前本地草稿', exact: true }).check();
      await review.getByRole('button', { name: '使用核对后的服务端版本', exact: true }).click();
      await saved(page, 1);
      const externalBody = { ...doc.body, scenes: doc.body.scenes.map((scene: Row) => ({ ...scene, action: '另一个原 owner 真实写入 v2' })), expected_version: 1 };
      const external = await exact(await request.put(doc.path, { headers: owned.headers, data: externalBody }), 200);
      expect(external.version).toBe(2);
      r.records.push({ phase: 'second_original_owner_put_200', expected_version: 1, owner: external });
      // The original derive action uses this clean cached v1. A real competing
      // owner has already committed v2, so its original CAS must refuse it.
      const deriving = page.waitForResponse(response => new URL(response.url()).pathname === `${doc.path}/derive`
        && response.request().method() === 'POST');
      await canvas(page).getByRole('button', { name: '建立制作计划', exact: true }).click();
      const refused = await deriving;
      expect(refused.status(), await refused.text()).toBe(409);
      const deriveProblem = await refused.json();
      expect((deriveProblem.detail ?? deriveProblem).code).toBe('EXPERIMENTAL_VERSION_CONFLICT');
      expect(refused.request().postDataJSON()).toMatchObject({ expected_version: 1, mode: 'PRODUCTION' });
      await uncertain(page, 1);
      await expect(canvas(page).getByText('已保存 · v1', { exact: true })).toBeVisible();
      r.records.push({ phase: 'real_original_derive_cas409_clean_blocked_origin', status: 409,
        request_body: refused.request().postDataJSON(), problem: deriveProblem });
      const verify = await r.gate(doc, 'GET', '', 'original_verify_get_late_other_document');
      await page.getByRole('button', { name: '核对服务端版本', exact: true }).click();
      await verify.held();
      await expect(state(page)).toHaveText('当前分镜：核对服务端版本中… · 基于 v1');
      await expect(canvas(page).getByRole('button', { name: '保存草稿', exact: true })).toBeDisabled();
      await expect(canvas(page).getByRole('button', { name: '保存中…', exact: true })).toHaveCount(0);
      await r.screenshot('real-verify-get-held-does-not-claim-save-write');
      // Original AssetBrowser may open B because A is blocked but clean.
      await r.open(cleanPeer, false); await saved(page, 1);
      await expect(canvas(page).getByLabel('动作与叙事', { exact: true })).toHaveValue(cleanPeer.owner.scenes[0].action);
      await expect(page.locator('.status-bar')).toContainText('其他文档：核对服务端版本中…');
      verify.evidence.other_clean_document_current_before_release_at = Date.now();
      verify.release(); const verified = await verify.delivered(200);
      expect(verified).toMatchObject({ id: doc.id, version: 2 });
      await verify.dispose();
      await saved(page, 1);
      await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(cleanPeer.title);
      await expect(page.getByRole('region', { name: '服务端版本核对', exact: true })).toHaveCount(0);
      await expect(page.getByRole('button', { name: '使用核对后的服务端版本', exact: true })).toHaveCount(0);
      expect(await r.owner(cleanPeer, 'late_verify_a_does_not_change_clean_b_owner')).toEqual(cleanPeer.owner);
      await r.screenshot('late-verify-a-v2-cannot-attach-candidate-to-clean-b-v1');
      // Return through the original cached card. Its base is still v1; only the
      // original server CAS may decide whether a new edit is current enough.
      await r.open(doc, false); await saved(page, 1);
      const conflictDraft = '本地旧v1上的独立编辑，409后仍保留';
      await action.fill(conflictDraft); await dirty(page, 1);
      const responsePromise = page.waitForResponse(response => new URL(response.url()).pathname === doc.path && response.request().method() === 'PUT');
      await canvas(page).getByRole('button', { name: '保存草稿', exact: true }).click();
      const response = await responsePromise; expect(response.status(), await response.text()).toBe(409);
      const problem = await response.json(); expect((problem.detail ?? problem).code).toBe('EXPERIMENTAL_VERSION_CONFLICT');
      expect(response.request().postDataJSON().expected_version).toBe(1);
      r.records.push({ phase: 'real_ui_original_cas_conflict', status: 409, problem, request_body: response.request().postDataJSON() });
      await uncertain(page, 1); await expect(action).toHaveValue(conflictDraft);
      expect(await r.owner(doc, 'conflict_original_owner_keeps_external_version_two')).toEqual(external);
      await r.screenshot('real-cas409-keeps-local-draft-and-server-v2');
      await page.getByRole('button', { name: '核对服务端版本', exact: true }).click();
      await expect(review).toContainText('服务端 v2');
      await expect(action).toHaveValue(conflictDraft);
      await review.getByRole('button', { name: '保留本地草稿', exact: true }).click();
      await uncertain(page, 1); await expect(action).toHaveValue(conflictDraft);
      await r.screenshot('real-cas409-author-keeps-local-draft-after-owner-check');
    } finally { await r.finish(); }
  });

test('late original history readbacks cannot contaminate another document or an explicitly changed project and branch',
  async ({ page, request }, info) => {
    const r = rig(page, request, info);
    try {
      const source = await r.project('旧范围'), destination = await r.project('新范围', true);
      const first = await r.document(source, '历史 A'), second = await r.document(source, '当前 B');
      const current = await r.document(destination, '新范围 C');
      await r.connect(source); await r.open(first); await saved(page, 1);
      const oldDocument = await r.gate(first, 'GET', '/history', 'late_original_history_other_document');
      await canvas(page).getByRole('button', { name: '历史', exact: true }).click(); await oldDocument.held();
      await r.open(second, false); await saved(page, 1);
      const local = 'B文档真实未保存编辑，不接受A的晚读回';
      await canvas(page).getByLabel('动作与叙事', { exact: true }).fill(local); await dirty(page, 1);
      oldDocument.evidence.current_other_document_dirty_before_release_at = Date.now();
      oldDocument.release(); const history = await oldDocument.delivered(200);
      expect(history.document_id).toBe(first.id);
      await expect(page.locator('.creative-history')).toHaveCount(0);
      await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(second.title);
      await expect(canvas(page).getByLabel('动作与叙事', { exact: true })).toHaveValue(local); await dirty(page, 1);
      await r.screenshot('late-history-a-cannot-relabel-or-clear-dirty-document-b');
      const oldScope = await r.gate(second, 'GET', '/history', 'late_original_history_other_project_branch');
      await canvas(page).getByRole('button', { name: '历史', exact: true }).click(); await oldScope.held();
      await tabs(page, '图片').click();
      await expect(page.locator('.creative-navigation-confirm')).toBeVisible();
      await expect(tabs(page, '小说')).toHaveAttribute('aria-selected', 'true');
      await page.getByRole('checkbox', { name: '确认放弃未保存草稿并离开', exact: true }).check();
      await page.getByRole('button', { name: '确认离开', exact: true }).click();
      await expect(page.locator('[aria-label="独立工作区内容"]')).toBeVisible();
      await page.getByRole('button', { name: '返回项目列表', exact: true }).click();
      await r.choose(destination); await r.open(current); await saved(page, 1);
      oldScope.evidence.new_project_and_branch_current_before_release_at = Date.now();
      oldScope.release(); const oldHistory = await oldScope.delivered(200);
      expect(oldHistory.document_id).toBe(second.id);
      await expect(page.locator('.creative-history')).toHaveCount(0);
      await expect(canvas(page).getByLabel('文档标题', { exact: true })).toHaveValue(current.title); await saved(page, 1);
      await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true })).toContainText(destination.path.branch_name);
      expect(await r.owner(second, 'old_scope_owner_unchanged_after_explicit_local_discard')).toEqual(second.owner);
      expect(await r.owner(current, 'new_scope_owner_remains_clean_after_old_history')).toEqual(current.owner);
      await r.screenshot('late-history-old-scope-cannot-contaminate-current-saved-v1');
    } finally { await r.finish(); }
  });
