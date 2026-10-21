/**
 * [HERMIA-FE-20261022 H-P0-01] Novel-focused action aliases.
 * Maps stable action ids → existing FeatureLauncher panel ids. Opening any of these
 * MUST land in the NOVEL module (caller ensures commitStudioModule('NOVEL')).
 * Does not move novel/** files; ChapterTree / AiWriting stay where App mounts them.
 */
import type {ActionRegistry} from './actions';

/** FeatureLauncher / Panel ids that belong to the novel authoring surface. */
export const NOVEL_PANEL_IDS = [
  'history', 'creation', 'story', 'check', 'overview', 'workflow',
  'adaptation', 'screenplay', 'knowledge', 'research', 'agents', 'exports',
] as const;
export type NovelPanelId = (typeof NOVEL_PANEL_IDS)[number];
export function isNovelPanel(id: string): id is NovelPanelId {
  return (NOVEL_PANEL_IDS as readonly string[]).includes(id);
}

/** Extra command labels so users can find Revision / Creation / Continuity by novel wording. */
export function registerNovelActionAliases(
  actions: ActionRegistry,
  openFeature: (id: string) => void,
): () => void {
  const undo: Array<() => void> = [];
  const aliases: Array<{id: string; label: string; panel: NovelPanelId}> = [
    {id: 'novel.open.revisionHistory', label: '打开：章节版本历史', panel: 'history'},
    {id: 'novel.open.creationWorkbench', label: '打开：创作方案与工作台', panel: 'creation'},
    {id: 'novel.open.storyDatabase', label: '打开：故事资料库（大纲/角色/设定）', panel: 'story'},
    {id: 'novel.open.continuityCheck', label: '打开：一致性检查', panel: 'check'},
    {id: 'novel.open.aiWritingSurface', label: '回到小说写作区（正文 + AI 写作）', panel: 'history'},
  ];
  for (const a of aliases) {
    undo.push(actions.register({
      id: a.id, label: a.label, surfaces: ['commandSearch', 'button'],
      run: async () => { openFeature(a.panel); return a.panel; },
    }));
  }
  return () => undo.reverse().forEach(f => f());
}
