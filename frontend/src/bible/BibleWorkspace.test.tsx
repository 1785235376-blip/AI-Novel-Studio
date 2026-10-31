// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api';
import { BibleWorkspace } from './BibleWorkspace';
import { fixtureBareProjection, fixtureEmptyProjection, fixtureProjection } from './bibleFixtures.testFixture';
import { CHARACTER_BIBLE_FIELDS, SCENE_BIBLE_FIELDS, UNKNOWN, type BibleClient } from './bibleTypes';

/**
 * 这些测试断言的是 Round2-B 的**可见契约**，不是外观：
 *  - 六个角色维度、七个场景维度都必须真的出现；
 *  - `UNKNOWN` 必须显示成字面量并标注"未作者化"，不能是空白；
 *  - `DRAFT` 必须标注非 canon，`APPROVED` 才显示 CANON；
 *  - 参考素材必须逐个标注 RESOLVED / UNRESOLVED；
 *  - 面板里**不能有任何写入入口**（本轮是纯只读）。
 */

function clientFor(result: unknown): BibleClient {
  return { readBible: vi.fn(async () => result) } as unknown as BibleClient;
}
function failingClient(error: unknown): BibleClient {
  return { readBible: vi.fn(async () => { throw error; }) } as unknown as BibleClient;
}

afterEach(cleanup);

describe('角色与场景圣经工作区', () => {
  it('显示全部六个角色维度与七个场景维度', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const characters = await screen.findByLabelText('角色圣经');
    for (const field of CHARACTER_BIBLE_FIELDS) {
      expect(characters.querySelectorAll(`[data-field="${field}"]`).length, field).toBeGreaterThan(0);
    }
    const scenes = screen.getByLabelText('场景圣经');
    for (const field of SCENE_BIBLE_FIELDS) {
      expect(scenes.querySelectorAll(`[data-field="${field}"]`).length, field).toBeGreaterThan(0);
    }
  });

  it('未 authoring 的维度显示 UNKNOWN 并标注未作者化，而不是留空', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const scenes = await screen.findByLabelText('场景圣经');
    for (const field of ['material', 'weather']) {
      const row = scenes.querySelector(`[data-field="${field}"]`)!;
      expect(row.getAttribute('data-state')).toBe('UNKNOWN');
      expect(row.textContent).toContain(UNKNOWN);
      expect(row.textContent).toContain('未作者化');
    }
  });

  it('DRAFT 标注非 canon，已批准显示 CANON · APPROVED', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const scenes = await screen.findByLabelText('场景圣经');
    const architecture = scenes.querySelector('[data-field="architecture"]')!;
    expect(architecture.getAttribute('data-canon')).toBe('DRAFT');
    expect(architecture.textContent).toContain('DRAFT');
    expect(architecture.textContent).toContain('非 canon');

    const characters = screen.getByLabelText('角色圣经');
    const appearance = characters.querySelector('[data-field="appearance"]')!;
    expect(appearance.getAttribute('data-canon')).toBe('CANON');
    expect(appearance.textContent).toContain('CANON · APPROVED');
  });

  it('参考素材逐个标注 RESOLVED / UNRESOLVED，并说明未提供索引的情况', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const characters = await screen.findByLabelText('角色圣经');
    const reference = characters.querySelector('[data-field="reference"]')!;
    expect(reference.textContent).toContain('RESOLVED');
    expect(reference.textContent).toContain('UNRESOLVED');
    expect(reference.textContent).toContain('a1');
    expect(reference.textContent).toContain('a2');
  });

  it('面板里没有任何写入入口', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    await screen.findByLabelText('角色圣经');
    const panel = screen.getByText('角色与场景圣经').closest('section')!;
    expect(within(panel).queryByRole('button', { name: /保存|编辑|修改|应用|提交|新建|删除/ })).toBeNull();
    expect(within(panel).queryByRole('textbox')).toBeNull();
    expect(within(panel).queryByRole('combobox')).toBeNull();
    // 只读声明必须可见。
    expect(panel.textContent).toContain('没有编辑入口');
  });

  it('显示每个维度的来源，便于核对值来自哪个 owner', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const characters = await screen.findByLabelText('角色圣经');
    const appearance = characters.querySelector('[data-field="appearance"]')!;
    expect(appearance.textContent).toContain('world_records.CHARACTER_VISUAL.appearance');
  });

  it('完全没有外形的角色：外形/服装/参考图都是 UNKNOWN', async () => {
    render(<BibleWorkspace client={clientFor(fixtureBareProjection())} />);
    const characters = await screen.findByLabelText('角色圣经');
    for (const field of ['appearance', 'clothing']) {
      const row = characters.querySelector(`[data-field="${field}"]`)!;
      expect(row.getAttribute('data-state')).toBe('UNKNOWN');
      expect(row.textContent).toContain('未作者化');
    }
    const reference = characters.querySelector('[data-field="reference"]')!;
    expect(reference.textContent).toContain('没有声明任何参考素材');
  });

  it('显示出现位置，且只来自原文档真实引用', async () => {
    render(<BibleWorkspace client={clientFor(fixtureProjection())} />);
    const characters = await screen.findByLabelText('角色圣经');
    expect(characters.textContent).toContain('场景角色表');
    expect(characters.textContent).toContain('镜头角色表');
    expect(characters.textContent).toContain('d1');
  });

  it('空项目进入 EMPTY 语义，并说明设定由原界面创建', async () => {
    render(<BibleWorkspace client={clientFor(fixtureEmptyProjection())} />);
    await waitFor(() => expect(screen.getByText('这个项目还没有角色记录。角色由原记录界面创建，这里不会替你生成。')).toBeTruthy());
    // 两个分区各自说明，且都不允许本工作面代生成内容。
    expect(screen.getByText('这个项目还没有地点记录。地点由原记录界面创建，这里不会替你生成。')).toBeTruthy();
    expect(screen.getAllByText(/不会替你生成/)).toHaveLength(2);
  });

  it('读失败显示机器码，绝不被当成"暂无内容"', async () => {
    const error = new ApiError({ status: 500, code: 'STUDIO_BIBLE_READ_FAILED', message: '读取失败' });
    render(<BibleWorkspace client={failingClient(error)} />);
    await waitFor(() => expect(screen.getByText(/STUDIO_BIBLE_READ_FAILED/)).toBeTruthy());
    expect(screen.queryByText(/这个项目还没有角色记录/)).toBeNull();
  });

  it('无权读取时显示为 DENIED', async () => {
    const error = new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: '无权读取' });
    render(<BibleWorkspace client={failingClient(error)} />);
    await waitFor(() => expect(screen.getByText(/CREATIVE_AUTHORITY_INVALID/)).toBeTruthy());
  });

  it('未激活时不发请求', async () => {
    const client = clientFor(fixtureProjection());
    render(<BibleWorkspace client={client} active={false} />);
    await waitFor(() => expect(screen.getByText(/工作区当前未激活/)).toBeTruthy());
    expect(client.readBible).not.toHaveBeenCalled();
  });
});
