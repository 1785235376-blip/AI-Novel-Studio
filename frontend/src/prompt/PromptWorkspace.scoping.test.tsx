// @vitest-environment jsdom
/**
 * R3-U3-D 专项 —— 跨家族竞态（重写版）。
 *
 * 上一版有**假阳性**：模拟传输层先用 `url.includes('/fam-A')` 匹配，而真实保存请求的 URL 是
 * `.../studio/prompts/fam-A/revisions`，同样含 `/fam-A`，于是 POST 被当成 GET，从未进入
 * receipt 分支。那个 PASS 不能证明任何事。这一版：
 *   - 先按 **method + 精确路径** 识别 POST，单独计数 postCount；
 *   - POST 返回**符合契约的 receipt**，并断言回执被真正解码（编辑器进入已保存状态）；
 *   - 家族 A 的 GET 分别计数：初读与“保存后再读”，只延迟第二个，并**断言它确实发生过**；
 *   - 所有 gate 都带超时与 finally 释放，失败时不悬挂。
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

/** 真实 saveRevision 的 URL 形状：POST .../studio/prompts/{family}/revisions */
const isSavePost = (url: string, method: string): boolean =>
  method === 'POST' && /\/studio\/prompts\/[^/]+\/revisions$/.test(url.split('?')[0]);

const receipt = (familyId: string, assetId: string) => ({
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

/** 带超时的 gate：失败时不会悬挂整个测试。 */
function gate(timeoutMs = 4000) {
  let releaseFn: () => void = () => {};
  const promise = new Promise<void>((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('gate 未被释放（测试超时）')), timeoutMs);
    releaseFn = () => { clearTimeout(timer); resolve(); };
  });
  return {promise, release: releaseFn};
}

const bodyBox = () => screen.getByLabelText('正文', {exact: true}) as HTMLTextAreaElement;

beforeEach(() => { clearAllStashedDrafts(); });
afterEach(() => { cleanup(); });

type Counters = {post: number; famAGet: number; libraryGet: number};

function makeTransport(options: {
  counters: Counters; libraryGate?: Promise<void>; lateFamA?: Promise<void>;
}): StudioGraphTransport {
  const {counters} = options;
  return {
    async json<T>(url: string, method = 'GET'): Promise<T> {
      // POST 判定必须在任何路径子串匹配之前，否则 /fam-A/revisions 会被误当成 GET。
      if (isSavePost(url, method)) {
        counters.post += 1;
        return receipt('fam-A', 'fam-A-a2') as T;
      }
      if (url.endsWith('/studio/prompts')) {
        counters.libraryGet += 1;
        // Gate on "this read happens after the save", NOT on a read index: StrictMode
        // replays the mount effect, so counting reads would gate the second mount's initial
        // load and the list would never populate at all.
        if (options.libraryGate && counters.post > 0) await options.libraryGate;
        return twoFamilyLibrary() as T;
      }
      if (url.includes('/fam-A')) {
        counters.famAGet += 1;
        // 只延迟“保存之后”的那一次再读（第一次是用户打开家族 A 的初读）。
        if (options.lateFamA && counters.famAGet > 1) await options.lateFamA;
        return familyDetail('fam-A', '家族 A 的正文') as T;
      }
      return familyDetail('fam-B', '家族 B 的正文') as T;
    },
  };
}

describe('保存成功后迟到的家族 A 详情不得污染用户已切换到的家族 B', () => {
  it('场景 A：保存后详情已发起但未返回时切到 B', async () => {
    const counters: Counters = {post: 0, famAGet: 0, libraryGet: 0};
    const lateFamA = gate();
    const transport = makeTransport({counters, lateFamA: lateFamA.promise});
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);

      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(bodyBox().value).toBe('家族 A 的正文'), {timeout: 3000});
      expect(counters.famAGet, '打开家族 A 的初读').toBe(1);

      fireEvent.change(bodyBox(), {target: {value: '我在 A 家族里改的正文'}});
      fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));

      // POST 必须真正走 receipt 分支：恰好一次，且回执被解码。
      await waitFor(() => expect(counters.post).toBe(1), {timeout: 3000});
      await waitFor(() => expect(document.querySelector('.prompt-status')?.textContent)
        .toContain('已保存'), {timeout: 3000});
      // 保存后的第二次 A 详情再读确实被发起（被 lateFamA 挡住）。
      await waitFor(() => expect(counters.famAGet).toBe(2), {timeout: 3000});

      fireEvent.click(libraryItems()[1]);
      await waitFor(() => expect(bodyBox().value).toBe('家族 B 的正文'), {timeout: 3000});

      lateFamA.release();
      await new Promise(tick => setTimeout(tick, 50));
      expect(bodyBox().value).toBe('家族 B 的正文');
      expect(document.body.textContent).not.toContain('家族 A 的正文');
    } finally { lateFamA.release(); }
  });

  it('场景 B：先完成 B 的详情，再释放保存后的 library 刷新，让 submit 之后才去读 A', async () => {
    const counters: Counters = {post: 0, famAGet: 0, libraryGet: 0};
    const libraryGate = gate();
    const lateFamA = gate();
    const transport = makeTransport({counters, libraryGate: libraryGate.promise,
      lateFamA: lateFamA.promise});
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);

      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(bodyBox().value).toBe('家族 A 的正文'), {timeout: 3000});

      fireEvent.change(bodyBox(), {target: {value: '我在 A 家族里改的正文'}});
      fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));

      await waitFor(() => expect(counters.post).toBe(1), {timeout: 3000});
      // submit() 现在卡在 await refresh()：保存后的 library 读取已发起但被挡住。
      await waitFor(() => expect(counters.libraryGet).toBeGreaterThanOrEqual(2), {timeout: 3000});
      expect(counters.famAGet, '此时 submit 还没开始它的 A 详情再读').toBe(1);

      // 用户在 library 刷新尚未返回时切到 B，并等 B 的详情真正显示。
      fireEvent.click(libraryItems()[1]);
      await waitFor(() => expect(bodyBox().value).toBe('家族 B 的正文'), {timeout: 3000});

      // 放行 library 刷新 → submit 继续，此时它才发起 A 家族的详情再读。
      libraryGate.release();
      await waitFor(() => expect(counters.famAGet).toBe(2), {timeout: 3000});
      lateFamA.release();
      await new Promise(tick => setTimeout(tick, 50));

      expect(bodyBox().value, '迟到的 A 详情覆盖了用户选择的 B').toBe('家族 B 的正文');
      expect(document.body.textContent).not.toContain('家族 A 的正文');
    } finally { libraryGate.release(); lateFamA.release(); }
  });
});
