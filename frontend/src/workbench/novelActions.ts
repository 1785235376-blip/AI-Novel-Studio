/**
 * [HERMIA-FE-20261022 H-P0-01 / overnight / N-UX-10] Novel-focused action aliases.
 * Maps stable action ids → existing FeatureLauncher panel ids OR focus hooks.
 * MUST land in NOVEL (caller ensures commitStudioModule('NOVEL')).
 * Does not invent new FL item ids (inventory: 今晚不瞎编 id); ChapterTree / AiWriting stay mounted.
 * N-UX-10: 设定/世界观 aliases open FL `story` (World*) — never storyboard bible.
 */
import type {ActionRegistry} from './actions';

/** FeatureLauncher / Panel ids that belong to the novel authoring surface. */
export const NOVEL_PANEL_IDS = [
  'write', 'history', 'creation', 'story', 'check', 'overview', 'workflow',
  'adaptation', 'screenplay', 'knowledge', 'research', 'agents', 'exports',
] as const;
export type NovelPanelId = (typeof NOVEL_PANEL_IDS)[number];
export function isNovelPanel(id: string): id is NovelPanelId {
  return (NOVEL_PANEL_IDS as readonly string[]).includes(id);
}

export type NovelFocusTarget = 'aiWriting' | 'chapterTree' | 'editor';

/**
 * openFeature: open a panel id (write/history/story/…).
 * focusSurface: optional UI focus without inventing FL ids (T1 AiWriting / ChapterTree / Editor).
 */
export function registerNovelActionAliases(
  actions: ActionRegistry,
  openFeature: (id: string) => void,
  focusSurface?: (target: NovelFocusTarget) => void,
): () => void {
  const undo: Array<() => void> = [];
  const aliases: Array<{id: string; label: string; panel: NovelPanelId}> = [
    {id: 'novel.open.revisionHistory', label: '打开：章节版本历史', panel: 'history'},
    {id: 'novel.open.creationWorkbench', label: '打开：创作方案与工作台', panel: 'creation'},
    {id: 'novel.open.storyDatabase', label: '打开：故事资料库（大纲/角色/小说设定）', panel: 'story'},
    {id: 'novel.open.storyPlanning', label: '打开：故事规划（经资料库 story）', panel: 'story'},
    // N-UX-10: same FL id `story` — novel World* / 设定；≠ 分镜 BibleWorkspace
    {id: 'novel.open.worldBuilding', label: '打开：世界观设定（story / World*，≠ 分镜 Bible）', panel: 'story'},
    {id: 'novel.open.novelSettings', label: '打开：小说设定与世界观（经故事资料库）', panel: 'story'},
    {id: 'novel.open.continuityCheck', label: '打开：一致性检查', panel: 'check'},
    {id: 'novel.open.pendingCanon', label: '打开：一致性与待审 Canon', panel: 'check'},
    {id: 'novel.open.writingShell', label: '回到纯写作主面', panel: 'write'},
    {id: 'novel.open.aiWritingSurface', label: '回到小说写作区（正文 + AI 写作）', panel: 'write'},
    {id: 'novel.open.overview', label: '打开：小说概览', panel: 'overview'},
    // workflow FL id kept; label elsewhere clarifies ≠ AiWriting旁路
    {id: 'novel.open.workflowSurface', label: '打开：工作流编排面（非 AI 旁路）', panel: 'workflow'},
  ];
  for (const a of aliases) {
    undo.push(actions.register({
      id: a.id, label: a.label, surfaces: ['commandSearch', 'button'],
      run: async () => { openFeature(a.panel); return a.panel; },
    }));
  }
  const focuses: Array<{id: string; label: string; target: NovelFocusTarget}> = [
    {id: 'novel.focus.aiWriting', label: '聚焦：AI 写作旁路（右栏）', target: 'aiWriting'},
    {id: 'novel.focus.chapterTree', label: '聚焦：章节树', target: 'chapterTree'},
    {id: 'novel.focus.editor', label: '聚焦：正文编辑器', target: 'editor'},
  ];
  for (const f of focuses) {
    undo.push(actions.register({
      id: f.id, label: f.label, surfaces: ['commandSearch', 'button'],
      run: async () => {
        openFeature('write');
        focusSurface?.(f.target);
        return f.target;
      },
    }));
  }
  return () => undo.reverse().forEach(fn => fn());
}
