// [HERMIA-FE-20261022 U4] 小说门控
import {describe, it, expect} from 'vitest';
import {gateNovel, novelPanelAllowed, NOVEL_PRO_PANELS, NOVEL_PRO_TABS, NOVEL_PRO_LINKS} from './novelMode';
const rail = ['overview', 'write', 'story', 'check', 'history', 'research', 'exports'].map(id => ({id}));
const tabs = ['overview', 'writer', 'outline', 'cast', 'canon', 'continuity', 'revision'].map(id => ({id}));
const links = ['draft', 'story-planning', 'continuity', 'pending-canon', 'history'].map(id => ({id}));
describe('novel mode gating', () => {
  it('basic hides 设定审核/连续性/版本/研究; keeps 写作台+大纲', () => {
    expect(gateNovel(rail, NOVEL_PRO_PANELS, 'basic').map(x => x.id)).toEqual(['overview', 'write', 'story', 'exports']);
    expect(gateNovel(tabs, NOVEL_PRO_TABS, 'basic').map(x => x.id)).toEqual(['overview', 'writer', 'outline', 'cast']);
    expect(gateNovel(links, NOVEL_PRO_LINKS, 'basic').map(x => x.id)).toEqual(['draft', 'story-planning']);
  });
  it('pro keeps everything; basic falls back from pro panels', () => {
    expect(gateNovel(rail, NOVEL_PRO_PANELS, 'pro')).toHaveLength(rail.length);
    expect(gateNovel(tabs, NOVEL_PRO_TABS, 'pro')).toHaveLength(tabs.length);
    expect(['check', 'history', 'research'].map(p => novelPanelAllowed(p, 'basic'))).toEqual([false, false, false]);
    expect(novelPanelAllowed('write', 'basic')).toBe(true);
    expect(novelPanelAllowed('check', 'pro')).toBe(true);
  });
});
