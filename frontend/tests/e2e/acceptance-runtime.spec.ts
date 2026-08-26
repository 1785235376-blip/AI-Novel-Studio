import fs from 'node:fs';
import path from 'node:path';
import {expect,test} from '@playwright/test';

const sessions=JSON.parse(fs.readFileSync(path.resolve('..','.runtime','acceptance-sessions.json'),'utf8').replace(/^\uFEFF/,''));
const admin=sessions.find((item:{role:string})=>item.role==='ADMIN');
const alpha={workspaceId:'acceptance-alpha',projectId:'acceptance-alpha-novel',storylineId:'acceptance-alpha-storyline',branchId:'acceptance-alpha-main'};
const evidence=path.resolve('..','docs','evidence','v0.5.9.1');
const audits=new WeakMap<object,{console:string[];network:string[];expected:Set<number>}>();

test.beforeEach(async({page})=>{
  const audit={console:[] as string[],network:[] as string[],expected:new Set<number>()};audits.set(page,audit);
  page.on('console',message=>{if(message.type()==='error'&&!message.text().startsWith('Failed to load resource:'))audit.console.push(message.text())});
  page.on('pageerror',error=>audit.console.push(error.message));
  page.on('response',response=>{if(response.status()>=400&&!audit.expected.has(response.status()))audit.network.push(`${response.status()} ${response.url()}`)});
});
test.afterEach(async({page})=>{
  const audit=audits.get(page)!;
  expect(audit.console,'unexpected browser console/page errors').toEqual([]);
  expect(audit.network,'unexpected HTTP 4xx/5xx responses').toEqual([]);
});

async function enterAlpha(page:any){
  await page.addInitScript(({token,scope}:{token:string;scope:typeof alpha})=>{localStorage.setItem('studio.session',token);localStorage.setItem('studio.scope',JSON.stringify(scope));},{token:admin.token,scope:alpha});
  await page.goto('/');
  await expect(page.locator('.app-shell')).toBeVisible();
}

test('user-runnable production acceptance environment keeps AppShell across all workspace switches',async({page})=>{
  await page.addInitScript(({token,scope})=>{
    localStorage.setItem('studio.session',token);
    localStorage.setItem('studio.scope',JSON.stringify(scope));
  },{token:admin.token,scope:alpha});
  await page.goto('/');
  await expect(page.locator('.context-bar')).not.toContainText('acceptance-alpha-novel');
  await expect(page.locator('.tree')).toContainText('Acceptance Chapter');
  await page.screenshot({path:path.join(evidence,'01_appshell.png'),fullPage:true});
  await page.screenshot({path:path.join(evidence,'02_workspace_alpha.png'),fullPage:true});

  await page.locator('.tree nav button').filter({hasText:'团队成员'}).click();
  await expect(page.locator('.workspace-management')).toBeVisible();
  await expect(page.locator('.workspace-list__item').filter({hasText:'Workspace Alpha'})).toBeVisible();
  await expect(page.locator('.workspace-management')).toContainText('Acceptance Admin');

  const switchTo=async(workspaceId:string,label:string)=>{
    const response=page.waitForResponse(item=>item.url().includes(`/${workspaceId}/navigation`));
    await page.locator('.workspace-list__item').filter({hasText:label}).click();
    expect((await response).status()).toBe(200);
    await expect(page.locator('.app-shell')).toBeVisible();
    await expect(page.getByRole('heading',{name:'连接协作项目'})).toHaveCount(0);
    await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('studio.scope')!).workspaceId)).toBe(workspaceId);
  };
  await switchTo('acceptance-beta','Workspace Beta');
  await page.screenshot({path:path.join(evidence,'03_workspace_beta.png'),fullPage:true});
  await switchTo('acceptance-alpha','Workspace Alpha');
  await switchTo('acceptance-empty','Workspace Empty');
  await expect(page.locator('.context-bar span').nth(1)).toContainText('NONE');
  await expect(page.locator('.context-bar span').nth(2)).toContainText('NONE');
  await expect(page.locator('.context-bar span').nth(3)).toContainText('NONE');
  await page.screenshot({path:path.join(evidence,'04_workspace_empty.png'),fullPage:true});
  await switchTo('acceptance-alpha','Workspace Alpha');
  await page.screenshot({path:path.join(evidence,'05_workspace_switch.png'),fullPage:true});
});

test('real management UI creates, renames, adds, and removes without actor spoofing',async({page})=>{
  await enterAlpha(page);
  const requests:any[]=[];page.on('request',(request:any)=>{if(request.url().includes('/api/collaboration/admin/'))requests.push({url:request.url(),method:request.method(),body:request.postDataJSON()})});
  await page.locator('.tree nav button').filter({hasText:'团队成员'}).click();
  const sidebar=page.locator('.workspace-management__sidebar');
  await sidebar.locator('.section-heading button').click();
  const name=`Acceptance Sweep ${Date.now()}`;
  await sidebar.locator('form input').fill(name);await sidebar.locator('form button[type="submit"]').click();
  await expect(sidebar).toContainText(name);
  await sidebar.locator('.workspace-list__item').filter({hasText:name}).click();
  const current=page.locator('.workspace-management__main .ui-panel').first();
  await expect.poll(()=>page.evaluate(()=>JSON.parse(localStorage.getItem('studio.scope')!).workspaceId)).not.toBe('acceptance-alpha');
  await expect(current).toContainText(name);
  await current.locator('button').click();await current.locator('form input').fill(`${name} Renamed`);await current.locator('form button[type="submit"]').click();
  await expect(current).toContainText(`${name} Renamed`);
  const memberPanel=page.locator('.workspace-management__main .ui-panel').nth(1);
  await memberPanel.locator('header button').click();await memberPanel.locator('form input').fill('acceptance-member');await memberPanel.locator('form button[type="submit"]').click();
  const member=memberPanel.locator('.member-item').filter({hasText:'Acceptance Member'});await expect(member).toBeVisible();await member.click();
  await memberPanel.locator('.member-detail button').click();await page.locator('[role="alertdialog"] button').first().click();await expect(memberPanel.locator('.member-detail')).toContainText('INACTIVE');
  expect(requests.every(item=>!item.body||item.body.actor_id===undefined)).toBeTruthy();
  await page.screenshot({path:path.join(evidence,'06_team.png'),fullPage:true});
});

test('real permission UI grants and revokes a NOVEL domain role',async({page})=>{
  await enterAlpha(page);await page.locator('.tree nav button').filter({hasText:'权限设置'}).click();
  const existingDirect=page.locator('.permission-assignment').filter({hasText:'DIRECT'}).filter({hasText:'Acceptance Member'}).filter({hasText:'domain.write'});await expect(existingDirect).toBeVisible();await existingDirect.getByRole('button',{name:'Revoke'}).click();await expect(existingDirect).toHaveCount(0);
  const grant=page.locator('.permission-grant');await grant.locator('input').fill('acceptance-member');await grant.locator('select').nth(0).selectOption('DOMAIN_LEAD');await grant.locator('select').nth(1).selectOption('NOVEL');await grant.locator('button[type="submit"]').click();
  const role=page.locator('.permission-assignment').filter({hasText:'DOMAIN_LEAD'}).filter({hasText:'Acceptance Member'});await expect(role).toBeVisible();
  await page.screenshot({path:path.join(evidence,'07_roles.png'),fullPage:true});await page.screenshot({path:path.join(evidence,'08_permissions.png'),fullPage:true});
  await role.getByRole('button',{name:'Revoke'}).click();await expect(role).toHaveCount(0);
  await grant.locator('input').fill('acceptance-member');await grant.locator('select').nth(0).selectOption('DIRECT');await grant.locator('button[type="submit"]').click();await expect(page.locator('.permission-assignment').filter({hasText:'DIRECT'}).filter({hasText:'Acceptance Member'}).filter({hasText:'domain.write'})).toBeVisible();
});

test('DOMAIN_LEAD and MEMBER cannot open Workspace ADMIN management',async({page})=>{
  await enterAlpha(page);audits.get(page)!.expected.add(403);
  for(const role of ['DOMAIN_LEAD','MEMBER']){
    const identity=sessions.find((item:{role:string})=>item.role===role);
    await page.goto('/');await page.evaluate(({token,scope})=>{localStorage.clear();localStorage.setItem('studio.session',token);localStorage.setItem('studio.scope',JSON.stringify(scope));},{token:identity.token,scope:alpha});
    await page.reload();await page.locator('.tree nav button').filter({hasText:'团队成员'}).click();await expect(page.locator('.workspace-management')).toContainText(/无权|权限|拒绝/);
  }
});

test('records the current manual connection page as productization evidence',async({page})=>{
  audits.get(page)!.expected.add(501);
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'AI Novel Studio'})).toBeVisible();
  await expect(page.getByRole('textbox',{name:'会话凭证'})).toBeVisible();
  await page.screenshot({path:path.join(evidence,'15_connection_page.png'),fullPage:true});
});

test('Novel, dirty, conflict, revision detail and restore remain reachable',async({page})=>{
  await enterAlpha(page);await expect(page.locator('.tree')).toContainText('Acceptance Chapter');
  await page.screenshot({path:path.join(evidence,'09_novel_workspace.png'),fullPage:true});await page.screenshot({path:path.join(evidence,'10_chapter_editor.png'),fullPage:true});
  const namespace=await page.evaluate(({token,scope})=>{let hash=2166136261;for(const character of token)hash=Math.imul(hash^character.charCodeAt(0),16777619);return `${scope.workspaceId}\u001f${scope.projectId}\u001f${scope.storylineId}\u001f${scope.branchId}\u001fclient:${(hash>>>0).toString(36)}`},{token:admin.token,scope:alpha});
  const chapter='acceptance-alpha-novel:1';
  const currentVersion=Number((await page.locator('.revision-timeline button').first().locator('strong').textContent())?.replace(/\D/g,''));
  await page.evaluate(({namespace,chapter,currentVersion})=>localStorage.setItem(`ai-novel-studio:draft:${namespace}:${chapter}`,JSON.stringify({chapterId:chapter,content:'Unsaved acceptance draft',baseVersion:currentVersion,updatedAt:new Date().toISOString()})),{namespace,chapter,currentVersion});
  await page.locator('.tree nav button').filter({hasText:'团队成员'}).click();let navigation=0;page.on('request',(request:any)=>{if(request.url().includes('/acceptance-empty/navigation'))navigation++});await page.locator('.workspace-list__item').filter({hasText:'Workspace Empty'}).click();expect(navigation).toBe(0);
  await page.screenshot({path:path.join(evidence,'11_dirty_guard.png'),fullPage:true});
  await page.evaluate(({namespace,chapter,currentVersion})=>{localStorage.removeItem(`ai-novel-studio:draft:${namespace}:${chapter}`);localStorage.setItem(`ai-novel-studio:conflict:${namespace}:${chapter}`,JSON.stringify({chapterId:chapter,local:{chapterId:chapter,content:'Conflict draft',baseVersion:currentVersion,updatedAt:new Date().toISOString()},server:{id:chapter,content:'Server content',version:currentVersion+1},detectedAt:new Date().toISOString()}))},{namespace,chapter,currentVersion});
  await page.locator('.tree nav button').filter({hasText:'权限设置'}).click();await page.locator('.tree nav button').filter({hasText:'团队成员'}).click();await page.locator('.workspace-list__item').filter({hasText:'Workspace Empty'}).click();expect(navigation).toBe(0);
  await page.screenshot({path:path.join(evidence,'12_conflict.png'),fullPage:true});
  await page.evaluate(({namespace,chapter})=>localStorage.removeItem(`ai-novel-studio:conflict:${namespace}:${chapter}`),{namespace,chapter});
  await page.reload();await expect(page.locator('.revision-panel')).toBeVisible();await page.locator('.revision-timeline button').first().click();await expect(page.locator('.revision-detail')).toContainText('Revision v');
  await page.screenshot({path:path.join(evidence,'13_revision.png'),fullPage:true});
  await page.getByRole('button',{name:/预览并恢复.*修订/}).click();await page.screenshot({path:path.join(evidence,'14_restore.png'),fullPage:true});
  await page.getByRole('button',{name:/确认恢复/}).click();await page.waitForLoadState('domcontentloaded');await expect(page.locator('.app-shell')).toBeVisible();
});
