import {expect,test} from '@playwright/test';

test('selected route readiness is visible in the author panel without runtime side effects',async({page})=>{
  const title=`路线就绪提示-${Date.now()}`;
  const consoleErrors:string[]=[],pageErrors:string[]=[],networkErrors:string[]=[];
  let providerRequests=0,generationRequests=0,diagnosticWrites=0;
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())});
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('request',request=>{const url=new URL(request.url()),path=url.pathname;if(url.hostname.includes('deepseek.com'))providerRequests++;if(path.startsWith('/api/generate/'))generationRequests++;if(path.endsWith('/text-runtime-diagnostics')&&request.method()!=='GET')diagnosticWrites++});
  page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))networkErrors.push(`${response.status()} ${new URL(response.url()).pathname}`)});
  await page.addInitScript(()=>{localStorage.setItem('studio.session','e2e-admin-session');localStorage.removeItem('studio.scope')});
  await page.goto('/');
  await page.getByRole('button',{name:/E2E|e2e/i}).first().click();
  await page.getByLabel('项目名称').fill(title);await page.getByRole('button',{name:'创建并打开'}).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByLabel('文本模型').selectOption('deepseek:deepseek-chat');
  const readiness=page.locator('.novel-route-readiness');
  await expect(readiness.getByText('所选路线状态')).toBeVisible();
  await expect(readiness.getByText('可用')).toBeVisible();
  await expect(readiness.getByText('可以返回写作面板开始生成。')).toBeVisible();
  await readiness.getByRole('button',{name:'查看详细诊断'}).click();
  await expect(page.getByRole('heading',{name:'模型运行诊断'})).toBeVisible();
  await expect(page.getByText('deepseek',{exact:true})).toBeVisible();
  for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
    await page.setViewportSize(viewport);
    await expect(readiness.getByText('所选路线状态')).toBeVisible();
    const shellBox=await page.locator('.app-shell').boundingBox();expect(shellBox).not.toBeNull();
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  }
  expect(providerRequests).toBe(0);expect(generationRequests).toBe(0);expect(diagnosticWrites).toBe(0);
  expect(consoleErrors).toEqual([]);expect(pageErrors).toEqual([]);expect(networkErrors).toEqual([]);
});
