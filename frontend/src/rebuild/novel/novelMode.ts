/* [HERMIA-FE-20261022 U4] 小说 普通/专业：普通＝写作台 + 继续写 + 大纲（一条主线、一个主按钮）；
   专业另有 设定审核（待审设定）/ 连续性检查 / 版本对比 / 研究。专业→普通时停在这些面板会回落写作台，章节与草稿不动。 */
export type ShellMode = 'basic' | 'pro';
export const NOVEL_PRO_PANELS = new Set(['check', 'history', 'research', 'workflow', 'agents']); // [HERMIA-FE-20261025 DUI P1-6] 工作流/AI 任务编排仅专业
export const NOVEL_PRO_TABS = new Set(['canon', 'continuity', 'revision']);
export const NOVEL_PRO_LINKS = new Set(['continuity', 'pending-canon', 'history']);
export const novelPanelAllowed = (id: string, mode: ShellMode) => mode === 'pro' || !NOVEL_PRO_PANELS.has(id);
export function gateNovel<T extends {id: string}>(items: T[], pro: Set<string>, mode: ShellMode): T[] {
  return mode === 'pro' ? items : items.filter(i => !pro.has(i.id));
}
