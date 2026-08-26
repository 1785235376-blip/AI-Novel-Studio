import {readFileSync} from 'node:fs';import {describe,expect,it} from 'vitest';
const tokens=readFileSync(new URL('../src/ui/tokens.css',import.meta.url),'utf8');const ui=readFileSync(new URL('../src/ui/ui.css',import.meta.url),'utf8');
describe('DS-v1.0 contracts',()=>{
 it('defines every frozen layout token',()=>{for(const name of ['header-height','context-height','sidebar-width','inspector-width','status-height','workspace-min','content-gap'])expect(tokens).toContain(`--layout-${name}:`)});
 it('defines one accent family and semantic states',()=>{for(const name of ['accent-primary','accent-hover','accent-active','accent-subtle','status-success','status-warning','status-error','status-info'])expect(tokens).toContain(`--color-${name}:`)});
 it('builds the shell geometry from tokens',()=>{expect(ui).toContain('var(--layout-header-height)');expect(ui).toContain('var(--layout-sidebar-width)');expect(ui).toContain('var(--layout-inspector-width)')});
 it('keeps the Inspector recoverable across desktop and narrow shell layouts',()=>{expect(ui).toContain('.app-shell.is-inspector-collapsed .workspace-body{grid-template-columns:var(--layout-sidebar-width) minmax(var(--layout-workspace-min),1fr)}');expect(ui).toContain('@media(max-width:1100px)');expect(ui).toContain('.workspace-inspector{position:absolute');expect(ui).not.toContain('@media(max-width:1100px){.workspace-inspector{display:none}')});
});
