// @vitest-environment jsdom
import { cleanup, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { ApiError } from '../api';
import { DirectorWorkspace } from './DirectorWorkspace';
import { fixtureEmptyProjection, fixtureProjection } from './directorWorkspaceFixtures.testFixture';
import {
  CONTINUITY_DIMENSIONS, DIRECTOR_INTENT_FIELDS, SHOT_CARD_FIELDS,
  type DirectorWorkspaceClient,
} from './directorWorkspaceTypes';

/**
 * 这些测试断言的是 Phase14-A 的**可见契约**，不是外观：
 *  - 七个导演意图维度、十一个镜头卡字段、五个连续性维度都必须真的出现；
 *  - "逐镜头统计"不得被渲染成"导演已决定的文档值"；
 *  - 旧写法原样保留，不折算成规范值；
 *  - 读失败不得被当成"暂无内容"。
 */

const DOCUMENT_ID = 'doc-1';

function clientFor(result: unknown): DirectorWorkspaceClient {
  return { readDirectorWorkspace: vi.fn(async () => result) } as unknown as DirectorWorkspaceClient;
}
function failingClient(error: unknown): DirectorWorkspaceClient {
  return { readDirectorWorkspace: vi.fn(async () => { throw error; }) } as unknown as DirectorWorkspaceClient;
}

afterEach(cleanup);

describe('导演工作台', () => {
  it('显示全部七个导演意图维度', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    await waitFor(() => expect(screen.getByLabelText('导演意图')).toBeTruthy());
    const intent = screen.getByLabelText('导演意图');
    for (const field of DIRECTOR_INTENT_FIELDS) {
      expect(intent.querySelector(`[data-field="${field}"]`), field).toBeTruthy();
    }
  });

  it('显示全部十一个镜头卡字段', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    const shots = await screen.findByLabelText('镜头卡');
    for (const field of SHOT_CARD_FIELDS) {
      expect(shots.querySelectorAll(`[data-field="${field}"]`).length, field).toBeGreaterThan(0);
    }
  });

  it('显示全部五个连续性维度与"只提示不自动修改"的声明', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    const continuity = await screen.findByLabelText('连续性检查');
    for (const field of CONTINUITY_DIMENSIONS) {
      expect(continuity.querySelector(`[data-field="${field}"]`), field).toBeTruthy();
    }
    expect(continuity.textContent).toContain('只提示');
    expect(continuity.textContent).toContain('不自动修改');
    // 面板里没有任何写入口：没有提交/保存/应用按钮。
    expect(within(continuity).queryByRole('button', { name: /保存|应用|修正|提交/ })).toBeNull();
  });

  it('把统计与 authoring 分开显示，不把统计说成决定', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    const intent = await screen.findByLabelText('导演意图');
    const camera = intent.querySelector('[data-field="camera_language"]')!;
    expect(camera.getAttribute('data-kind')).toBe('PER_SHOT_MEASURED');
    expect(camera.textContent).toContain('逐镜头统计');
    // 文档级 authoring 的维度才显示 authoring 的值。
    const genre = intent.querySelector('[data-field="genre"]')!;
    expect(genre.getAttribute('data-kind')).toBe('DOCUMENT_AUTHORED');
    expect(genre.textContent).toContain('悬疑科幻');
  });

  it('原样保留旧写法景别，并标注出来', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    const shots = await screen.findByLabelText('镜头卡');
    expect(shots.textContent).toContain('很宽的镜头');
    expect(shots.textContent).toContain('旧写法保留');
  });

  it('镜头语言下拉的取值来自后端发布的词表', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureProjection())} documentId={DOCUMENT_ID} />);
    const shots = await screen.findByLabelText('镜头卡');
    const selects = shots.querySelectorAll('select');
    expect(selects.length).toBeGreaterThan(0);
    const movement = Array.from(selects).find(select => select.getAttribute('aria-label') === '摄影机运动')!;
    const options = Array.from(movement.querySelectorAll('option')).map(option => option.textContent);
    expect(options).toContain('DOLLY');
    expect(options).toContain('TRACKING');
  });

  it('原文档未 authoring 的字段显示"原文档未提供"，不补一个像样的值', async () => {
    const projection = fixtureProjection();
    projection.shot_cards = [{
      ...projection.shot_cards[0],
      lighting: { field: 'lighting', value: '', authored: false, source: 'ShotCard.lighting', owner: 'ShotCard.lighting' },
      emotion: { field: 'emotion', value: '', authored: false, source: 'ShotCard.emotion', owner: 'ShotCard.emotion' },
    }];
    render(<DirectorWorkspace client={clientFor(projection)} documentId={DOCUMENT_ID} />);
    const shots = await screen.findByLabelText('镜头卡');
    const lighting = shots.querySelector('[data-field="lighting"]')!;
    expect(lighting.textContent).toContain('原文档未提供');
    expect(shots.querySelector('[data-field="emotion"]')!.textContent).toContain('原文档未提供');
  });

  it('空文档进入 EMPTY 语义，并说明镜头由原界面创建', async () => {
    render(<DirectorWorkspace client={clientFor(fixtureEmptyProjection())} documentId={DOCUMENT_ID} />);
    await waitFor(() => expect(screen.getByText('原文档还没有镜头。镜头由原分镜界面创建，这里不会替你生成。')).toBeTruthy());
    expect(screen.getByText(/原文档还没有镜头或导演备注/)).toBeTruthy();
    expect(screen.getByText(/不会替你生成/)).toBeTruthy();
  });

  it('读失败显示机器码，绝不被当成"暂无内容"', async () => {
    const error = new ApiError({ status: 500, code: 'STUDIO_DIRECTOR_WORKSPACE_READ_FAILED', message: '读取失败' });
    render(<DirectorWorkspace client={failingClient(error)} documentId={DOCUMENT_ID} />);
    await waitFor(() => expect(screen.getByText(/STUDIO_DIRECTOR_WORKSPACE_READ_FAILED/)).toBeTruthy());
    expect(screen.queryByText(/原文档还没有镜头/)).toBeNull();
  });

  it('无权读取时显示为 DENIED 而不是通用失败', async () => {
    const error = new ApiError({ status: 403, code: 'CREATIVE_AUTHORITY_INVALID', message: '无权读取' });
    render(<DirectorWorkspace client={failingClient(error)} documentId={DOCUMENT_ID} />);
    await waitFor(() => expect(screen.getByText(/CREATIVE_AUTHORITY_INVALID/)).toBeTruthy());
  });

  it('未选定文档时不发请求', async () => {
    const client = clientFor(fixtureProjection());
    render(<DirectorWorkspace client={client} documentId={null} />);
    await waitFor(() => expect(screen.getByText(/尚未选定文档/)).toBeTruthy());
    expect(client.readDirectorWorkspace).not.toHaveBeenCalled();
  });

  it('未激活时不发请求', async () => {
    const client = clientFor(fixtureProjection());
    render(<DirectorWorkspace client={client} documentId={DOCUMENT_ID} active={false} />);
    await waitFor(() => expect(screen.getByText(/工作台当前未激活/)).toBeTruthy());
    expect(client.readDirectorWorkspace).not.toHaveBeenCalled();
  });
});
