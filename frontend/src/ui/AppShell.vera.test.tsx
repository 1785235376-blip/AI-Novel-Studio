// @vitest-environment jsdom
// [HERMIA-FE-20261025 VERA-FIX MF-3/MF-4] Vera re-review: accessible names asserted via getByRole(name),
// so removing the visible search text or reverting en overflow.aria.pro fails here; Cmd-K list has no id column.
import {cleanup,fireEvent,render,screen,within} from '@testing-library/react';
import {afterEach,beforeEach,describe,expect,it,vi} from 'vitest';
import {AppShell,ModuleOverflowMenu,ShellSettingsMenu} from './AppShell';
import {setLocale} from '../i18n';
import {STUDIO_MODULES,STUDIO_MODULE_OVERFLOW} from './moduleRegistry';
const props={module:'NOVEL' as const,onModuleChange:vi.fn(),scope:{workspace:'',project:'',storyline:'',branch:''},actor:'author',sidebar:null,main:'Editor',inspector:null,status:'Saved'};
beforeEach(()=>{Object.defineProperty(window,'innerWidth',{configurable:true,writable:true,value:1440});});
afterEach(()=>{cleanup();setLocale('zh-CN');localStorage.clear();});
describe('global-search accessible name keeps the real label (not only "Ctrl K")',()=>{
  it.each([['zh-CN','搜索功能、章节或命令'],['en','Search chapters, commands']] as const)('%s',(loc,label)=>{
    setLocale(loc);render(<AppShell {...props}/>);
    const btn=screen.getByRole('button',{name:`${label} Ctrl K`});
    expect(btn.className).toContain('global-search');
    // name must start with the visible label text (axe label-content-name-mismatch)
    expect(btn.textContent?.trim().startsWith(label)).toBe(true);
  });
});
describe('en pro overflow trigger name contains its visible text',()=>{
  it('Pro more → "Pro more workspaces"',()=>{
    setLocale('en');render(<ModuleOverflowMenu value="NOVEL" onChange={vi.fn()} shellMode="pro"/>);
    const btn=screen.getByRole('button',{name:'Pro more workspaces'});
    const visible=btn.textContent!.trim();
    expect(visible).toBe('Pro more');
    expect(btn.getAttribute('aria-label')!.startsWith(visible)).toBe(true);
  });
});
describe('Cmd-K list has no internal id column',()=>{
  it.each(['basic','pro'] as const)('%s',mode=>{
    render(<AppShell {...props} shellMode={mode}/>);
    fireEvent.click(screen.getByRole('button',{name:/Ctrl K/}));
    const list=screen.getByRole('listbox');
    const ids=[...STUDIO_MODULES,...STUDIO_MODULE_OVERFLOW].map(m=>m.id);
    for(const opt of within(list).getAllByRole('option')){
      const txt=opt.textContent||'';
      for(const id of ids) expect(txt.includes(id),`option "${txt}" shows id ${id}`).toBe(false);
    }
  });
});

// [HERMIA-FE-20261025 VERA-FIX2] kills C1 (ModuleOverflowMenu) / C2 (ShellSettingsMenu): normal mode must not show internal ids
const OV_IDS=STUDIO_MODULE_OVERFLOW.map(m=>m.id);
function openMenu(c:HTMLElement){const trig=c.querySelector('button[aria-haspopup="menu"]') as HTMLButtonElement;expect(trig).not.toBeNull();fireEvent.click(trig);const menu=c.querySelector('[role="menu"]') as HTMLElement;expect(menu).not.toBeNull();return menu;}
describe.each([['ModuleOverflowMenu',ModuleOverflowMenu],['ShellSettingsMenu',ShellSettingsMenu]] as const)('%s: normal mode hides module ids',(_n,Menu)=>{
  it.each(['NOVEL',OV_IDS[0]] as const)('value=%s basic → no <small>, no id text',v=>{
    const {container}=render(<Menu value={v as any} onChange={vi.fn()} shellMode="basic"/>);
    const menu=openMenu(container);
    expect(menu.querySelectorAll('[role="menuitem"],button').length).toBeGreaterThan(0);
    expect(menu.querySelectorAll('small').length).toBe(0);
    for(const id of OV_IDS) expect(menu.textContent!.includes(id),`basic shows ${id}`).toBe(false);
  });
  it('pro may show ids (positive control)',()=>{
    const {container}=render(<Menu value="NOVEL" onChange={vi.fn()} shellMode="pro"/>);
    const menu=openMenu(container);
    expect(menu.querySelectorAll('small').length).toBe(OV_IDS.length);
  });
});
describe('global-search title carries the full label (ellipsis fallback)',()=>{
  it.each([['zh-CN','搜索功能、章节或命令'],['en','Search chapters, commands']] as const)('%s',(loc,label)=>{
    setLocale(loc);render(<AppShell {...props} shellMode="pro"/>);
    const btn=screen.getByRole('button',{name:`${label} Ctrl K`});
    expect(btn.getAttribute('title')).toBe(label);
    expect(btn.getAttribute('aria-label')).toBeNull();
  });
});
