// @vitest-environment jsdom
/**
 * R3-U3-D 任务 1 —— loading 所有权。
 *
 * 上一次修复让“已被废弃的 selectFamily 读取”在自己的 catch 里无条件清除共享 loading。
 * 但 loading 是**共享**标志：若 A 的读取已被废弃、而 B 的读取正在进行，A 的失败会把
 * B 的 loading 清掉 —— 界面提前显示“已就绪”，保存按钮被错误启用。
 *
 * 这里用受控 gate 编排：A 挂起 → B 挂起 → A 失败 → 断言 B 仍处于读取中 → B 成功 → 断言就绪。
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

/** 库面板的“重新读取”按钮在 loading 时文案为“正在读取…”。 */
const libraryBusy = (): boolean =>
  !!screen.queryByRole('button', {name: '正在读取…'});

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

describe('任务 1：被废弃的读取不得清除仍在进行的读取所拥有的 loading', () => {
  it('A 失败时 B 仍在读取，界面不得提前认为已就绪', async () => {
    const gateA = gate();
    const gateB = gate();
    let failA = true;
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (url.endsWith('/studio/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-A')) {
          await gateA.promise;
          if (failA) {
            throw new ApiError({status: 500, code: 'HTTP_500', message: 'A 家族读取失败'});
          }
          return familyDetail('fam-A', '家族 A 的正文') as T;
        }
        await gateB.promise;
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };
    try {
      render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
        mode="PROFESSIONAL" writable denied={false} /></StrictMode>);
      await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});

      // A 的详情读取挂起，紧接着 B 的详情读取也挂起。
      fireEvent.click(libraryItems()[0]);
      await waitFor(() => expect(libraryBusy()).toBe(true), {timeout: 3000});
      fireEvent.click(libraryItems()[1]);
      await waitFor(() => expect(libraryBusy()).toBe(true), {timeout: 3000});

      // 让已被废弃的 A 失败。它的错误属于用户已经离开的家族，因此**不应**显示出来；
      // 真正要断言的是它不得把 B 正在进行中的 loading 一起清掉。
      gateA.release();
      await new Promise(tick => setTimeout(tick, 60));
      expect(document.body.textContent, '已被废弃的 A 的错误不应显示给用户')
        .not.toContain('A 家族读取失败');

      // B 仍在读取：loading 必须仍然为真（保存按钮仍被禁用）。
      expect(libraryBusy(), 'A 的失败清掉了 B 正在拥有的 loading').toBe(true);
      const save = screen.queryByRole('button', {name: '保存新版本'})
        ?? screen.queryByRole('button', {name: '保存为新 Prompt'});
      expect(save && (save as HTMLButtonElement).disabled,
        'B 仍在读取时保存按钮却被启用').toBe(true);

      // 放行 B：当前详情、草稿与按钮都必须正确。
      gateB.release();
      await waitFor(() => expect(historyText()).toContain('fam-B-a1'), {timeout: 3000});
      expect(libraryBusy()).toBe(false);
      expect((screen.getByLabelText('正文', {exact: true}) as HTMLTextAreaElement).value)
        .toBe('家族 B 的正文');
    } finally { gateA.release(); gateB.release(); }
  });
});
