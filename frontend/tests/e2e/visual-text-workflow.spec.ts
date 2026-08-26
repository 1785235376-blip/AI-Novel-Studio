import {expect,test} from '@playwright/test';

test('read-only visual text workflow is accessible, isolated and side-effect free',async({page})=>{
  const title=`只读流程验收-${Date.now()}`;
  const consoleErrors:string[]=[],pageErrors:string[]=[],networkErrors:string[]=[];
  let generationRequests=0,writeWorkflowRequests=0;
  page.on('console',message=>{if(message.type()==='error')consoleErrors.push(message.text())});
  page.on('pageerror',error=>pageErrors.push(error.message));
  page.on('request',request=>{const path=new URL(request.url()).pathname;if(path.startsWith('/api/generate/'))generationRequests++;if(path.endsWith('/visual-text-workflow')&&request.method()!=='GET')writeWorkflowRequests++});
  page.on('response',response=>{if(response.status()>=400&&!response.url().endsWith('/favicon.ico'))networkErrors.push(`${response.status()} ${new URL(response.url()).pathname}`)});
  await page.addInitScript(()=>{localStorage.setItem('studio.session','e2e-admin-session');localStorage.removeItem('studio.scope')});
  await page.goto('/');
  await page.getByRole('button',{name:/E2E|e2e/i}).first().click();
  await page.getByLabel('项目名称').fill(title);await page.getByRole('button',{name:'创建并打开'}).click();
  await expect(page.getByText(title)).toBeVisible();
  await page.getByLabel('文本模型').selectOption('deepseek:deepseek-chat');
  await page.getByRole('button',{name:'文本生成流程'}).click();
  await expect(page.getByRole('heading',{name:'文本生成流程'})).toBeVisible();
  await expect(page.getByText('只读检查')).toBeVisible();
  await expect(page.getByRole('list',{name:'文本生成流程步骤'})).toBeVisible();
  await expect(page.getByLabel('步骤 1：隐私筛选上下文')).toBeVisible();
  await expect(page.getByLabel(/步骤 2：DeepSeek/)).toBeVisible();
  await expect(page.getByLabel('步骤 3：流式生成')).toBeVisible();
  await expect(page.getByLabel('步骤 4：草稿与差异预览')).toBeVisible();
  await expect(page.getByLabel('步骤 5：显式采用')).toBeVisible();
  await expect(page.getByLabel('步骤 6：创建新修订')).toBeVisible();
  await expect(page.locator('.visual-workflow')).not.toContainText(/ActorContext|ProviderRegistry|LOCAL_ONLY|api_key|Authorization|\{"/);
  await expect(page.getByRole('button',{name:/运行|保存流程|添加节点|发布/})).toHaveCount(0);
  for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
    await page.setViewportSize(viewport);const shell=page.locator('.app-shell'),workflow=page.locator('.visual-workflow');
    const [shellBox,workflowBox]=await Promise.all([shell.boundingBox(),workflow.boundingBox()]);
    expect(shellBox).not.toBeNull();expect(workflowBox).not.toBeNull();
    expect(workflowBox!.x).toBeGreaterThanOrEqual(shellBox!.x);expect(workflowBox!.x+workflowBox!.width).toBeLessThanOrEqual(viewport.width+1);
    expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);
  }
  expect(generationRequests).toBe(0);expect(writeWorkflowRequests).toBe(0);
  expect(consoleErrors).toEqual([]);expect(pageErrors).toEqual([]);expect(networkErrors).toEqual([]);
});
