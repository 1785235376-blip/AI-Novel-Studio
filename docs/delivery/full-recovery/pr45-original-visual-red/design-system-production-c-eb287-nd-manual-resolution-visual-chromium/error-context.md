# Instructions

- Following Playwright test failed.
- Explain why, be concise, respect Playwright best practices.
- Provide a snippet of code with the fix, if possible.

# Test info

- Name: design-system.spec.ts >> production conflict compare and manual resolution visual
- Location: tests\visual\design-system.spec.ts:67:1

# Error details

```
Error: expect(locator).toBeVisible() failed

Locator: locator('[role="dialog"]')
Expected: visible
Timeout: 5000ms
Error: element(s) not found

Call log:
  - Expect "toBeVisible" with timeout 5000ms
  - waiting for locator('[role="dialog"]')

```

# Test source

```ts
  1  | import {expect, test, type Page, type Route} from '@playwright/test';
  2  | 
  3  | const modules = ['NOVEL', 'IMAGE', 'VIDEO'] as const;
  4  | test.beforeEach(async ({page}) => {
  5  |   await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
  6  | });
  7  | 
  8  | for (const module of modules) test(`${module.toLowerCase()} workspace visual baseline`, async ({page}) => {
  9  |   await page.goto(`/ui-fixture?module=${module}`);
  10 |   await page.evaluate(() => document.fonts.ready);
  11 |   await expect(page.locator('.app-shell')).toHaveScreenshot(`${module.toLowerCase()}-workspace.png`);
  12 | });
  13 | 
  14 | for (const viewport of [{width:1024,height:768},{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]) test(`shell geometry ${viewport.width}x${viewport.height}`, async ({page}) => {
  15 |   await page.setViewportSize(viewport);
  16 |   await page.goto('/ui-fixture?module=NOVEL');
  17 |   const geometry = await page.evaluate(() => {
  18 |     const rect = (selector:string) => { const r=document.querySelector(selector)!.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
  19 |     return {header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),switcher:rect('.module-switcher')};
  20 |   });
  21 |   expect(geometry.header.height).toBe(56); expect(geometry.context.height).toBe(44); expect(geometry.status.height).toBe(32);
  22 |   expect(geometry.sidebar.width).toBe(viewport.width<1100?200:248); expect(geometry.inspector.width).toBe(viewport.width<1100?0:340); expect(geometry.switcher.y).toBe(0);
  23 | });
  24 | 
  25 | test('compact desktop keeps the workspace within the viewport', async ({page}) => {
  26 |   await page.setViewportSize({width:1024,height:768});
  27 |   await page.goto('/ui-fixture?module=NOVEL');
  28 |   const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: window.innerWidth, body: document.body.scrollWidth }));
  29 |   expect(overflow.width).toBeLessThanOrEqual(overflow.viewport);
  30 |   expect(overflow.body).toBeLessThanOrEqual(overflow.viewport);
  31 | });
  32 | 
  33 | test('production NOVEL route uses the frozen AppShell', async ({page}) => {
  34 |   await page.addInitScript(() => {localStorage.setItem('studio.session','visual-session');localStorage.setItem('studio.scope',JSON.stringify({workspaceId:'workspace-real',projectId:'project-real',storylineId:'storyline-real',branchId:'branch-real'}));});
  35 |   await page.goto('/');
  36 |   await expect(page.locator('.app-shell[data-module="NOVEL"]')).toBeVisible();
  37 |   await expect(page.locator('.context-bar')).toContainText('当前工作区');
  38 |   await expect(page.locator('.context-bar')).not.toContainText('workspace-real');
  39 |   await expect(page.locator('.context-bar')).not.toContainText('星海残章');
  40 |   await expect(page.locator('.app-shell')).toHaveScreenshot('production-novel-shell.png');
  41 | });
  42 | 
  43 | const v058Scope={workspaceId:'workspace-v058',projectId:'project-v058',storylineId:'storyline-v058',branchId:'branch-v058'};
  44 | async function seedV058Production(page:Page, conflict=false) {
  45 |   await page.addInitScript(({scope,conflict}) => {
  46 |     localStorage.setItem('studio.session','visual-session'); localStorage.setItem('studio.scope',JSON.stringify(scope));
  47 |     if (conflict) {
  48 |       let hash=2166136261; for(const character of 'visual-session') hash=Math.imul(hash^character.charCodeAt(0),16777619);
  49 |       const namespace=`${[scope.workspaceId,scope.projectId,scope.storylineId,scope.branchId].join('\u001f')}\u001fclient:${(hash>>>0).toString(36)}`;
  50 |       const local={chapterId:'chapter-v058',content:'Local resolution draft',baseVersion:1,updatedAt:'2026-08-10T10:00:00Z'};
  51 |       localStorage.setItem(`ai-novel-studio:draft:${namespace}:chapter-v058`,JSON.stringify(local));
  52 |       localStorage.setItem(`ai-novel-studio:conflict:${namespace}:chapter-v058`,JSON.stringify({chapterId:'chapter-v058',local,server:{id:'chapter-v058',novel_id:scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'},detectedAt:'2026-08-10T10:01:00Z'}));
  53 |     }
  54 |   }, {scope:v058Scope,conflict});
  55 |   await page.route('**/api/**', async (route:Route) => {
  56 |     const path=new URL(route.request().url()).pathname;
  57 |     if(path.endsWith('/bootstrap')) return route.fulfill({json:{actor:{actor_id:'actor-v058',session_id:'session-v058',client_id:'client-v058'},scope:{workspace_id:v058Scope.workspaceId,project_id:v058Scope.projectId,storyline_id:v058Scope.storylineId,branch_id:v058Scope.branchId},capabilities:{}}});
  58 |     if(path.endsWith('/chapters')&&path.includes('/collaboration/')) return route.fulfill({json:{items:[{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',version:2,word_count:3,status:'DRAFT'}]}});
  59 |     if(path.endsWith('/chapters/chapter-v058/revisions/1')) return route.fulfill({json:{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Historical content'}]}]}}});
  60 |     if(path.endsWith('/chapters/chapter-v058/revisions')) return route.fulfill({json:{chapter_id:'chapter-v058',current_version:2,items:[{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old'}]}});
  61 |     if(path.endsWith('/api/chapters/chapter-v058')&&route.request().method()==='GET') return route.fulfill({json:{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'}});
  62 |     if(path.includes('/history/1/restore')) return route.fulfill({status:409,json:{detail:{code:'VERSION_CONFLICT',message:'Current version changed',actual_version:3}}});
  63 |     return route.fulfill({json:{items:[]}});
  64 |   });
  65 | }
  66 | 
  67 | test('production conflict compare and manual resolution visual', async ({page}) => {
  68 |   await seedV058Production(page,true); await page.goto('/');
> 69 |   await expect(page.locator('[role="dialog"]')).toBeVisible();
     |                                                 ^ Error: expect(locator).toBeVisible() failed
  70 |   await expect(page.locator('[role="dialog"]')).toContainText('Local resolution draft');
  71 |   await expect(page.locator('[role="dialog"]')).toContainText('Latest server content');
  72 |   await expect(page.locator('[role="dialog"]')).toHaveScreenshot('production-conflict-resolution.png');
  73 | });
  74 | 
  75 | test('production revision detail restore preview and conflict visual', async ({page}) => {
  76 |   await seedV058Production(page); await page.goto('/');
  77 |   await page.getByRole('button',{name:'版本历史',exact:true}).click();
  78 |   await expect(page.locator('.revision-panel')).toBeVisible();
  79 |   await page.locator('.revision-timeline button').first().click();
  80 |   await expect(page.locator('.revision-detail')).toContainText('Historical content');
  81 |   await page.locator('.revision-detail>.ui-button').click();
  82 |   await expect(page.locator('.revision-confirm')).toBeVisible();
  83 |   await page.locator('.revision-confirm .ui-button--primary').click();
  84 |   await expect(page.locator('.revision-restore-message[role="alert"]')).toBeVisible();
  85 |   await expect(page.locator('.revision-panel')).toHaveScreenshot('production-revision-restore-conflict.png');
  86 | });
  87 | 
```