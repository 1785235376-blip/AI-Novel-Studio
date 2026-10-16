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
  await seedProductionShell(page);
  await page.goto('/');
  await expect(page.locator('.app-shell[data-module="NOVEL"]')).toBeVisible();
  await expect(page.locator('.context-bar')).toContainText('当前工作区');
  await expect(page.locator('.context-bar')).not.toContainText('workspace-real');
  await expect(page.locator('.context-bar')).not.toContainText('星海残章');
  await expect(page.locator('.novel-chapter-tree')).toContainText('还没有章节');
  await page.evaluate(() => document.fonts.ready);
  const geometry=await page.evaluate(()=>{
    const rect=(selector:string)=>{const r=document.querySelector(selector)!.getBoundingClientRect();return {width:r.width,height:r.height,left:r.left,right:r.right,bottom:r.bottom};};
    return {viewport:{width:innerWidth,height:innerHeight},shell:rect('.app-shell'),header:rect('.global-header'),context:rect('.context-bar'),sidebar:rect('.workspace-sidebar'),main:rect('.main-workspace'),inspector:rect('.workspace-inspector'),status:rect('.status-bar'),pageScrollWidth:document.documentElement.scrollWidth};
  });
  expect(geometry.viewport).toEqual({width:1440,height:900});
  expect(geometry.shell.width).toBe(1440);expect(geometry.shell.height).toBe(900);
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);
  expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);
  expect(geometry.main.width).toBe(804);
  expect(geometry.main.left).toBeGreaterThanOrEqual(geometry.sidebar.right);
  expect(geometry.main.right).toBeLessThanOrEqual(geometry.inspector.left);
  expect(geometry.pageScrollWidth).toBeLessThanOrEqual(geometry.viewport.width);
  await expect(page.locator('.app-shell')).toHaveScreenshot('production-novel-shell.png');
});

async function seedProductionShell(page:Page) {
  const scope={workspaceId:'workspace-real',projectId:'project-real',storylineId:'storyline-real',branchId:'branch-real',workspaceName:'当前工作区',projectName:'测试小说',storylineName:'测试故事线',branchName:'测试草稿'};
  await page.addInitScript(scope=>{localStorage.setItem('studio.session','visual-session');localStorage.setItem('studio.scope',JSON.stringify(scope));},{...scope});
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/bootstrap'))return route.fulfill({json:{actor:{actor_id:'测试创作者',session_id:'session-real',client_id:'client-real'},scope:{workspace_id:scope.workspaceId,project_id:scope.projectId,storyline_id:scope.storylineId,branch_id:scope.branchId},capabilities:{}}});
    if(path.endsWith('/writing-goal'))return route.fulfill({json:{current_words:0,target_words:0,current_chapters:0,target_chapters:0,words_progress:0,chapters_progress:0,deadline:''}});
    if(path.endsWith('/text-models'))return route.fulfill({json:{items:[]}});
    if(path.endsWith('/chapters/archived'))return route.fulfill({json:[]});
    if(path.endsWith('/experimental/features'))return route.fulfill({json:{experimental:false,default_enabled:false,features:{}}});
    if(path.endsWith('/media-tasks'))return route.fulfill({json:{novel_id:scope.projectId,audiobook:[],motion:[]}});
    return route.fulfill({json:{items:[]}});
  });
}

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
    if(path.endsWith('/writing-goal')) return route.fulfill({json:{current_words:3,target_words:0,current_chapters:1,target_chapters:0,words_progress:0,chapters_progress:0}});
    if(path.endsWith('/text-models')) return route.fulfill({json:{items:[]}});
    if(path.endsWith('/chapters/archived')) return route.fulfill({json:[]});
    if(path.endsWith('/experimental/features')) return route.fulfill({json:{experimental:false,default_enabled:false,features:{}}});
    if(path.endsWith('/chapters')&&path.includes('/collaboration/')) return route.fulfill({json:{items:[{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',version:2,word_count:3,status:'DRAFT'}]}});
    if(path.endsWith('/chapters/chapter-v058/revisions/1')) return route.fulfill({json:{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old',document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'Historical content'}]}]}}});
    if(path.endsWith('/chapters/chapter-v058/revisions')) return route.fulfill({json:{chapter_id:'chapter-v058',current_version:2,items:[{version:1,timestamp:'2026-08-10T09:00:00Z',source:'USER',operator:'actor-old',reason:'MANUAL_SAVE',actor_id:'actor-old'}]}});
    if(path.endsWith('/api/chapters/chapter-v058')&&route.request().method()==='GET') return route.fulfill({json:{id:'chapter-v058',novel_id:v058Scope.projectId,number:1,title:'Conflict chapter',content:'Latest server content',document:{type:'doc',content:[]},version:2,word_count:3,status:'DRAFT'}});
    if(path.includes('/history/1/restore')) return route.fulfill({status:409,json:{detail:{code:'VERSION_CONFLICT',message:'Current version changed',actual_version:3}}});
    return route.fulfill({json:{items:[]}});
  });
}

async function openProductionFeature(page:Page, name:string) {
  await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
  await page.getByRole('navigation',{name:'功能面板导航'}).getByRole('button',{name,exact:true}).click();
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
  await openProductionFeature(page,'版本历史');
  await expect(page.locator('.revision-panel')).toBeVisible();
  await page.locator('.revision-timeline button').first().click();
  await expect(page.locator('.revision-detail')).toContainText('Historical content');
  await page.locator('.revision-detail>.ui-button').click();
  await expect(page.locator('.revision-confirm')).toBeVisible();
  await page.locator('.revision-confirm .ui-button--primary').click();
  await expect(page.locator('.revision-restore-message[role="alert"]')).toBeVisible();
  await page.locator('.revision-panel').scrollIntoViewIfNeeded();
  const geometry = await page.locator('.revision-panel').evaluate(panel => {
    const rect=panel.getBoundingClientRect();
    const main=panel.closest('.main-workspace')!.getBoundingClientRect();
    const status=document.querySelector('.status-bar')!.getBoundingClientRect();
    return {viewport:{width:innerWidth,height:innerHeight},panel:{width:rect.width,left:rect.left,right:rect.right,top:rect.top,bottom:rect.bottom},main:{left:main.left,right:main.right},statusTop:status.top,panelWidth:panel.clientWidth,panelScrollWidth:panel.scrollWidth,pageScrollWidth:document.documentElement.scrollWidth};
  });
  expect(geometry.viewport).toEqual({width:1440,height:900});
  expect(geometry.panel.width).toBe(802);
  expect(geometry.panel.left).toBeGreaterThanOrEqual(geometry.main.left);
  expect(geometry.panel.right).toBeLessThanOrEqual(geometry.main.right);
  expect(geometry.panel.top).toBeGreaterThanOrEqual(100);
  expect(geometry.panel.bottom).toBeLessThanOrEqual(geometry.statusTop);
  expect(geometry.panelScrollWidth).toBeLessThanOrEqual(geometry.panelWidth);
  expect(geometry.pageScrollWidth).toBeLessThanOrEqual(geometry.viewport.width);
  await expect(page.locator('.revision-panel')).toHaveScreenshot('production-revision-restore-conflict.png');
});
