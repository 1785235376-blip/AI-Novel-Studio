import {expect,test,type Page} from '@playwright/test';

const token='e2e-admin-session';
const scopeA={workspaceId:'e2e-workspace-a',projectId:'e2e-project-a',storylineId:'e2e-story-a',branchId:'e2e-branch-a'};

async function enter(page:Page){
  await page.addInitScript(({token,scope})=>{localStorage.setItem('studio.session',token);localStorage.setItem('studio.scope',JSON.stringify(scope));},{token,scope:scopeA});
  await page.goto('/');
  await page.locator('.tree nav button').filter({hasText:'members'}).click();
  await expect(page.locator('.workspace-management')).toBeVisible();
}

async function recoveryNamespace(page:Page){return page.evaluate(({token,scope})=>{let hash=2166136261;for(const character of token)hash=Math.imul(hash^character.charCodeAt(0),16777619);return `${scope.workspaceId}\u001f${scope.projectId}\u001f${scope.storylineId}\u001f${scope.branchId}\u001fclient:${(hash>>>0).toString(36)}`},{token,scope:scopeA})}

test('production workspace management uses the real trusted-session PostgreSQL chain',async({page})=>{
  await page.route('**/api/collaboration/workspaces/e2e-workspace-a/projects/e2e-project-a/storylines/e2e-story-a/branches/e2e-branch-a/chapters',route=>route.fulfill({json:{items:[]}}));
  const requests:Array<{method:string,url:string,body:any}>=[];
  page.on('request',request=>{if(request.url().includes('/api/collaboration/admin/'))requests.push({method:request.method(),url:request.url(),body:request.postDataJSON()})});
  await enter(page);

  const sidebar=page.locator('.workspace-management__sidebar');
  await sidebar.locator('.section-heading button').click();
  await sidebar.locator('form input').fill('Browser Created Workspace');
  await sidebar.locator('form button[type="submit"]').click();
  await expect(sidebar).toContainText('Browser Created Workspace');
  const create=requests.find(item=>item.method==='POST'&&item.url.endsWith('/admin/workspaces'))!;
  expect(create.body.name).toBe('Browser Created Workspace');expect(create.body.actor_id).toBeUndefined();

  const currentPanel=page.locator('.workspace-management__main .ui-panel').first();
  await currentPanel.locator('button').click();
  await currentPanel.locator('form input').fill('E2E Workspace A Renamed');
  await currentPanel.locator('form button[type="submit"]').click();
  await expect(currentPanel).toContainText('E2E Workspace A Renamed');
  await page.reload();await page.locator('.tree nav button').filter({hasText:'members'}).click();
  await expect(page.locator('.workspace-management')).toContainText('E2E Workspace A Renamed');

  const memberPanel=page.locator('.workspace-management__main .ui-panel').nth(1);
  await memberPanel.locator('header button').click();
  await memberPanel.locator('form input').fill('e2e-candidate');
  await memberPanel.locator('form button[type="submit"]').click();
  await expect(memberPanel).toContainText('E2E Candidate');
  await memberPanel.locator('.member-item').filter({hasText:'E2E Candidate'}).click();
  await memberPanel.locator('.member-detail button').click();
  await page.locator('[role="alertdialog"] button').first().click();
  await expect(memberPanel.locator('.member-detail')).toContainText('INACTIVE');

  await page.locator('.tree nav button').filter({hasText:'permissions'}).click();
  const grant=page.locator('.permission-grant');
  await grant.locator('input').fill('e2e-member');
  await grant.locator('select').nth(0).selectOption('DOMAIN_LEAD');
  await grant.locator('select').nth(1).selectOption('NOVEL');
  await grant.locator('button[type="submit"]').click();
  const lead=page.locator('.permission-assignment').filter({hasText:'DOMAIN_LEAD'}).filter({hasText:'E2E Member'});
  await expect(lead).toBeVisible();await lead.getByRole('button',{name:'Revoke'}).click();await expect(lead).toHaveCount(0);
  await grant.locator('input').fill('e2e-member');
  await grant.locator('select').nth(0).selectOption('DIRECT');
  await grant.locator('button[type="submit"]').click();
  const direct=page.locator('.permission-assignment').filter({hasText:'DIRECT'}).filter({hasText:'E2E Member'});
  await expect(direct).toBeVisible();await direct.getByRole('button',{name:'Revoke'}).click();await expect(direct).toHaveCount(0);

  await page.locator('.tree nav button').filter({hasText:'members'}).click();
  const navResponse=page.waitForResponse(response=>response.url().includes('/e2e-workspace-b/navigation'));
  await page.locator('.workspace-list__item').filter({hasText:'E2E Empty Workspace B'}).click();expect((await navResponse).status()).toBe(200);
  await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('studio.scope')!))).toEqual({workspaceId:'e2e-workspace-b',projectId:'',storylineId:'',branchId:''});
  expect(requests.some(item=>item.url.includes('/e2e-workspace-b/members'))).toBeTruthy();
});

async function routeChapter(page:Page){
  await page.route('**/api/collaboration/workspaces/e2e-workspace-a/projects/e2e-project-a/storylines/e2e-story-a/branches/e2e-branch-a/chapters',route=>route.fulfill({json:{items:[{id:'e2e-chapter',novel_id:'e2e-project-a',number:1,title:'Safety',content:'Saved text',document:{type:'doc',content:[]},version:1,word_count:2,status:'DRAFT'}]}}));
  await page.route('**/api/collaboration/workspaces/e2e-workspace-a/projects/e2e-project-a/storylines/e2e-story-a/branches/e2e-branch-a/chapters/e2e-chapter/revisions',route=>route.fulfill({json:{items:[]}}));
  await page.route('**/api/chapters/e2e-chapter',route=>route.fulfill({json:{id:'e2e-chapter',novel_id:'e2e-project-a',number:1,title:'Safety',content:'Saved text',document:{type:'doc',content:[]},version:1,word_count:2,status:'DRAFT'}}));
}

test('production browser fails closed on dirty workspace switch',async({page})=>{
  await routeChapter(page);await enter(page);
  const key=await recoveryNamespace(page);
  await page.evaluate(key=>localStorage.setItem(`ai-novel-studio:draft:${key}:e2e-chapter`,JSON.stringify({chapterId:'e2e-chapter',content:'Unsaved browser draft',baseVersion:1,updatedAt:new Date().toISOString()})),key);
  await page.locator('.tree nav button').filter({hasText:'permissions'}).click();await page.locator('.tree nav button').filter({hasText:'members'}).click();
  let navigation=0;page.on('request',request=>{if(request.url().includes('/e2e-workspace-b/navigation'))navigation++});
  await page.locator('.workspace-list__item').filter({hasText:'E2E Empty Workspace B'}).click();
  expect(navigation).toBe(0);expect(await page.evaluate(()=>localStorage.getItem('studio.scope'))).toContain('e2e-workspace-a');
  expect(await page.evaluate(key=>localStorage.getItem(`ai-novel-studio:draft:${key}:e2e-chapter`),key)).toContain('Unsaved browser draft');
});

test('production browser fails closed on persisted conflict workspace switch',async({page})=>{
  await routeChapter(page);await enter(page);
  const key=await recoveryNamespace(page);
  await page.evaluate(key=>localStorage.setItem(`ai-novel-studio:conflict:${key}:e2e-chapter`,JSON.stringify({chapterId:'e2e-chapter',local:{chapterId:'e2e-chapter',content:'Conflict draft',baseVersion:1,updatedAt:new Date().toISOString()},server:{id:'e2e-chapter',content:'Server',version:2},detectedAt:new Date().toISOString()})),key);
  await page.locator('.tree nav button').filter({hasText:'permissions'}).click();await page.locator('.tree nav button').filter({hasText:'members'}).click();
  let navigation=0;page.on('request',request=>{if(request.url().includes('/e2e-workspace-b/navigation'))navigation++});
  await page.locator('.workspace-list__item').filter({hasText:'E2E Empty Workspace B'}).click();
  expect(navigation).toBe(0);expect(await page.evaluate(()=>localStorage.getItem('studio.scope'))).toContain('e2e-workspace-a');
  expect(await page.evaluate(key=>localStorage.getItem(`ai-novel-studio:conflict:${key}:e2e-chapter`),key)).toContain('Conflict draft');
});
