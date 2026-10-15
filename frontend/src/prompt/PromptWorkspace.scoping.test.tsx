// @vitest-environment jsdom
/**
 * R3-U3-D 专项 —— 迟到的家族详情与比较状态的作用域。
 *
 * 1. 保存成功后会自动再读一次已打开家族的详情。它**迟到**时不得覆盖用户此刻已切换到的
 *    另一个家族（跨 family / project / branch / actor 一律不允许）。
 * 2. 切换家族后，上一个家族的正文明文比较结果不得继续显示在新家族下（已复现并修复）。
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

/**
 * 库行的可访问名含 "IMAGE"，编辑器里的用途 <select> 选项也含 "IMAGE"，因此 role+name 有歧义。
 * 直接查已发布的库行元素。
 */
function libraryItems(): HTMLElement[] {
  const region = document.querySelector('[aria-label="Prompt 列表"]');
  return region ? (Array.from(region.querySelectorAll('.prompt-list-item')) as HTMLElement[]) : [];
}

const receipt = (familyId: string, assetId: string) => ({
  family_id: familyId, asset_id: assetId, revision: 2, asset_version: 2,
  text_digest: 'd'.repeat(64), idempotent_replay: false,
  previous_asset_id: `${familyId}-a1`, payload_digest: 'p'.repeat(64),
});

/** 两个结构相同、正文不同的家族。 */
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

function deferred() {
  let resolveFn: () => void = () => {};
  const promise = new Promise<void>(resolve => { resolveFn = resolve; });
  return {promise, resolve: resolveFn};
}

const bodyBox = () => screen.getByLabelText('正文', {exact: true}) as HTMLTextAreaElement;

beforeEach(() => { clearAllStashedDrafts(); });
afterEach(() => { cleanup(); });

describe('a late post-save detail must not hijack the user selection', () => {
  it('keeps family B on screen when the save-time family A detail arrives late', async () => {
    const saveGate = deferred();
    const lateDetail = deferred();
    let famAReads = 0;
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (url.endsWith('/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/fam-A')) {
          famAReads += 1;
          // Only the SECOND read (the one issued after the save) is delayed.
          if (famAReads > 1) await lateDetail.promise;
          return familyDetail('fam-A', '家族 A 的正文') as T;
        }
        if (method === 'POST') { await saveGate.promise; return receipt('fam-A', 'fam-A-a2') as T; }
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };

    render(<StrictMode><PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} /></StrictMode>);

    await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
    fireEvent.click(libraryItems()[0]);
    await waitFor(() => expect(bodyBox().value).toBe('家族 A 的正文'), {timeout: 3000});

    fireEvent.change(bodyBox(), {target: {value: '我在 A 家族里改的正文'}});
    fireEvent.click(screen.getByRole('button', {name: '保存新版本'}));
    await waitFor(() => expect(famAReads).toBeGreaterThan(1), {timeout: 3000});

    // The user moves to family B while the save and its follow-up detail read are in flight.
    fireEvent.click(libraryItems()[1]);
    await waitFor(() => expect(bodyBox().value).toBe('家族 B 的正文'), {timeout: 3000});

    saveGate.resolve();
    lateDetail.resolve();
    await new Promise(tick => setTimeout(tick, 50));

    // B stays on screen; a stale A detail may not take over the user's selection.
    expect(bodyBox().value).toBe('家族 B 的正文');
    expect(document.body.textContent).not.toContain('家族 A 的正文');
  });
});

describe('comparison state follows the family', () => {
  it('clears the previous family diff when another family is selected', async () => {
    const transport: StudioGraphTransport = {
      async json<T>(url: string, method = 'GET'): Promise<T> {
        if (url.endsWith('/prompts')) return twoFamilyLibrary() as T;
        if (url.includes('/revisions/') && url.endsWith('/body')) {
          const raw = structuredClone(fixture('revision-1-body.json')) as Record<string, unknown>;
          raw.value = url.includes('fam-A') ? '家族 A 的旧正文' : '家族 B 的旧正文';
          raw.verified = true;
          raw.read_complete = true;
          raw.state = 'COMPLETE';
          return raw as T;
        }
        if (url.includes('/fam-A')) return familyDetail('fam-A', '家族 A 的正文') as T;
        return familyDetail('fam-B', '家族 B 的正文') as T;
      },
    };

    render(<PromptWorkspace projectId="p1" actor="author-a" transport={transport}
      mode="PROFESSIONAL" writable denied={false} />);
    await waitFor(() => expect(libraryItems().length).toBe(2), {timeout: 3000});
    fireEvent.click(libraryItems()[0]);
    await waitFor(() => expect(bodyBox().value).toBe('家族 A 的正文'), {timeout: 3000});

    fireEvent.click(screen.getByRole('button', {name: '比较正文'}));
    await waitFor(() => expect(document.querySelector('.prompt-diff table')).toBeTruthy(),
      {timeout: 3000});
    expect(document.body.textContent).toContain('家族 A 的旧正文');

    fireEvent.click(libraryItems()[1]);
    await waitFor(() => expect(bodyBox().value).toBe('家族 B 的正文'), {timeout: 3000});
    expect(document.querySelector('.prompt-diff table'),
      '上一个家族的比较结果不得留在新家族下').toBeNull();
    expect(document.body.textContent).not.toContain('家族 A 的旧正文');
  });
});
