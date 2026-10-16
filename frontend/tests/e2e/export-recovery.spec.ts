import {expect,test} from '@playwright/test';
import {readFile} from 'node:fs/promises';

test('create, close, reopen, rediscover identical snapshot and download; isolate user and branch',async({page,context})=>{
  await page.goto('/tests/e2e/export-recovery.html');
  const creation=page.waitForResponse(response=>response.url().endsWith('/api/exports?novel_id=synthetic-project')&&response.request().method()==='POST');
  await page.getByRole('button',{name:'Fountain 剧本',exact:true}).click();
  const job=await (await creation).json();
  await expect(page.getByRole('button',{name:/^下载/})).toBeVisible();
  await expect(page.locator('.export-job')).toContainText(job.snapshot_id);
  await page.close();
  const reopened=await context.newPage();
  await reopened.goto('/tests/e2e/export-recovery.html');
  await expect(reopened.locator('.export-job')).toContainText(job.snapshot_id);
  await expect(reopened.locator('.export-job')).toContainText(job.id.slice(0,8));
  const downloading=reopened.waitForEvent('download');
  await reopened.getByRole('button',{name:/^下载/}).click();
  const file=await downloading;
  const bytes=await readFile((await file.path())!,'utf8');
  expect(bytes).toContain(job.snapshot_id);expect(bytes).toContain('THE DOOR');expect(bytes).toContain('@小明Alex');
  await reopened.getByRole('combobox',{name:'测试身份'}).selectOption('session-other');
  await expect(reopened.getByText('暂无导出记录')).toBeVisible();
  await expect(reopened.getByRole('button',{name:/^下载/})).toHaveCount(0);
  await reopened.getByRole('combobox',{name:'测试身份'}).selectOption('session-owner');
  await expect(reopened.getByRole('button',{name:/^下载/})).toBeVisible();
  await reopened.getByRole('combobox',{name:'测试分支'}).selectOption('branch-b');
  await expect(reopened.getByText('暂无导出记录')).toBeVisible();
  await expect(reopened.getByRole('button',{name:/^下载/})).toHaveCount(0);
  await reopened.getByRole('combobox',{name:'测试分支'}).selectOption('branch-a');
  await expect(reopened.getByRole('button',{name:/^下载/})).toBeVisible();
  for(const width of [1366,1440,1920]){
    await reopened.setViewportSize({width,height:900});
    expect(await reopened.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await reopened.screenshot({path:`test-results/export-recovery-${width}.png`,fullPage:true});
  }
});
