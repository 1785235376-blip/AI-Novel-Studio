import {describe,expect,it} from 'vitest';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {readFileSync} from 'node:fs';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {fileURLToPath} from 'node:url';

const css=readFileSync(fileURLToPath(new URL('./novel.css',import.meta.url)),'utf8').replace(/\s+/g,'');
const globalCss=readFileSync(fileURLToPath(new URL('../style.css',import.meta.url)),'utf8').replace(/\s+/g,'');

describe('chapter directory CSS contract',()=>{
 it('loads real CSS and protects long title layout',()=>{expect(css.length).toBeGreaterThan(100);expect(css).toContain('.novel-tree-title{min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}');expect(css).toContain('.novel-chapter-tree.novel-tree-select{flex:11auto;min-width:0;width:auto;display:flex');expect(css).not.toContain('!important')});
 it('constrains both ChapterTree grid tracks and rename controls',()=>{expect(css).toContain('.novel-chapter-tree{display:grid;grid-template-columns:minmax(0,1fr)');expect(css).toContain('.novel-chapter-treeol{list-style:none;padding:0;margin:0;display:grid;grid-template-columns:minmax(0,1fr)');expect(css).toContain('.novel-tree-rename.ui-button{flex:none;width:auto');expect(globalCss).toContain('.treebutton{width:100%');expect('.novel-chapter-tree .novel-tree-rename .ui-button'.split(' ').length).toBeGreaterThan('.tree button'.split(' ').length)});
 it('reserves a stable selected indicator and action footprint',()=>{expect(css).toContain('border-left:3pxsolidtransparent');expect(css).toContain('.novel-tree-row.is-selected{border-left-color:var(--color-accent-primary)');expect(css).toContain('.novel-chapter-tree.novel-tree-actions{flex:00auto;flex-shrink:0;display:flex')});
 it('protects archived titles with the same overflow contract',()=>{expect(css).toContain('.novel-archive-title{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}')});
});
