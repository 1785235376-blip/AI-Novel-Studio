// [HERMIA-FE-20261022 U2] 漫画分格模板：参考常见漫画分镜（大格+小格、建立镜头、斜切、竖长格、三段不等高、
// 跨页大图、不规则 5-6 格、嵌入小格、出血无框格）。纯数据：每格是 grid-area 坐标 + 可选 clip-path/样式类。
export type PanelDef = {area: string; clip?: string; cls?: 'inset' | 'bleed'};
export type ComicTemplate = {id: string; label: string; hint: string; cols: string; rows: string; panels: PanelDef[]};
const A = (r1: number, c1: number, r2: number, c2: number) => `${r1} / ${c1} / ${r2} / ${c2}`;
export const COMIC_TEMPLATES: ComicTemplate[] = [
  {id: 'grid4', label: '四格均分', hint: '四格漫画 / 节奏平稳', cols: '1fr 1fr', rows: '1fr 1fr', panels: [{area: A(1, 1, 2, 2)}, {area: A(1, 2, 2, 3)}, {area: A(2, 1, 3, 2)}, {area: A(2, 2, 3, 3)}]},
  {id: 'big1small2', label: '一大两小', hint: '重点画面在上，反应在下', cols: '1fr 1fr', rows: '1.8fr 1fr', panels: [{area: A(1, 1, 2, 3)}, {area: A(2, 1, 3, 2)}, {area: A(2, 2, 3, 3)}]},
  {id: 'establish3', label: '建立镜头 + 三格', hint: '顶部宽景交代场景', cols: '1fr 1fr 1fr', rows: '1.2fr 1fr', panels: [{area: A(1, 1, 2, 4)}, {area: A(2, 1, 3, 2)}, {area: A(2, 2, 3, 3)}, {area: A(2, 3, 3, 4)}]},
  // 斜切：两格的盒子只在中间一行重叠，各自 clip 出平行斜边，保证斜向留白与其他格一致、点击区域不被对方盖住
  {id: 'diagonal', label: '斜切分格', hint: '动作 / 冲突，斜向分隔线', cols: '1fr 1fr', rows: '1fr .5fr 1fr 1.1fr', panels: [
    {area: A(1, 1, 3, 3), clip: 'polygon(0 0,100% 0,100% 67%,0 100%)'},
    {area: A(2, 1, 4, 3), clip: 'polygon(0 39%,100% 5%,100% 100%,0 100%)'},
    {area: A(4, 1, 5, 2)}, {area: A(4, 2, 5, 3)}]},
  {id: 'tallLeft', label: '左竖长 + 右三格', hint: '人物全身 / 下落感', cols: '1.1fr 1fr', rows: '1fr 1fr 1fr', panels: [{area: A(1, 1, 4, 2)}, {area: A(1, 2, 2, 3)}, {area: A(2, 2, 3, 3)}, {area: A(3, 2, 4, 3)}]},
  {id: 'tiers3', label: '三段不等高', hint: '窄-宽-中，控制阅读停顿', cols: '1fr 1fr', rows: '0.8fr 1.6fr 1fr', panels: [{area: A(1, 1, 2, 3)}, {area: A(2, 1, 3, 3)}, {area: A(3, 1, 4, 2)}, {area: A(3, 2, 4, 3)}]},
  {id: 'irregular6', label: '不规则六格', hint: '对话密集的常规页', cols: '1fr 1fr 1fr', rows: '1fr 1.3fr 1fr', panels: [{area: A(1, 1, 2, 3)}, {area: A(1, 3, 2, 4)}, {area: A(2, 1, 4, 2)}, {area: A(2, 2, 3, 4)}, {area: A(3, 2, 4, 3)}, {area: A(3, 3, 4, 4)}]},
  {id: 'irregular5', label: '不规则五格', hint: '一格特写夹在中间', cols: '1fr 1fr', rows: '1fr 1.4fr 1fr', panels: [{area: A(1, 1, 2, 2)}, {area: A(1, 2, 2, 3)}, {area: A(2, 1, 3, 3)}, {area: A(3, 1, 4, 2)}, {area: A(3, 2, 4, 3)}]},
  {id: 'inset', label: '大格 + 嵌入小格', hint: '远景里插一个特写', cols: '1fr', rows: '1fr', panels: [{area: A(1, 1, 2, 2)}, {area: A(1, 1, 2, 2), cls: 'inset'}]},
  {id: 'bleed', label: '出血大图 + 两格', hint: '无框画面铺到页边', cols: '1fr 1fr', rows: '1.7fr 1fr', panels: [{area: A(1, 1, 2, 3), cls: 'bleed'}, {area: A(2, 1, 3, 2)}, {area: A(2, 2, 3, 3)}]},
  {id: 'splash', label: '整页大图', hint: '高潮 / 章节开篇', cols: '1fr', rows: '1fr', panels: [{area: A(1, 1, 2, 2)}]},
];
export const templateById = (id: string) => COMIC_TEMPLATES.find(t => t.id === id) ?? COMIC_TEMPLATES[0]!;

export type BubbleKind = 'speech' | 'thought' | 'shout' | 'whisper' | 'caption' | 'sfx';
export type TailDir = 'bl' | 'br' | 'tl' | 'tr' | 'l' | 'r' | 'none';
export const BUBBLE_KINDS: {id: BubbleKind; label: string}[] = [
  {id: 'speech', label: '对话'}, {id: 'thought', label: '心声'}, {id: 'shout', label: '喊叫'},
  {id: 'whisper', label: '耳语'}, {id: 'caption', label: '旁白框'}, {id: 'sfx', label: '拟声字'}];
export const TAIL_DIRS: {id: TailDir; label: string}[] = [
  {id: 'bl', label: '↙ 左下'}, {id: 'br', label: '↘ 右下'}, {id: 'tl', label: '↖ 左上'}, {id: 'tr', label: '↗ 右上'},
  {id: 'l', label: '← 左'}, {id: 'r', label: '→ 右'}, {id: 'none', label: '无尾巴'}];
export type Bubble = {id: string; text: string; x: number; y: number; w: number; kind: BubbleKind; tail: TailDir; vertical?: boolean};
export const DEFAULT_TEXT: Record<BubbleKind, string> = {speech: '双击改写台词', thought: '（心里想…）', shout: '站住！', whisper: '小声点…', caption: '雾港，凌晨三点。', sfx: '轰'};
export const hasTail = (k: BubbleKind) => k === 'speech' || k === 'whisper' || k === 'shout';
/** 换模板时保留已有格子的气泡；多出的格子留空，少了的格子气泡并入最后一格（不悄悄丢台词）。 */
export function remapCells(cells: Bubble[][], count: number): Bubble[][] {
  const out = Array.from({length: count}, (_, i) => [...(cells[i] ?? [])]);
  if (cells.length > count && count > 0) out[count - 1] = [...out[count - 1]!, ...cells.slice(count).flat()];
  return out;
}
