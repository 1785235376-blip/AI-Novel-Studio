import {expect,test} from '@playwright/test';

test('author selection reaches the generation request without exposing runtime profiles',async({page})=>{
  const requests:any[]=[];
  await page.addInitScript(()=>{localStorage.setItem('studio.session','model-session');localStorage.setItem('studio.scope',JSON.stringify({workspaceId:'w',projectId:'p',storylineId:'s',branchId:'b'}));});
  await page.route('**/api/**',async route=>{
    const path=new URL(route.request().url()).pathname;
    if(path.endsWith('/bootstrap'))return route.fulfill({json:{actor:{actor_id:'author',session_id:'session',client_id:'browser'},scope:{workspace_id:'w',project_id:'p',storyline_id:'s',branch_id:'b'},capabilities:{}}});
    if(path.endsWith('/text-models'))return route.fulfill({json:{items:[{provider_id:'deepseek',model_id:'deepseek-chat',display_name:'DeepSeek',available:true}]}});
    if(path.endsWith('/chapters')&&path.includes('/collaboration/'))return route.fulfill({json:{items:[{id:'c',novel_id:'p',number:1,title:'Chapter',version:1,word_count:1,status:'DRAFT'}]}});
    if(path.endsWith('/chapters/c'))return route.fulfill({json:{id:'c',novel_id:'p',number:1,title:'Chapter',content:'正文',document:{type:'doc',content:[]},version:1,word_count:1,status:'DRAFT'}});
    if(path.includes('/generate/')){requests.push(route.request().postDataJSON());return route.fulfill({status:202,json:{job_id:'j',events_url:'/events',base_chapter_version:1}})}
    if(path.endsWith('/generation/j'))return route.fulfill({json:{id:'j',status:'FAILED',output:'',error:'stop'}});
    return route.fulfill({json:{items:[]}});
  });
  await page.goto('/');
  const selector=page.getByLabel('文本模型');await expect(selector).toBeVisible();
  await expect(page.locator('.novel-ai-panel')).not.toContainText('LOCAL_ONLY');
  await selector.selectOption('deepseek:deepseek-chat');await page.getByRole('button',{name:'生成续写草稿'}).click();
  await expect.poll(()=>requests.length).toBe(1);
  expect(requests[0]).toMatchObject({provider_id:'deepseek',model_id:'deepseek-chat',profile:'LOCAL_ONLY'});
});
