import {expect,test} from '@playwright/test';

test('production novel flow needs no internal ids',async({page})=>{
  const title=`浏览器验收小说-${Date.now()}`;
  await page.addInitScript(()=>{localStorage.setItem('studio.session','e2e-admin-session');localStorage.removeItem('studio.scope')});
  await page.goto('/');
  await expect(page.getByText('选择工作区和小说项目，继续创作。')).toBeVisible();
  await expect(page.getByText(/workspaceId|projectId|storylineId|branchId/)).toHaveCount(0);
  await page.getByRole('button',{name:/E2E|e2e/i}).first().click();
  await page.getByLabel('项目名称').fill(title);
  await page.getByRole('button',{name:'创建并打开'}).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByRole('button',{name:'新建章节'}).click();
  await page.getByLabel('章节标题').fill('第一章 雨夜来信');
  await page.getByRole('button',{name:'创建章节',exact:true}).click();
  await expect(page.getByRole('heading',{name:'第一章 雨夜来信'})).toBeVisible();
  const editor=page.locator('.ProseMirror');
  await editor.click();
  await editor.fill('雨落在旧城的石板路上。林岚拆开了那封没有署名的信。');
  await expect(page.locator('.editorbar small')).toContainText('已保存',{timeout:15_000});
  await page.reload();
  await expect(editor).toContainText('雨落在旧城的石板路上');
  await page.getByRole('button',{name:'故事资料库'}).click();
  await expect(page.getByRole('heading',{name:'故事资料库'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'AI 写作助手'})).toBeVisible();
  await expect(page.getByText(/workspaceId|projectId|storylineId|branchId|actorId/)).toHaveCount(0);
});
