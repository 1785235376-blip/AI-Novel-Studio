import {expect,test} from '@playwright/test';

test('selected text route diagnostics are read-only, accessible and side-effect free',async({page})=>{
  const title=`运行诊断验收-${Date.now()}`;
  const consoleErrors:string[]=[],pageErrors:string[]=[],networkErrors:string[]=[];
  let providerFacingRequests=0,generationRequests=0,diagnosticWrites=0;
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())});
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('request',request=>{
    const url=new URL(request.url()),path=url.pathname;
    if(path.startsWith('/api/generate/'))generationRequests++;
    if(path.endsWith('/text-runtime-diagnostics')&&request.method()!=='GET')diagnosticWrites++;
    if(url.hostname.includes('deepseek.com'))providerFacingRequests++;
  });
  page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))networkErrors.push(`${response.status()} ${new URL(response.url()).pathname}`)});
  await page.addInitScript(()=>{localStorage.setItem('studio.session','e2e-admin-session');localStorage.removeItem('studio.scope')});
  await page.goto('/');
  await page.getByRole('button',{name:/E2E|e2e/i}).first().click();
  await page.getByLabel('项目名称').fill(title);await page.getByRole('button',{name:'创建并打开'}).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByLabel('文本模型').selectOption('deepseek:deepseek-chat');
  await page.getByRole('button',{name:'模型运行诊断'}).click();
  await expect(page.getByRole('heading',{name:'模型运行诊断'})).toBeVisible();
  await expect(page.getByRole('heading',{name:'可用'})).toBeVisible();
  await expect(page.getByText('deepseek',{exact:true})).toBeVisible();
  await expect(page.getByText('deepseek-chat',{exact:true})).toBeVisible();
  await expect(page.getByText('流式输出')).toBeVisible();
  await expect(page.locator('.runtime-diagnostics')).not.toContainText(/api_key|Authorization|credential|prompt|ActorContext|ProviderRegistry/);
  await expect(page.locator('.runtime-diagnostics').getByRole('button',{name:/配置|修复|运行|切换路线|保存|探测/})).toHaveCount(0);
  for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
    await page.setViewportSize(viewport);
    const shell=page.locator('.app-shell'),surface=page.locator('.runtime-diagnostics');
    const [shellBox,surfaceBox]=await Promise.all([shell.boundingBox(),surface.boundingBox()]);
    expect(shellBox).not.toBeNull();expect(surfaceBox).not.toBeNull();
    expect(surfaceBox!.x).toBeGreaterThanOrEqual(shellBox!.x);expect(surfaceBox!.x+surfaceBox!.width).toBeLessThanOrEqual(viewport.width+1);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
    await expect(page.getByText('建议操作')).toBeVisible();
  }
  expect(providerFacingRequests).toBe(0);expect(generationRequests).toBe(0);expect(diagnosticWrites).toBe(0);
  expect(consoleErrors).toEqual([]);expect(pageErrors).toEqual([]);expect(networkErrors).toEqual([]);
});
