import {describe,expect,it} from 'vitest';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {readFileSync} from 'node:fs';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {fileURLToPath} from 'node:url';
const css=readFileSync(fileURLToPath(new URL('./style.css',import.meta.url)),'utf8');
const tokens=readFileSync(fileURLToPath(new URL('./ui/tokens.css',import.meta.url)),'utf8');
const compact=(value:string)=>value.replace(/\s+/g,'');
const styles=compact(css),designTokens=compact(tokens);
describe('manuscript typography contract',()=>{
 it('loads the real stylesheets',()=>{expect(styles.length).toBeGreaterThan(100);expect(designTokens.length).toBeGreaterThan(100)});
 it('uses deliberate long-form typography',()=>{expect(styles).toMatch(/\.editor\.ProseMirror\{[^}]*line-height:1\.8;[^}]*font-family:var\(--font-editor\);[^}]*font-size:16px;/);expect(styles).toContain('.editor.ProseMirrorp{margin:00.7em}');expect(designTokens).toMatch(/--font-editor:[^;]+;/)});
 it('keeps constrained width and responsive padding',()=>{expect(styles).toMatch(/\.editor\{[^}]*max-width:850px;[^}]*padding:40px64px;/);expect(styles).toContain('@media(min-width:1101px)and(max-width:1440px){.editor{padding-left:48px;padding-right:48px}}');expect(styles).toContain('@media(max-width:1100px){.editor{padding-left:32px;padding-right:32px}}')});
});
