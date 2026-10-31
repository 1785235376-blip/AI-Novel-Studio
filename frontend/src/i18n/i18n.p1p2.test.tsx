// @vitest-environment jsdom
/** [HERMIA-FE-20261025 I18N P1/P2] "en has no Chinese" for migrated areas + tz reverse-lookup / pattern tests. */
import { describe, it, expect, beforeEach } from 'vitest';
import { render, act, cleanup } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { setLocale, translateZh, formatTime } from './index';
import { NovelOrient, NovelModTabs } from '../rebuild/novel/NovelOrient';
import { NovelStructureRail, NovelChapterColumn } from '../rebuild/novel/NovelStructureRail';
import { NovelStartEmpty } from '../rebuild/novel/NovelStartEmpty';
import { NovelAssist } from '../rebuild/novel/NovelAssist';
import { TasksBody } from '../rebuild/TasksMenu';
import { SettingsPathGateway } from '../ui/AppShell';
import { WorkspaceHonestEmpty } from '../ui/WorkspaceHonestEmpty';
import { EmptyState, Spinner } from '../ui/primitives';
import { Drawer } from '../rebuild/primitives';
import { ChapterTree } from '../novel/ChapterTree';

const HAN = /[\u4e00-\u9fff]/;
const noop = () => {};
/** visible text + aria-label/title/placeholder, user data stripped */
function ownText(el: HTMLElement, userData: string[] = []) {
  let s = (el.textContent || '') + ' ' + [...el.querySelectorAll('[aria-label],[title],[placeholder]')].map((n) => ['aria-label', 'title', 'placeholder'].map((a) => n.getAttribute(a) || '').join(' ')).join(' ');
  if (el.parentElement) s += ' ' + [...document.body.querySelectorAll('[aria-label]')].map((n) => n.getAttribute('aria-label')).join(' ');
  for (const u of userData) s = s.split(u).join('');
  return s;
}
const expectEn = (el: HTMLElement, userData: string[] = []) => {
  const s = ownText(el, userData);
  expect(s.match(/[\u4e00-\u9fff][^\sA-Za-z]*/g) || []).toEqual([]);
  expect(s).not.toMatch(/\b(orient|status|rail|nv|tk|spg|pr|he|desk|pat|as|cta)\.[a-z]/);
};
const PANELS = [
  { id: 'overview', label: '总览', status: 'ok' as const }, { id: 'write', label: '写作台', status: 'ok' as const },
  { id: 'story', label: '大纲 · 人物 · 世界观', status: 'ok' as const }, { id: 'history', label: '版本 / 修订', status: 'ok' as const, disabled: true, title: '先打开一个章节' },
  { id: 'exports', label: '导出', status: 'part' as const, title: '可导出与下载；取消 / 重试还没接上' },
];
const CH = [{ id: 'c1', number: 1, title: 'Dawn', wordCount: 1234 }, { id: 'c2', number: 2 }];

beforeEach(() => { cleanup(); localStorage.clear(); act(() => setLocale('en')); });

describe('tz reverse lookup', () => {
  it('translates known zh and templates, passes unknown through', () => {
    expect(translateZh('en', '写作台')).not.toMatch(HAN);
    expect(translateZh('en', '第 3 章 · Dawn')).toMatch(/3/);
    expect(translateZh('en', '第 3 章 · Dawn')).not.toMatch(HAN);
    expect(translateZh('en', '1200 字 · 版本 4')).not.toMatch(HAN);
    expect(translateZh('en', '保存位置：本机')).not.toMatch(HAN);
    expect(translateZh('en', '用户自己的标题')).toBe('用户自己的标题');
    expect(translateZh('zh-CN', '写作台')).toBe('写作台');
  });
  it('formatTime follows locale', () => { expect(formatTime(0, 'en', { timeZone: 'UTC', timeStyle: 'short', hour12: false })).toBe('00:00'); });
});

describe('en has no Chinese — P1/P2 areas', () => {
  it('onboarding bar + module tabs', () => {
    const { container } = render(<><NovelOrient what="《Moon》 · 第 1 章 · Dawn" can="写作台改章 · AI 生成先成候选、你采用后才进正文 · 设定需审核才进正典" effect="自动保存到本机；采用候选不会覆盖已批准设定" /><NovelModTabs tabs={[{ id: 'write', label: '写作', selected: true, onClick: noop }]} badge="写作台" /></>);
    expectEn(container, ['Moon', 'Dawn']);
  });
  it('left rail + chapter column', () => {
    const { container } = render(<><NovelStructureRail chapters={CH} selectedId="c1" onSelect={noop} onCreate={noop} panels={PANELS} activePanel="write" onOpenPanel={noop} /><NovelChapterColumn chapters={CH} onSelect={noop} onCreate={noop} /></>);
    expectEn(container, ['Dawn']);
  });
  it('rail 更多: chapter tree (loading / empty / list)', () => {
    for (const props of [{ loading: true }, { chapters: [] }, { chapters: [{ id: 'c1', title: 'Dawn', number: 1 }], selectedId: 'c1' }]) {
      cleanup();
      const { container } = render(<ChapterTree chapters={[]} {...props} onSelect={noop} onCreate={noop} onRename={noop} onArchive={noop} onRestore={noop} archived={[]} />);
      expectEn(container, ['Dawn']);
    }
  });
  it('start empty', () => { const { container } = render(<NovelStartEmpty choices={[]} onCreate={noop} />); expectEn(container); });
  it('right 创作辅助 rail', () => {
    const { container } = render(<NovelAssist chapterTitle="第 1 章 · Dawn" chapterMeta="1234 字 · 版本 2" saveLabel="已保存" saveLocation="保存位置：本机"
      primaryCta={{ label: '生成草稿', onClick: noop }} links={[{ id: 'draft', label: '生成草稿', onClick: noop }, { id: 'history', label: '版本历史', onClick: noop }]}
      outlineItems={[{ id: 'c1', label: '第 1 章 · Dawn' }]} castNote="当前人物视角：Ann" aiStatus="有候选待你确认" ai={null} onOpenStory={noop} onQuickOp={noop} />);
    expectEn(container, ['Dawn', 'Ann']);
  });
  it('task menu body (no work open)', () => {
    const qc = new QueryClient();
    const { container } = render(<QueryClientProvider client={qc}><TasksBody novelId="" /></QueryClientProvider>);
    expectEn(container);
  });
  it('settings path panel', () => { const { container } = render(<SettingsPathGateway onOpenModule={noop} />); expectEn(container); });
  it('honest empty / error / loading states', () => {
    for (const kind of ['no_project', 'load_failed', 'loading', 'no_chapter'] as const) {
      cleanup();
      const { container } = render(<WorkspaceHonestEmpty kind={kind} workspace="NOVEL" onAction={noop} />);
      expectEn(container);
    }
  });
  it('primitives: EmptyState / Spinner / Drawer', () => {
    const { container } = render(<><EmptyState title="当前还没有打开的章节" detail="在左侧新建或选择章节，开始写作。" /><Spinner /><Drawer title="Tasks" onClose={noop}>x</Drawer></>);
    expectEn(container); expectEn(document.body);
  });
});
