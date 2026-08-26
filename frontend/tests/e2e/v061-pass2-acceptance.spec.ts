import fs from 'node:fs';
import path from 'node:path';
import {expect,test} from '@playwright/test';

const sessions=JSON.parse(fs.readFileSync(path.resolve('..','.runtime','acceptance-sessions.json'),'utf8').replace(/^\uFEFF/,''));
const admin=sessions.find((item:{role:string})=>item.role==='ADMIN');
const scope={workspaceId:'acceptance-alpha',projectId:'acceptance-alpha-novel',storylineId:'acceptance-alpha-storyline',branchId:'acceptance-alpha-main'};

test('Pass 2 management and revision presentation remain safe',async({page})=>{
  const consoleErrors:string[]=[],pageErrors:string[]=[],networkErrors:string[]=[];
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())});
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('response',response=>{if(response.status()>=400)networkErrors.push(`${response.status()} ${response.url()}`)});
  await page.addInitScript(({token,value})=>{localStorage.setItem('studio.session',token);localStorage.setItem('studio.scope',JSON.stringify(value))},{token:admin.token,value:scope});
  await page.goto('/');
  await expect(page.locator('.app-shell')).toBeVisible();

  await Promise.all([
    page.waitForResponse(response=>response.url().includes('/acceptance-alpha/members')&&response.ok()),
    page.getByRole('button',{name:'团队成员'}).click(),
  ]);
  const management=page.locator('.workspace-management__main');
  await expect(management).toContainText('Acceptance Admin');
  await expect(management).toContainText('工作区管理员');
  await expect(management).not.toContainText('acceptance-admin');
  await expect(management).not.toContainText('acceptance-alpha-novel');
  await expect(management).not.toContainText('ADMIN · NOVEL');

  await page.getByRole('button',{name:'版本历史'}).click();
  const timeline=page.locator('.revision-timeline');
  await expect(timeline).toContainText('版本');
  await expect(timeline).not.toContainText('MANUAL_SAVE');
  await expect(timeline).not.toContainText('RESTORE');
  const before=await timeline.locator('button').count();
  await timeline.locator('button').filter({hasNotText:'当前'}).first().click();
  const detail=page.locator('.revision-detail');
  await expect(detail.getByRole('heading',{name:/^历史版本 \d+$/,level:3})).toBeVisible();
  await expect(detail.locator('.revision-body')).toHaveCount(2);
  await expect(detail).not.toContainText('"type": "doc"');
  await expect(detail.getByRole('button',{name:'预览并恢复此版本'})).toBeVisible();
  await detail.getByRole('button',{name:'预览并恢复此版本'}).click();
  await expect(detail).toContainText('现有历史版本不会被删除');
  await Promise.all([
    page.waitForResponse(response=>response.request().method()==='POST'&&response.url().includes('/history/')&&response.url().includes('/restore')&&response.ok()),
    page.waitForEvent('load'),
    detail.getByRole('button',{name:'恢复此版本'}).click(),
  ]);
  await expect(page.locator('.revision-timeline')).toContainText('版本');
  await expect(page.locator('.revision-timeline button')).toHaveCount(before+1);
  await page.getByRole('button',{name:'故事资料库'}).focus();
  expect(consoleErrors).toEqual([]);
  expect(pageErrors).toEqual([]);
  expect(networkErrors).toEqual([]);
});
