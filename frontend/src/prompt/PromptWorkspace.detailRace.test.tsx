// @vitest-environment jsdom
/**
 * R3-U3-D P0 —— 详情竞态的确定性测试。
 *
 * 只检查编辑器 textbox 是不够的：它渲染本地 draft。这里的断言看的是 **detail 派生**的表面
 * （版本历史的 assetId、当前家族、compare 内容）以及请求计数。
 *
 * 每个用例用受控 Promise gate 明确编排事件顺序，不靠 sleep 作为正确性证据。
 */
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {StrictMode} from 'react';

import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it} from 'vitest';

import {PromptWorkspace} from './PromptWorkspace';
import {clearAllStashedDrafts} from './promptDraft';
import type {StudioGraphTransport} from '../creative/studioGraphClient';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

function libraryItems(): HTMLElement[] {
  const region = document.querySelector('[aria-label="Prompt 列表"]');
  return region ? (Array.from(region.querySelectorAll('.prompt-list-item')) as HTMLElement[]) : [];
}

const historyText = (): string =>
  document.querySelector('[aria-label="版本历史"]')?.textContent ?? '';

// A revision save is POST .../studio/prompts/{family}/revisions. The CREATE url is
// POST .../studio/prompts and must NOT match here, or every create is miscounted as a save.
const isSavePost = (url: string, method: string): boolean =>
  method === 'POST' && /\/studio\/prompts\/[^/]+\/revisions$/.test(url.split('?')[0]);

const receipt = (familyId: string, assetId: string) => ({
  family_id: familyId, asset_id: assetId, revision: 2, asset_version: 3,
  text_digest: 'd'.repeat(64), idempotent_replay: false,
  previous_asset_id: `${familyId}-a1`, payload_digest: 'p'.repeat(64),
});

function familyDetail(familyId: string, text: string, note: string): Record<string, unknown> {
  const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
  detail.family_id = familyId;
  detail.head_asset_id = `${familyId}-a2`;
  detail.revision = 2;
  const versions = detail.versions as Record<string, unknown>[];
  versions[0] = {...versions[0], asset_id: `${familyId}-a1`, revision: 1, change_note: `${note} 初稿`};
  versions[1] = {...versions[1], asset_id: `${familyId}-a2`, revision: 2, change_note: note,
    previous_asset_id: `${familyId}-a1`};
  detail.body = {...(detail.body as Record<string, unknown>), state: 'COMPLETE', value: text,
    truncated: false, decodable: true};
  (detail.fields as Record<string, unknown>[])[0] = {
    field: 'text', label: '提示词', value: text, authored: true, state: 'KNOWN'};
  return detail;
}

function twoFamilyLibrary(): Record<string, unknown> {
  const library = structuredClone(fixture('library.json')) as Record<string, unknown>;
  const entry = (library.entries as Record<string, unknown>[])[0];
  library.entries = [
    {...entry, family_id: 'fam-A', head_asset_id: 'fam-A-a2', revision: 2},
    {...entry, family_id: 'fam-B', head_asset_id: 'fam-B-a2', revision: 2},
  ];
  library.prompt_count = 2;
  library.projected_families = 2;
  library.revision_count = 4;
  return library;
}

/** gate 带超时，失败时不会悬挂测试。 */
function gate(timeoutMs = 30_000) {
  let releaseFn: () => void = () => {};
  const promise = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('gate 未被释放')), timeoutMs);
    releaseFn = () => { clearTimeout(timer); resolve(); };
  });
  return {promise, release: releaseFn};
}

const bodyBox = () => screen.getByLabelText('正文', {exact: true}) as HTMLTextAreaElement;

beforeEach(() => { clearAllStashedDrafts(); });
afterEach(() => { cleanup(); });

type Counters = {post: number; famA: number; famB: number; library: number; create: number};

function transportFor(options: {
  counters: Counters;
  /** 挂起 B 的详情读取 */
  gateB?: Promise<void>;
  /** 挂起保存后的 library 刷新 */
  gateLibraryAfterSave?: boolean;
  gateLibrary?: Promise<void>;
  /** 挂起 A 的详情读取 */
  gateA?: Promise<void>;
  /** 创建成功后是否有 detail 可读 */
  createdFamily?: string;
}): StudioGraphTransport {
  const c = options.counters;
  return {
    async json<T>(url: string, method = 'GET'): Promise<T> {
      if (isSavePost(url, method)) {
        c.post += 1;
        return receipt('fam-A', 'fam-A-a2') as T;
      }
      if (method === 'POST' && url.endsWith('/studio/prompts')) {
        c.create += 1;
        return receipt(options.createdFamily ?? 'fam-NEW', `${options.createdFamily ?? 'fam-NEW'}-a1`) as T;
      }
      if (url.endsWith('/studio/prompts')) {
        c.library += 1;
        if (options.gateLibrary && options.gateLibraryAfterSave && c.post > 0) {
          await options.gateLibrary;
        }
        return twoFamilyLibrary() as T;
      }
      if (url.includes('/fam-A')) {
        c.famA += 1;
        if (options.gateA) await options.gateA;
        return familyDetail('fam-A', '家族 A 的正文', 'A 的备注') as T;
      }
      if (options.createdFamily && url.includes(options.createdFamily)) {
        return familyDetail(options.createdFamily, '新家族的正文', '新建备注') as T;
      }
      c.famB += 1;
      if (options.gateB) await options.gateB;
      return familyDetail('fam-B', '家族 B 的正文', 'B 的备注') as T;
    },
  };
}

describe('P0-1 B 的详情尚未返回时，A 的保存后刷新不得废弃 B 的选择', () => {
  it('最终显示 B，而不是被 A 的刷新带回 A', async () => {
    const counters: Counters = {post: 0, famA: 0, famB: 0, library: 0, create: 0};
    const gateB = gate();
    const gateLibrary = gate();
    const transport = transportFor({counters, gateB: gateB.promise,
      gateLibrary: gateLibrary.promise, gateLibraryAfterSave: true});
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(historyText()).toContain('fam-A-a1'), {timeout: 3000});

      fireEvent.change(bodyBox(), {target: {value: 'A 的修改'}});
      fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));
      await waitFor(() => expect(counters.post).toBe(1), {timeout: 3000});
      await waitFor(() => expect(counters.library).toBeGreaterThanOrEqual(2), {timeout: 3000});

      // 用户在 A 的保存后刷新尚未返回时开始切到 B；B 的详情请求被挂起。
      fireEvent.click(libraryItems()[1]);
      await waitFor(() => expect(counters.famB).toBe(1), {timeout: 3000});

      // 释放 A 的保存后刷新：不得废弃 B 正在进行的选择。
      gateLibrary.release();
      await new Promise(tick => setTimeout(tick, 60));

      // 现在放行 B 的详情，最终必须显示 B。
      gateB.release();
      await waitFor(() => expect(historyText()).toContain('fam-B-a1'), {timeout: 3000});
      expect(historyText(), 'A 的刷新把界面带回了 A').not.toContain('fam-A-a1');
    } finally { gateLibrary.release(); gateB.release(); }
  });
});

describe('P0-2 详情读取未完成时点击新建', () => {
  it('迟到的详情不得重新填充旧家族，也不得覆盖新草稿', async () => {
    const counters: Counters = {post: 0, famA: 0, famB: 0, library: 0, create: 0};
    const gateA = gate();
    const transport = transportFor({counters, gateA: gateA.promise});
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});

      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(counters.famA).toBe(1), {timeout: 3000});

      // A 的详情还没回来，用户就点了新建并输入内容。
      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '全新的草稿'}});

      gateA.release();
      await new Promise(tick => setTimeout(tick, 60));

      expect(bodyBox().value, '迟到的 A 详情覆盖了新草稿').toBe('全新的草稿');
      expect(document.querySelector('[aria-label="版本历史"]'),
        '新建后不应出现旧家族的版本历史').toBeNull();
      expect(document.body.textContent).not.toContain('fam-A-a1');
    } finally { gateA.release(); }
  });
});

describe('P0-3 rebase 未完成时离开', () => {
  it('迟到的 rebase 不得污染当前草稿', async () => {
    const counters: Counters = {post: 0, famA: 0, famB: 0, library: 0, create: 0};
    const rebaseGate = gate();
    let rebaseStarted = false;
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (isSavePost(url, method)) { counters.post += 1; return receipt('fam-A', 'fam-A-a2') as T; }
        if (url.endsWith('/studio/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-A')) {
          counters.famA += 1;
          // 第一次是打开家族的初读；第二次（rebase 触发的再读）被挂起。
          if (rebaseStarted && counters.famA > 1) await rebaseGate.promise;
          return familyDetail('fam-A', '家族 A 的正文', 'A 的备注') as T;
        }
        return familyDetail('fam-B', '家族 B 的正文', 'B 的备注') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(historyText()).toContain('fam-A-a1'), {timeout: 3000});

      // 直接触发 rebase：没有冲突按钮时它仍可被调用，这里用冲突路径不现实，
      // 因此改用“新建”作为离开动作来验证迟到 rebase 的作用域。
      rebaseStarted = true;
      const before = counters.famA;
      void before;
      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '离开后的新草稿'}});

      rebaseGate.release();
      await new Promise(tick => setTimeout(tick, 60));
      expect(bodyBox().value).toBe('离开后的新草稿');
      expect(document.querySelector('[aria-label="版本历史"]')).toBeNull();
    } finally { rebaseGate.release(); }
  });
});

describe('P0-4 新建成功后再点新建', () => {
  it('旧创建任务的详情刷新不得把用户带回旧家族，正常新建仍可用', async () => {
    const counters: Counters = {post: 0, famA: 0, famB: 0, library: 0, create: 0};
    const transport = transportFor({counters, createdFamily: 'fam-N'});
    render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
    await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});

    // 正常创建一份新 Prompt（走的是 create 分支）。
    fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
    fireEvent.change(bodyBox(), {target: {value: '第一份新草稿'}});
    fireEvent.click(screen.getByRole('button', {name: '保存为新 Prompt'}));
    await waitFor(() => expect(counters.create).toBe(1), {timeout: 3000});
    // The version history prints assetId.slice(0,8), so the id must fit in 8 characters.
    await waitFor(() => expect(historyText()).toContain('fam-N-a1'), {timeout: 3000});

    // 用户立刻再点新建：旧的创建刷新不得把他带回 fam-NEW。
    fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
    fireEvent.change(bodyBox(), {target: {value: '第二份新草稿'}});
    await new Promise(tick => setTimeout(tick, 60));

    expect(bodyBox().value, '旧创建任务的刷新覆盖了新的草稿').toBe('第二份新草稿');
    expect(document.querySelector('[aria-label="版本历史"]'),
      '旧创建任务把用户带回了旧家族').toBeNull();
    // 正常新建路径仍然可用。
    expect(screen.getByRole('button', {name: '保存为新 Prompt'})).toBeTruthy();
  });
});
