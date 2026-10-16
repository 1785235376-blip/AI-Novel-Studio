import { createHash } from 'node:crypto';
import { expect, test, type APIRequestContext, type APIResponse, type Page, type Request, type Route, type TestInfo } from '@playwright/test';

type Path = { project_id: string; storyline_id: string; branch_id: string; project_name: string; branch_name: string };
type Seed = { id: string; title: string; path: Path; boardTitle: string; ownerPath: string; owner: Record<string, unknown> };
type Row = Record<string, unknown>;
const digest = (value: string) => createHash('sha256').update(value).digest('hex');
const admin = '/api/collaboration/admin/workspaces/workspace-a';
const moduleTab = (page: Page, name: string) => page.getByRole('tab', { name, exact: true });
const studio = (page: Page) => page.locator('[aria-label="独立工作区内容"]');
// These are read-only browser render barriers, not a latency schedule or a retry.
// A real response must finish before observing the original App's passive effect.
const rendered = (page: Page) => page.evaluate(() => new Promise<void>(resolve =>
  requestAnimationFrame(() => requestAnimationFrame(() => resolve()))));

async function exact(response: APIResponse, status: number) {
  expect(response.status(), await response.text()).toBe(status);
  return status === 204 ? null : response.json();
}

class DispatchGate {
  readonly rows: Row[] = [];
  private releases: (() => void)[] = [];
  private selected = new Map<Request, Row>();
  private open = false;
  private routePattern: string;
  constructor(readonly page: Page, readonly seed: Seed, readonly token: string, readonly origin: string) {
    this.routePattern = `**/api/projects/${seed.id}/studio`;
  }
  private failed = (request: Request) => {
    const row = this.selected.get(request);
    if (row) Object.assign(row, { request_failed: request.failure()?.errorText, failed_at: Date.now() });
  };
  private handler = async (route: Route) => {
    const request = route.request(), headers = request.headers();
    if (request.method() !== 'GET' || headers['x-branch-id'] !== this.seed.path.branch_id
        || headers['x-session-token'] !== this.token) return route.fallback();
    const row: Row = { origin: this.origin, url: request.url(), method: request.method(),
      project_id: this.seed.id, branch_id: headers['x-branch-id'], token_sha256: digest(headers['x-session-token']),
      held_at: Date.now(), request_not_dispatched_until_release: true, response_fabricated: false };
    this.rows.push(row); this.selected.set(request, row);
    if (!this.open) await new Promise<void>(resolve => this.releases.push(resolve));
    row.continue_at = Date.now();
    try {
      // No URL, body, method or headers override. This dispatches the original request.
      await route.continue(); row.continue_returned = true;
    } catch (error) { row.continue_error = String(error); }
    try {
      const response = await request.response();
      if (response) {
        const failure = await response.finished();
        if (failure) row.response_finished_error = String(failure);
        const body = await response.text();
        Object.assign(row, { status: response.status(), response_body_sha256: digest(body), response_raw_body: body, response_body: JSON.parse(body),
          response_at: Date.now(), source: 'original_backend_http' });
      }
    } catch (error) { row.response_error = String(error); }
  };
  async install() {
    this.page.on('requestfailed', this.failed);
    await this.page.route(this.routePattern, this.handler);
  }
  async heldCurrent() {
    await rendered(this.page);
    await expect.poll(() => this.rows.filter(row => !row.request_failed && !row.continue_at).length).toBeGreaterThan(0);
    const current = this.rows.filter(row => !row.request_failed && !row.continue_at).at(-1)!;
    return current;
  }
  markIntent(row: Row, modules: string[]) {
    expect(this.open).toBe(false); expect(row.continue_at).toBeUndefined();
    row.explicit_intent_at = Date.now(); row.explicit_modules = modules;
    row.intent_observed_while_request_held = true;
  }
  release() { this.open = true; this.releases.splice(0).forEach(release => release()); }
  async delivered(row: Row) {
    await expect.poll(() => row.status ?? row.request_failed ?? null).toBe(200);
    expect((row.response_body as { project: { id: string; entry_kind: string } }).project)
      .toMatchObject({ id: this.seed.id, entry_kind: 'NEUTRAL_STUDIO' });
    if (row.explicit_intent_at) expect(Number(row.continue_at)).toBeGreaterThanOrEqual(Number(row.explicit_intent_at));
    await rendered(this.page);
  }
  async canceled(row: Row) {
    await expect.poll(() => row.request_failed ?? null).toBe('net::ERR_ABORTED');
    expect(row.status).toBeUndefined(); row.outcome = 'canceled_by_original_scope_owner';
  }
  async dispose() {
    this.release();
    await this.page.unroute(this.routePattern, this.handler);
    this.page.off('requestfailed', this.failed);
  }
}

function bootstrap(page: Page, seed: Seed) {
  return page.waitForResponse(response => response.request().method() === 'GET'
    && new URL(response.url()).pathname === `/api/collaboration/workspaces/workspace-a/projects/${seed.id}`
      + `/storylines/${seed.path.storyline_id}/branches/${seed.path.branch_id}/bootstrap`);
}
async function resolved(page: Page, promise: ReturnType<typeof bootstrap>, rows: Row[]) {
  const response = await promise;
  expect(response.status(), await response.text()).toBe(200);
  await response.finished();
  const body = await response.json();
  expect(body.actor.actor_id).toBeTruthy();
  rows.push({ phase: 'original_bootstrap_actor_resolved', url: response.url(), status: response.status(),
    actor_id: body.actor.actor_id, scope: body.scope, response_body_sha256: digest(await response.text()) });
  await rendered(page);
}
async function choose(page: Page, seed: Seed) {
  const workspace = page.getByRole('button', { name: '我的创作空间', exact: true });
  const choice = page.getByRole('button').filter({ hasText: seed.title }).filter({ hasText: seed.path.branch_name });
  await expect.poll(async () => await workspace.isVisible() || await choice.isVisible()).toBe(true);
  if (await workspace.isVisible()) await workspace.click();
  await expect(choice).toBeVisible(); await choice.click();
  await expect(page.getByRole('navigation', { name: '当前创作范围', exact: true }))
    .toContainText(seed.title);
}
async function connect(page: Page, token: string, seed: Seed) {
  await page.goto('/');
  await page.getByText('连接已有创作空间', { exact: true }).click();
  await page.getByLabel('访问凭证', { exact: true }).fill(token);
  await page.getByRole('button', { name: '连接创作空间', exact: true }).click();
  await choose(page, seed);
}
async function openBoard(page: Page, seed: Seed) {
  await page.getByRole('button', { name: '打开 V2 创作工作台', exact: true }).click();
  await page.getByRole('tab', { name: /^分镜/ }).click();
  const documents = page.getByRole('region', { name: '创作文档', exact: true });
  await documents.getByRole('button').filter({ hasText: seed.boardTitle }).click();
  await expect(page.getByRole('button', { name: '按需打开镜头工作区', exact: true })).toBeVisible();
  await expect(documents).toContainText(seed.boardTitle);
}
async function selected(page: Page, name: string) {
  await expect(moduleTab(page, name)).toHaveAttribute('aria-selected', 'true');
}

function rig(page: Page, request: APIRequestContext, info: TestInfo) {
  const token = process.env.STUDIO_NAVIGATION_BROWSER_TOKEN;
  if (!token) throw new Error('Use the original ordinary LocalSessionBootstrap launcher.');
  const globalHeaders = { 'X-Session-Token': token };
  const headers = (seed: Seed) => ({ ...globalHeaders, 'X-Branch-ID': seed.path.branch_id });
  const projects: string[] = [], gates: DispatchGate[] = [], pages: Page[] = [];
  const records: Row[] = [], calls: Row[] = [], errors: string[] = [];
  const pendingOverview = new Set<Request>();
  const monitor = (target: Page) => {
    target.on('pageerror', error => errors.push(error.message));
    target.on('request', request => {
      if (request.method() === 'GET' && /\/api\/projects\/[^/]+\/studio$/.test(new URL(request.url()).pathname))
        pendingOverview.add(request);
    });
    target.on('requestfinished', request => pendingOverview.delete(request));
    target.on('requestfailed', request => pendingOverview.delete(request));
    target.on('response', response => {
      const path = new URL(response.url()).pathname;
      if (path.startsWith('/api/')) calls.push({ method: response.request().method(), path, status: response.status() });
    });
  };
  monitor(page);
  const branch = async (id: string, title: string, path: Path, suffix: string): Promise<Seed> => {
    const temporary = { id, path } as Seed;
    await exact(await request.post(`/api/projects/${id}/studio/activate`, { headers: headers(temporary) }), 200);
    const creative = `/api/novels/${id}/experimental/creative/documents`;
    const script = await exact(await request.post(creative, { headers: headers(temporary), data: { mode: 'SCREENPLAY',
      title: `真实导航剧本 ${suffix}`, source_independent: true,
      scenes: [{ id: 'navigation-intent-real-scene', sequence: 1, heading: 'INT. ROOM - DAY', action: 'A visitor arrives.' }] } }), 201);
    const boardTitle = `真实导航分镜 ${suffix}`;
    const board = await exact(await request.post(`${creative}/${script.id}/derive`, { headers: headers(temporary),
      data: { expected_version: script.version, mode: 'STORYBOARD', title: boardTitle, shot_policy: 'SCENE' } }), 201);
    const ownerPath = `${creative}/${board.id}`;
    const owner = await exact(await request.get(ownerPath, { headers: headers(temporary) }), 200);
    const seed = { id, title, path, boardTitle, ownerPath, owner };
    await gateFalse(seed); return seed;
  };
  const gateFalse = async (seed: Seed) => {
    const value = await exact(await request.get(`/api/projects/${seed.id}/studio/documents/${seed.owner.id}/prompt-adoption`,
      { headers: headers(seed) }), 200);
    expect(value.write_enabled).toBe(false);
    records.push({ phase: 'ordinary_production_capability', project_id: seed.id, branch_id: seed.path.branch_id,
      write_enabled: value.write_enabled });
  };
  const seed = async (suffix: string) => {
    const title = `导航意图验收 ${info.project.name} ${suffix}`;
    const created = await exact(await request.post(`${admin}/projects`, { headers: globalHeaders, data: { title, genre: '' } }), 201);
    projects.push(created.id);
    const navigation = await exact(await request.get(`${admin}/navigation`, { headers: globalHeaders }), 200);
    const path = navigation.eligible_paths.find((row: Path) => row.project_id === created.id);
    expect(path).toBeTruthy(); return branch(created.id, title, path, suffix);
  };
  const newBranch = async (original: Seed) => {
    const created = await exact(await request.post(`${admin}/projects/${original.id}/storylines/${original.path.storyline_id}/branches`,
      { headers: globalHeaders, data: { name: `导航另一分支 ${info.project.name}` } }), 201);
    const navigation = await exact(await request.get(`${admin}/navigation`, { headers: globalHeaders }), 200);
    const path = navigation.eligible_paths.find((row: Path) => row.project_id === original.id && row.branch_id === created.id);
    expect(path).toBeTruthy(); return branch(original.id, original.title, path, '另一分支');
  };
  const gate = async (target: Page, owned: Seed, origin: string) => {
    const value = new DispatchGate(target, owned, token, origin); gates.push(value); await value.install(); return value;
  };
  const unchanged = async (owned: Seed, phase: string) => {
    const owner = await exact(await request.get(owned.ownerPath, { headers: headers(owned) }), 200);
    expect(owner).toEqual(owned.owner);
    const overview = await exact(await request.get(`/api/projects/${owned.id}/studio`, { headers: headers(owned) }), 200);
    expect(overview.project).toMatchObject({ id: owned.id, title: owned.title, entry_kind: 'NEUTRAL_STUDIO' });
    records.push({ phase, source: 'standalone_owner_readback', project_id: owned.id, branch_id: owned.path.branch_id,
      owner, overview, old_callback_delivery: false });
    await gateFalse(owned);
  };
  const screenshot = async (target: Page, name: string) => {
    const actualModules: Record<string, string | null> = {};
    for (const name of ['小说', '图片', '视频']) actualModules[name] = await moduleTab(target, name).getAttribute('aria-selected');
    const document = target.getByRole('region', { name: '创作文档', exact: true });
    records.push({ phase: name, source: 'original_browser_dom_read_only', actual_module_tabs: actualModules,
      creative_documents_visible: await document.isVisible(),
      creative_documents_text: await document.isVisible() ? await document.innerText() : null });
    const file = info.outputPath(name + '.png'); await target.screenshot({ path: file, fullPage: true });
    await info.attach(name, { path: file, contentType: 'image/png' });
  };
  const finish = async () => {
    const cleanupErrors: string[] = [];
    for (const value of gates) try { await value.dispose(); } catch (error) { cleanupErrors.push(String(error)); }
    for (const value of pages) try { await value.close(); } catch (error) { cleanupErrors.push(String(error)); }
    for (const id of projects.reverse()) {
      try {
        const response = await request.delete(`${admin}/projects/${id}`, { headers: globalHeaders });
        records.push({ phase: 'owned_project_cleanup', project_id: id, status: response.status() });
        expect(response.status(), await response.text()).toBe(204);
      } catch (error) { cleanupErrors.push(String(error)); }
    }
    await info.attach('navigation-intent-evidence', { body: Buffer.from(JSON.stringify({
      token_sha256: digest(token), latency_schedule: 'client GET dispatch gate then original route.continue',
      request_not_dispatched_until_release: true, response_mocks: false, identity_injection: false,
      production_gate_override: false, model_execution: 'NOT_REQUESTED', model_counter: 'NOT_INSTRUMENTED',
      records, gates: gates.map(value => ({ origin: value.origin, requests: value.rows })), calls, errors, cleanupErrors,
    }, null, 2)), contentType: 'application/json' });
    expect(errors).toEqual([]);
    expect(cleanupErrors).toEqual([]);
    expect(calls.filter(row => row.method === 'POST' && String(row.path).endsWith('/prompt-adoption'))).toEqual([]);
  };
  const drained = async () => {
    await expect.poll(() => pendingOverview.size).toBe(0);
    await rendered(page);
    await expect.poll(() => pendingOverview.size).toBe(0);
  };
  return { token, records, seed, newBranch, gate, unchanged, screenshot, finish, monitor, pages, drained };
}

test('cold same-value NOVEL and reloaded rapid intent survive the real late parent overview; no intent defaults IMAGE',
  async ({ page, context, request }, info) => {
    const r = rig(page, request, info);
    try {
      const owned = await r.seed('冷启动与刷新');
      const cold = await r.gate(page, owned, 'App studioProject parent after original bootstrap actor resolution');
      const initialBootstrap = bootstrap(page, owned);
      await connect(page, r.token, owned);
      await resolved(page, initialBootstrap, r.records);
      const coldRequest = await cold.heldCurrent();
      await selected(page, '小说');
      await moduleTab(page, '小说').click(); await selected(page, '小说');
      cold.markIntent(coldRequest, ['NOVEL_same_value']);
      await openBoard(page, owned);
      await r.screenshot(page, 'cold-explicit-novel-overview-held');
      cold.release(); await cold.delivered(coldRequest);
      await selected(page, '小说'); await expect(page.getByRole('region', { name: '创作文档', exact: true })).toContainText(owned.boardTitle);
      await r.unchanged(owned, 'cold_explicit_novel_late_parent_applied');
      await r.screenshot(page, 'cold-late-overview-preserved-real-workbench');
      await cold.dispose();

      const reload = await r.gate(page, owned, 'reloaded App studioProject parent after original bootstrap actor resolution');
      const reloadedBootstrap = bootstrap(page, owned);
      await page.reload(); await resolved(page, reloadedBootstrap, r.records);
      const reloadRequest = await reload.heldCurrent();
      for (const name of ['图片', '视频', '小说']) { await moduleTab(page, name).click(); await selected(page, name); }
      reload.markIntent(reloadRequest, ['IMAGE', 'VIDEO', 'NOVEL']);
      await openBoard(page, owned);
      await r.screenshot(page, 'reload-rapid-last-novel-overview-held');
      reload.release(); await reload.delivered(reloadRequest);
      await selected(page, '小说'); await expect(page.getByRole('region', { name: '创作文档', exact: true })).toContainText(owned.boardTitle);
      await r.unchanged(owned, 'reload_rapid_last_intent_preserved');
      await r.screenshot(page, 'reload-late-overview-preserved-real-workbench');
      await reload.dispose();

      // A new page uses only the scope persisted by the preceding real connection UI.
      // It performs no module click and is the independent default-IMAGE control.
      const control = await context.newPage(); r.pages.push(control); r.monitor(control);
      const automatic = await r.gate(control, owned, 'new page App parent no explicit module intent');
      const controlBootstrap = bootstrap(control, owned);
      await control.goto('/'); await resolved(control, controlBootstrap, r.records);
      const controlRequest = await automatic.heldCurrent();
      expect(controlRequest.explicit_intent_at).toBeUndefined();
      automatic.release(); await automatic.delivered(controlRequest);
      await selected(control, '图片'); await expect(studio(control)).toBeVisible();
      r.records.push({ phase: 'no_explicit_intent_default_control', selected_module: 'IMAGE', module_clicks: 0 });
      await r.unchanged(owned, 'no_intent_default_image_owner_unchanged');
      await r.screenshot(control, 'no-intent-default-image-positive-control');
    } finally { await r.finish(); }
  });

test('original scope cancellation isolates old project and branch child overview from the new explicit workbench',
  async ({ page, request }, info) => {
    const r = rig(page, request, info);
    const settle = async () => { await expect(studio(page)).toBeVisible(); await r.drained(); };
    try {
      const first = await r.seed('项目 A'), otherBranch = await r.newBranch(first), second = await r.seed('项目 B');
      const initialBootstrap = bootstrap(page, first);
      await connect(page, r.token, first); await resolved(page, initialBootstrap, r.records);
      await selected(page, '图片'); await settle();
      const transition = async (old: Seed, next: Seed, label: string) => {
        await moduleTab(page, '小说').click(); await selected(page, '小说');
        const stale = await r.gate(page, old, `${label}: IndependentStudioSession.refresh after explicit IMAGE remount`);
        await moduleTab(page, '图片').click(); await selected(page, '图片');
        const staleRequest = await stale.heldCurrent();
        await expect(page.getByRole('button', { name: '返回项目列表', exact: true })).toBeVisible();
        await r.screenshot(page, `${label}-old-child-dispatch-held`);
        const fresh = await r.gate(page, next, `${label}: new scope App studioProject parent`);
        await page.getByRole('button', { name: '返回项目列表', exact: true }).click();
        const nextBootstrap = bootstrap(page, next);
        await choose(page, next); await resolved(page, nextBootstrap, r.records);
        const freshRequest = await fresh.heldCurrent();
        await moduleTab(page, '小说').click(); await selected(page, '小说');
        fresh.markIntent(freshRequest, ['NOVEL']); await openBoard(page, next);
        staleRequest.scope_changed_before_release_at = Date.now();
        stale.release(); await stale.canceled(staleRequest);
        fresh.release(); await fresh.delivered(freshRequest);
        await selected(page, '小说');
        const scope = page.getByRole('navigation', { name: '当前创作范围', exact: true });
        await expect(scope).toContainText(next.title); await expect(scope).toContainText(next.path.branch_name);
        await expect(page.getByRole('region', { name: '创作文档', exact: true })).toContainText(next.boardTitle);
        await r.unchanged(old, `${label}_old_owner_readback_not_old_callback_delivery`);
        await r.unchanged(next, `${label}_new_owner_readback`);
        await r.screenshot(page, `${label}-new-scope-last-novel-preserved`);
        await stale.dispose(); await fresh.dispose();
      };
      await transition(first, second, 'cross-project');
      // Return through the same original entry UI, then exercise a distinct branch.
      await moduleTab(page, '图片').click(); await selected(page, '图片'); await settle();
      await page.getByRole('button', { name: '返回项目列表', exact: true }).click();
      const returnBootstrap = bootstrap(page, first);
      await choose(page, first); await resolved(page, returnBootstrap, r.records);
      await selected(page, '图片'); await settle();
      await transition(first, otherBranch, 'cross-branch');
    } finally { await r.finish(); }
  });
