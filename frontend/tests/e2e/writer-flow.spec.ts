import {expect,test} from '@playwright/test';

test('current PostgreSQL writer journey with mock generation',async({page,request})=>{
  const title=`E2E Novel ${Date.now()}`,initial='The captain opened the rusted door.',autosaved=' A cold wind crossed the deck.';let novelId='';
  const apiResponses:Array<{url:string;status:number}>=[];page.on('response',response=>{if(response.url().includes('/api/'))apiResponses.push({url:response.url(),status:response.status()})});
  await page.goto('/');await expect(page.getByRole('heading',{name:'本机作品'})).toBeVisible();
  const health=await request.get('http://127.0.0.1:8000/api/health');expect(health.ok()).toBeTruthy();expect((await health.json()).storage).toBe('postgres');
  await page.getByPlaceholder('小说名称').fill(title);const novelCreated=page.waitForResponse(r=>r.url().endsWith('/api/novels')&&r.request().method()==='POST');await page.getByRole('button',{name:'创建小说'}).click();novelId=(await (await novelCreated).json()).id;await expect(page.getByText('AI Novel Studio')).toBeVisible();
  const chapterCreated=page.waitForResponse(r=>r.url().includes(`/api/novels/${novelId}/chapters`)&&r.request().method()==='POST');await page.getByRole('button',{name:'新建章节'}).click();await page.getByLabel('章节标题').fill('第一章');await page.getByRole('button',{name:'创建章节',exact:true}).click();await chapterCreated;await expect(page.getByRole('heading',{name:'第一章'})).toBeVisible();
  const editor=page.locator('.ProseMirror');await editor.click();await editor.fill(initial);await page.getByRole('button',{name:'保存',exact:true}).click();await expect(page.locator('.editorbar small')).toContainText('已保存');await page.reload();await expect(editor).toContainText(initial);
  await editor.click();await editor.press('End');await editor.type(autosaved);await expect(page.locator('.editorbar small')).toContainText('已保存',{timeout:10_000});await page.reload();await expect(editor).toContainText(initial+autosaved);
  await editor.click();await editor.press('Control+A');await page.getByRole('tab',{name:'改写'}).click();await page.getByRole('button',{name:'生成改写草稿'}).click();await expect(page.locator('.novel-draft-review')).toContainText('等待确认',{timeout:20_000});await page.getByRole('button',{name:'采用草稿'}).click();await expect(page.locator('.novel-draft-review')).toHaveCount(0);
  await page.getByRole('button',{name:'版本历史',exact:true}).click();await expect(page.locator('.revision-panel')).toContainText('修订历史');await expect(page.locator('.revision-timeline button')).not.toHaveCount(0);
  expect(apiResponses.filter(item=>!item.url.includes('/api/jobs/')).every(item=>item.status<400)).toBeTruthy();const deleted=await request.delete(`http://127.0.0.1:8000/api/novels/${novelId}`);expect(deleted.ok()).toBeTruthy();
});
