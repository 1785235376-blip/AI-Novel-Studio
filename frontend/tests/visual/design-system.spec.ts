import {expect, test, type Page, type Route} from '@playwright/test';

const modules = ['NOVEL', 'IMAGE', 'VIDEO'] as const;
test.beforeEach(async ({page}) => {
  await page.addStyleTag({content: '*,*::before,*::after{animation:none!important;transition:none!important;caret-color:transparent!important}'});
});

for (const module of modules) test(`${module.toLowerCase()} workspace visual baseline`, async ({page}) => {
  await page.goto(`/ui-fixture?module=${module}`);
  await page.evaluate(() => document.fonts.ready);
  await expect(page.locator('.app-shell')).toHaveScreenshot(`${module.toLowerCase()}-workspace.png`);
});

for (const viewport of [{width:1024,height:768},{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]) test(`shell geometry ${viewport.width}x${viewport.height}`, async ({page}) => {
  await page.setViewportSize(viewport);
  await page.goto('/ui-fixture?module=NOVEL');
  const geometry = await page.evaluate(() => {
    const rect = (selector:string) => { const r=document.querySelector(selector)!.getBoundingClientRect(); return {x:r.x,y:r.y,width:r.width,height:r.height}; };
    return {header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),switcher:rect('.module-switcher')};
  });
  expect(geometry.header.height).toBe(56); expect(geometry.context.height).toBe(44); expect(geometry.status.height).toBe(32);
  expect(geometry.sidebar.width).toBe(viewport.width<1100?200:248); expect(geometry.inspector.width).toBe(viewport.width<1100?0:340); expect(geometry.switcher.y).toBe(0);
});

test('compact desktop keeps the workspace within the viewport', async ({page}) => {
  await page.setViewportSize({width:1024,height:768});
  await page.goto('/ui-fixture?module=NOVEL');
  const overflow = await page.evaluate(() => ({ width: document.documentElement.scrollWidth, viewport: window.innerWidth, body: document.body.scrollWidth }));
  expect(overflow.width).toBeLessThanOrEqual(overflow.viewport);
  expect(overflow.body).toBeLessThanOrEqual(overflow.viewport);
});

test('production NOVEL route uses the frozen AppShell', async ({page}) => {
  await page.addInitScript(() => {localStorage.setItem('studio.session','visual-session');localStorage.setItem('studio.scope',JSON.stringify({workspaceId:'workspace-real',projectId:'project-real',storylineId:'storyline-real',branchId:'branch-real'}));});
  await page.goto('/');
  await expect(page.locator('.app-shell[data-module="NOVEL"]')).toBeVisible();
  await expect(page.locator('.context-bar')).toContainText('当前工作区');
  await expect(page.locator('.context-bar')).not.toContainText('workspace-real');
  await expect(page.locator('.context-bar')).not.toContainText('星海残章');
  await expect(page.locator('.app-shell')).toHaveScreenshot('production-novel-shell.png');
});

const v058Scope={workspaceId:'workspace-v058',projectId:'project-v058',storylineId:'storyline-v058',branchId:'branch-v058'};
async function seedV058Production(page:Page, conflict=false) {
  await page.addInitScript(({scope,conflict}) => {
    localStorage.setItem('studio.session','visual-session'); localStorage.setItem('studio.scope',JSON.stringify(scope));
    if (conflict) {
      let hash=2166136261; for(const character of 'visual-session') hash=Math.imul(hash^character.charCodeAt(0),16777619);
      const namespace=`${[scope.workspaceId,scope.projectId,scope.storylineId,scope.branchId].join('\u001f')}\u001fclient:${(hash>>>0).toString(36)}`;
      const local={chapterId:'chapter-v058',content:'Local resolution draft',baseVersion:1,updatedAt:'2026-08-10T10:00:00Z'};
      localStorage.setItem(`ai-novel-studio:draft:${namespace}:chapter-v058`,JSON.stringify(local));
      localStorage.setItem(`ai-novel-studio:conflict:${namespace}:chapter-v058`,JSON.stringify({chapterId:'chapter-v058',local,server:{id:'chapter-v058',novel_id:scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'},detectedAt:'2026-08-10T10:01:00Z'}));
    }
  }, {scope:v058Scope,conflict});
  await page.route('**/api/**', async (route:Route) => {
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/bootstrap')) return route.fulfill({json:{actor:{actor_id:'actor-v058',session_id:'session-v058',client_id:'client-v058'},scope:{workspace_id:v058Scope.workspaceId,project_id:v058Scope.projectId,storyline_id:v058Scope.storylineId,branch_id:v058Scope.branchId},capabilities:{}}});
    if(path.endsWith('/chapters')&&path.includes('/collaboration/')) return route.fulfill({json:{items:[{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',version:2,word_count:3,status:'DRAFT'}]}});
    if(path.endsWith('/chapters/chapter-v058/revisions/1')) return route.fulfill({json:{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Historical content'}]}]}}});
    if(path.endsWith('/chapters/chapter-v058/revisions')) return route.fulfill({json:{chapter_id:'chapter-v058',current_version:2,items:[{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old'}]}});
    if(path.endsWith('/api/chapters/chapter-v058')&&route.request().method()==='GET') return route.fulfill({json:{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'}});
    if(path.includes('/history/1/restore')) return route.fulfill({status:409,json:{detail:{code:'VERSION_CONFLICT',message:'Current version changed',actual_version:3}}});
    return route.fulfill({json:{items:[]}});
  });
}

test('production conflict compare and manual resolution visual', async ({page}) => {
  await seedV058Production(page,true); await page.goto('/');
  await expect(page.locator('[role="dialog"]')).toBeVisible();
  await expect(page.locator('[role="dialog"]')).toContainText('Local resolution draft');
  await expect(page.locator('[role="dialog"]')).toContainText('Latest server content');
  await expect(page.locator('[role="dialog"]')).toHaveScreenshot('production-conflict-resolution.png');
});

test('production revision detail restore preview and conflict visual', async ({page}) => {
  await seedV058Production(page); await page.goto('/');
  await page.getByRole('button',{name:'版本历史',exact:true}).click();
  await expect(page.locator('.revision-panel')).toBeVisible();
  await page.locator('.revision-timeline button').first().click();
  await expect(page.locator('.revision-detail')).toContainText('Historical content');
  await page.locator('.revision-detail>.ui-button').click();
  await expect(page.locator('.revision-confirm')).toBeVisible();
  await page.locator('.revision-confirm .ui-button--primary').click();
  await expect(page.locator('.revision-restore-message[role="alert"]')).toBeVisible();
  await expect(page.locator('.revision-panel')).toHaveScreenshot('production-revision-restore-conflict.png');
});
