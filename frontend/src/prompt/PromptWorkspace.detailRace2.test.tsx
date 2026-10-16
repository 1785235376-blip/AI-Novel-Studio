// @vitest-environment jsdom
/**
 * R3-U3-D 复审补遗 —— 任务 A/B/C/D。
 *
 * A：真实 409 → 用户触发 rebase（服务端详情 GET 被挂起）→ 用户离开 → 释放旧请求。
 * B：首次创建成功后，其保存后刷新被挂起 → 用户再点新建 → 释放旧请求 → 新草稿不被污染且可保存。
 * C：selectFamily 的读取被 startNew 废弃后，loading 不得永久为 true（新草稿必须仍可编辑与保存）。
 * D：A 的 POST 尚未返回、用户已开始切到 B，随后 A 才返回 201。
 *
 * 断言看 detail 派生表面（版本历史 assetId、家族身份、草稿内容、请求计数）与可操作性，
 * 不只看编辑器 textbox；事件顺序由受控 gate 编排。
 */
import {readFileSync} from 'node:fs';
import {resolve} from 'node:path';
import {StrictMode} from 'react';

import {cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, beforeEach, describe, expect, it} from 'vitest';

import {PromptWorkspace} from './PromptWorkspace';
import {clearAllStashedDrafts} from './promptDraft';
import {ApiError} from '../api';
import type {StudioGraphTransport} from '../creative/studioGraphClient';

const fixture = (name: string): unknown => JSON.parse(readFileSync(
  resolve(process.cwd(), 'src', 'prompt', '__fixtures__', name), 'utf-8')) as unknown;

function libraryItems(): HTMLElement[] {
  const region = document.querySelector('[aria-label="Prompt 列表"]');
  return region ? (Array.from(region.querySelectorAll('.prompt-list-item')) as HTMLElement[]) : [];
}

const historyText = (): string =>
  document.querySelector('[aria-label="版本历史"]')?.textContent ?? '';
const bodyBox = () => screen.getByLabelText('正文', {exact: true}) as HTMLTextAreaElement;
const saveEnabled = (name: string): boolean => {
  const button = screen.queryByRole('button', {name});
  return !!button && !(button as HTMLButtonElement).disabled;
};

const isRevisionPost = (url: string, method: string): boolean =>
  method === 'POST' && /\/studio\/prompts\/[^/]+\/revisions$/.test(url.split('?')[0]);
const isCreatePost = (url: string, method: string): boolean =>
  method === 'POST' && /\/studio\/prompts$/.test(url.split('?')[0]);

/** 真实契约形状：首次创建返回 revision 1，previous_asset_id 为 null。 */
const createReceipt = (familyId: string, assetId: string) => ({
  family_id: familyId, asset_id: assetId, revision: 1, asset_version: 1,
  text_digest: 'c'.repeat(64), idempotent_replay: false,
  previous_asset_id: null, payload_digest: 'q'.repeat(64),
});

const revisionReceipt = (familyId: string, assetId: string) => ({
  family_id: familyId, asset_id: assetId, revision: 2, asset_version: 3,
  text_digest: 'd'.repeat(64), idempotent_replay: false,
  previous_asset_id: `${familyId}-a1`, payload_digest: 'p'.repeat(64),
});

function familyDetail(familyId: string, text: string): Record<string, unknown> {
  const detail = structuredClone(fixture('detail.json')) as Record<string, unknown>;
  detail.family_id = familyId;
  detail.head_asset_id = `${familyId}-a2`;
  detail.revision = 2;
  const versions = detail.versions as Record<string, unknown>[];
  versions[0] = {...versions[0], asset_id: `${familyId}-a1`, revision: 1};
  versions[1] = {...versions[1], asset_id: `${familyId}-a2`, revision: 2,
    previous_asset_id: `${familyId}-a1`};
  detail.body = {...(detail.body as Record<string, unknown>), state: 'COMPLETE', value: text,
    truncated: false, decodable: true};
  (detail.fields as Record<string, unknown>[])[0] = {
    field: 'text', label: '提示词', value: text, authored: true, state: 'KNOWN'};
  return detail;
}

/** 首次创建后的家族详情：只有一个修订。 */
function newFamilyDetail(familyId: string, text: string): Record<string, unknown> {
  const detail = familyDetail(familyId, text);
  const versions = detail.versions as Record<string, unknown>[];
  detail.versions = [versions[0]];
  detail.head_asset_id = `${familyId}-a1`;
  detail.revision = 1;
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

/** 带超时的 gate。 */
function gate(timeoutMs = 30_000) {
  let releaseFn: () => void = () => {};
  const promise = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('gate 未被释放')), timeoutMs);
    releaseFn = () => { clearTimeout(timer); resolve(); };
  });
  return {promise, release: releaseFn};
}

beforeEach(() => { clearAllStashedDrafts(); });
afterEach(() => { cleanup(); });

describe('任务 C：selectFamily 被 startNew 废弃后 loading 不得永久为 true', () => {
  it('新草稿仍可编辑并成功创建', async () => {
    const counters = {create: 0, detail: 0};
    const gateA = gate();
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (isCreatePost(url, method)) {
          counters.create += 1;
          return createReceipt('fam-N', 'fam-N-a1') as T;
        }
        if (url.endsWith('/studio/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-A')) { counters.detail += 1; await gateA.promise; return familyDetail('fam-A', '家族 A 的正文') as T; }
        if (url.includes('/fam-N')) return newFamilyDetail('fam-N', '新家族正文') as T;
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});

      // 打开 A：详情读取被挂起（loading 处于 true）。
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(counters.detail).toBe(1), {timeout: 3000});

      // 用户不等它返回就点新建。
      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '仍然要能写的新草稿'}});

      // 释放被废弃的 A 读取。
      gateA.release();
      await new Promise(tick => setTimeout(tick, 60));

      // 界面不能卡在读取状态：新草稿必须可编辑、可保存。
      expect(bodyBox().value).toBe('仍然要能写的新草稿');
      expect(saveEnabled('保存为新 Prompt'), '界面卡在 loading，保存被禁用').toBe(true);
      fireEvent.click(screen.getByRole('button', {name: '保存为新 Prompt'}));
      await waitFor(() => expect(counters.create, '新草稿无法完成创建').toBe(1), {timeout: 3000});
    } finally { gateA.release(); }
  });
});

describe('任务 D：A 的 POST 未返回时用户已切到 B', () => {
  it('A 的保存仍被正确处理，但其刷新不得抢占 B', async () => {
    const counters = {post: 0, famA: 0, famB: 0, library: 0};
    const postGate = gate();
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (isRevisionPost(url, method)) {
          counters.post += 1;
          await postGate.promise;            // A 的回执迟到
          return revisionReceipt('fam-A', 'fam-A-a2') as T;
        }
        if (url.endsWith('/studio/prompts')) { counters.library += 1; return twoFamilyLibrary() as T; }
        if (url.includes('/fam-A')) { counters.famA += 1; return familyDetail('fam-A', '家族 A 的正文') as T; }
        counters.famB += 1;
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(historyText()).toContain('fam-A-a1'), {timeout: 3000});

      fireEvent.change(bodyBox(), {target: {value: 'A 的修改'}});
      fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));
      await waitFor(() => expect(counters.post).toBe(1), {timeout: 3000});

      // 用户在 A 的回执到达前切到 B，并等 B 的详情显示。
      fireEvent.click(libraryItems()[1]);
      await waitFor(() => expect(historyText()).toContain('fam-B-a1'), {timeout: 3000});

      postGate.release();
      await new Promise(tick => setTimeout(tick, 80));

      // A 的服务端保存仍被正确处理（恰好一次 POST），但界面必须是 B。
      expect(counters.post).toBe(1);
      expect(historyText(), 'A 的迟到回执把界面带回了 A').toContain('fam-B-a1');
      expect(historyText()).not.toContain('fam-A-a1');
      expect(bodyBox().value).toBe('家族 B 的正文');
    } finally { postGate.release(); }
  });
});

describe('任务 A：真实 409 后的 rebase 被挂起时用户离开', () => {
  it('迟到的 rebase 不得覆盖新草稿或错误状态', async () => {
    const counters = {post: 0, famA: 0};
    const rebaseGate = gate();
    let conflictSeen = false;
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (isRevisionPost(url, method)) {
          counters.post += 1;
          conflictSeen = true;
          // 真实契约的白名单 409 冲突体。
          throw new ApiError({status: 409, code: 'EXPERIMENTAL_VERSION_CONFLICT',
            message: 'conflict', details: {code: 'PROMPT_REVISION_STALE', family_id: 'fam-A',
              expected_revision: 2, current_revision: 3, retryable: true}});
        }
        if (url.endsWith('/studio/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-A')) {
          counters.famA += 1;
          // 初读立即返回；rebase 触发的再读被挂起。
          if (conflictSeen && counters.famA > 1) await rebaseGate.promise;
          return familyDetail('fam-A', conflictSeen && counters.famA > 1
            ? '服务器上的最新 A 正文' : '家族 A 的正文') as T;
        }
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(historyText()).toContain('fam-A-a1'), {timeout: 3000});

      fireEvent.change(bodyBox(), {target: {value: '我的宝贵草稿'}});
      fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));
      // 409 后必须出现明确的 rebase 操作，草稿保留。
      const rebaseButton = await screen.findByRole('button', {name: '重新基准到服务器最新修订'},
        {timeout: 3000});
      expect(bodyBox().value, '409 后草稿丢失').toBe('我的宝贵草稿');

      // 用户触发 rebase：服务端详情 GET 被挂起。
      fireEvent.click(rebaseButton);
      await waitFor(() => expect(counters.famA).toBe(2), {timeout: 3000});

      // rebase 未完成时用户离开去新建。
      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '离开后的新草稿'}});

      rebaseGate.release();
      await new Promise(tick => setTimeout(tick, 80));

      // 迟到的 rebase 不得污染新草稿、detail 或错误状态。
      expect(bodyBox().value, '迟到的 rebase 覆盖了新草稿').toBe('离开后的新草稿');
      expect(document.querySelector('[aria-label="版本历史"]'),
        '迟到的 rebase 把旧家族详情带了回来').toBeNull();
      expect(document.body.textContent).not.toContain('服务器上的最新 A 正文');
      expect(saveEnabled('保存为新 Prompt'), '离开后界面不可用').toBe(true);
    } finally { rebaseGate.release(); }
  });
});

describe('任务 B：首次创建成功后再点新建（真实创建回执形状）', () => {
  it('旧创建任务的保存后刷新不得污染第二份草稿，且第二份仍可保存', async () => {
    const counters = {create: 0, famN: 0};
    const gateN = gate();
    let created = false;
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (isCreatePost(url, method)) {
          counters.create += 1;
          created = true;
          // 首次创建的契约形状：revision 1、previous_asset_id 为 null。
          return createReceipt('fam-N', 'fam-N-a1') as T;
        }
        if (url.endsWith('/studio/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-N')) {
          counters.famN += 1;
          // 创建后的详情读取被挂起，模拟旧任务尚未结束。
          if (created) await gateN.promise;
          return newFamilyDetail('fam-N', '新家族正文') as T;
        }
        if (url.includes('/fam-A')) return familyDetail('fam-A', '家族 A 的正文') as T;
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});

      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '第一份新草稿'}});
      fireEvent.click(screen.getByRole('button', {name: '保存为新 Prompt'}));
      await waitFor(() => expect(counters.create).toBe(1), {timeout: 3000});
      await waitFor(() => expect(counters.famN).toBe(1), {timeout: 3000});

      // 旧创建任务的详情刷新仍被挂起时，用户再次点新建并输入第二份草稿。
      fireEvent.click(screen.getByRole('button', {name: '新建 Prompt'}));
      fireEvent.change(bodyBox(), {target: {value: '第二份新草稿'}});

      gateN.release();
      await new Promise(tick => setTimeout(tick, 80));

      expect(bodyBox().value, '旧创建任务的刷新污染了第二份草稿').toBe('第二份新草稿');
      expect(document.querySelector('[aria-label="版本历史"]'),
        '旧创建任务把用户带回了旧家族').toBeNull();
      // 第二份草稿必须仍能正常保存。
      expect(saveEnabled('保存为新 Prompt')).toBe(true);
      fireEvent.click(screen.getByRole('button', {name: '保存为新 Prompt'}));
      await waitFor(() => expect(counters.create, '第二份草稿无法保存').toBe(2), {timeout: 3000});
    } finally { gateN.release(); }
  });
});
