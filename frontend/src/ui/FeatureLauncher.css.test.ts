import {describe,expect,it} from 'vitest';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {readFileSync} from 'node:fs';
// @ts-expect-error Node built-ins are provided by the Vitest runtime.
import {fileURLToPath} from 'node:url';

const css=readFileSync(fileURLToPath(new URL('./FeatureLauncher.css',import.meta.url)),'utf8').replace(/\s+/g,'');
const app=readFileSync(fileURLToPath(new URL('../App.tsx',import.meta.url)),'utf8').replace(/\s+/g,'');

describe('feature launcher layout contract',()=>{
  it('gives chapters and the feature overlay independent scroll containers',()=>{
    expect(css).toContain('.sidebar-chapter-scroll{flex:11auto;min-height:0;height:auto;overflow-x:hidden;overflow-y:auto');
    expect(css).toContain('.feature-launcher__scroll{min-height:0;overflow-x:hidden;overflow-y:auto');
    expect(css).toContain('max-height:min(55vh,calc(100vh-var(--layout-header-height)-var(--layout-context-height)-var(--layout-status-height)-var(--space-12)-var(--control-height-lg)-var(--space-8)))');
  });

  it('anchors the overlay to the sidebar without a viewport-fixed layer or shell width mutation',()=>{
    expect(css).toContain('.feature-launcher{position:absolute;left:0;right:0;bottom:0');
    expect(css).toContain('nav.feature-launcher__overlay{position:absolute');
    expect(css).toContain('z-index:var(--z-overlay)');
    expect(css).toContain('.workspace-sidebar--novel{position:relative;display:flex;flex-direction:column;min-height:0;overflow:visible');
    expect(css).not.toContain('position:fixed');
    expect(css).not.toContain('100vw');
    expect(css).not.toContain('grid-template-columns:var(--layout-sidebar-width)');
  });

  it('keeps the existing feature-group persistence key and panel callback',()=>{
    expect(app).toContain('localStorage.getItem("studio-feature-groups")');
    expect(app).toContain('localStorage.setItem("studio-feature-groups",JSON.stringify(featureGroups))');
    expect(app).toContain('onSelect={setPanel}');
  });
});
