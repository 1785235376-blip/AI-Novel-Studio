import {test,expect} from '@playwright/test';
import fs from 'node:fs';
import path from 'node:path';

async function feature(page:any,name:string){
 const menu=page.getByRole('button',{name:/功能导航/}).first();
 // reload() resolves before React mounts; count() does not wait and can skip
 // opening the navigation entirely. Wait for the existing accessible control.
 await expect(menu).toBeVisible();
 await menu.click();
 await page.getByRole('button',{name,exact:true}).first().click();
}

test('R2 real File API: save/reopen, reviewed plans, anchored comments and immutable export recovery',async({page,request},info)=>{
 test.info().annotations.push({type:'verification',description:'Real File/backend/browser; synthetic manuscript; no real providers'});
 await page.goto('/');
 const title=`R2 合成验收 ${Date.now()}`;
 await page.getByPlaceholder('小说名称').fill(title);
 const created=page.waitForResponse(r=>r.url().endsWith('/api/novels')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'创建小说',exact:true}).click();
 const novel=(await (await created).json());
 await page.getByRole('button',{name:'新建章节',exact:true}).click();
 await page.getByLabel('章节标题').fill('第一章 合成海港');
 await page.getByRole('button',{name:'创建章节',exact:true}).click();
 const editor=page.locator('.ProseMirror');
 await editor.fill('Alice said hello. 林默说道：“秘密会解开。”他们来到云港。');
 await page.getByRole('button',{name:'保存',exact:true}).click();
 await expect(page.locator('.editorbar')).toContainText('已保存');
 await page.reload();await expect(editor).toContainText('Alice said hello');
 // Real browser Draft/Diff/Accept and revision restore, with explicitly labeled mock execution.
 const beforeWriting=await (await request.get(`http://127.0.0.1:8015/api/novels/${novel.id}/chapters`)).json();
 const writingChapter=await (await request.get(`http://127.0.0.1:8015/api/chapters/${beforeWriting[0].id}`)).json();
 // Exercise the actual StrictMode root's first post-reload history request,
 // before a later version change can mask an initial observer replay bug.
 await expect(page.locator('.revision-timeline')).toContainText(`版本 ${writingChapter.version-1}`);
 await page.getByRole('combobox',{name:/文本模型/}).first().selectOption('deepseek:deepseek-chat');
 await expect(page.locator('.novel-ai-status [role="status"]')).toContainText(/DeepSeek Chat.*模拟测试/);
 await editor.click();await editor.press('Control+A');
 await page.getByRole('tab',{name:'改写',exact:true}).click();
 await page.getByRole('button',{name:'生成改写草稿',exact:true}).click();
 const draft=page.locator('.novel-draft-review');
 await expect(draft.getByRole('button',{name:'采用草稿',exact:true})).toBeEnabled();
 expect((await (await request.get(`http://127.0.0.1:8015/api/chapters/${writingChapter.id}`)).json()).version).toBe(writingChapter.version);
 await draft.getByRole('tab',{name:'差异',exact:true}).click();await expect(draft.locator('.novel-diff')).toBeVisible();
 await draft.getByRole('button',{name:'采用草稿',exact:true}).click();
 await expect(page.locator('.novel-draft-review')).toHaveCount(0);
 await feature(page,'版本历史');
 await page.locator('.revision-timeline button').filter({has:page.getByText(`版本 ${writingChapter.version}`,{exact:true})}).click();
 await page.getByRole('button',{name:'预览并恢复此版本',exact:true}).click();
 await page.getByRole('button',{name:'恢复此版本',exact:true}).click();
 await expect(editor).toContainText('Alice said hello');

 await feature(page,'创作方案与风格');
 await page.getByLabel('名称',{exact:true}).fill('简练风格');
 await page.getByLabel(/可复用风格指令/).fill('使用短句，保持人称一致。');
 await page.getByRole('button',{name:'保存草稿',exact:true}).click();
 await page.getByRole('button',{name:'审核通过',exact:true}).click();
 await expect(page.getByText('已审核 · v2')).toBeVisible();
 await page.getByRole('button',{name:'用于写作',exact:true}).click();
 await page.getByRole('tab',{name:'评论与审核',exact:true}).click();
 await page.getByLabel('评论内容').fill('请核对本章人物动机。');
 await page.getByRole('button',{name:'保存评论',exact:true}).click();
 await expect(page.getByText('请核对本章人物动机。',{exact:true})).toBeVisible();
 await page.getByRole('button',{name:'标记已解决',exact:true}).click();
 await page.getByRole('button',{name:'重新打开',exact:true}).click();
 await expect(page.getByText('待处理',{exact:true})).toBeVisible();
 const chapters=await (await request.get(`http://127.0.0.1:8015/api/novels/${novel.id}/chapters`)).json();
 const chapter=await (await request.get(`http://127.0.0.1:8015/api/chapters/${chapters[0].id}`)).json();
 await request.put(`http://127.0.0.1:8015/api/chapters/${chapter.id}`,{data:{content:'新版本正文，评论锚点应标为过期。',version:chapter.version}});
 await page.getByRole('button',{name:'刷新记录',exact:true}).click();
 await expect(page.getByText('来源已更新，请重新核对',{exact:true})).toBeVisible();
 // A second client changed the server version; preserve both sides and resolve explicitly.
 await editor.fill('本地未提交内容，必须保留。');
 await page.getByRole('button',{name:'保存',exact:true}).click();
 const conflict=page.getByRole('dialog');await expect(conflict).toBeVisible();
 await expect(conflict).toContainText('本地未提交内容');await expect(conflict).toContainText('新版本正文');
 await conflict.getByRole('textbox',{name:'手工解决草稿'}).fill('新版本正文，已与本地未提交内容合并。');
 await conflict.getByRole('button',{name:'应用手工解决并保存'}).click();
 await expect(conflict).toHaveCount(0);await expect(editor).toContainText('已与本地未提交内容合并');

 await feature(page,'导出中心');
 const exported=page.waitForResponse(r=>r.url().includes('/api/exports?')&&r.request().method()==='POST');
 await page.getByRole('button',{name:'TXT 小说',exact:true}).click();
 const job=await (await exported).json();
 await expect(page.getByRole('button',{name:/^下载 /})).toBeVisible();
 await page.reload();await feature(page,'导出中心');
 const history=page.locator('.export-history');
 await expect(history).toContainText(job.id.slice(0,8));
 await history.getByRole('button').filter({hasText:job.id.slice(0,8)}).click();
 await expect(page.locator('.export-job')).toContainText(job.snapshot_id);
 const download=page.waitForEvent('download');await page.getByRole('button',{name:/^下载 /}).click();
 const file=await download;expect(file.suggestedFilename()).toMatch(/\.txt$/);
 const downloaded=await file.path();expect(downloaded).toBeTruthy();expect(fs.readFileSync(downloaded!,'utf8')).toContain('新版本正文');
 const screenshots=process.env.CI_RECEIPTS?path.join(process.env.CI_RECEIPTS,'screenshots'):info.outputPath('screenshots');fs.mkdirSync(screenshots,{recursive:true});
 for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){
  await page.setViewportSize({width,height});
  const goal=page.locator('.writing-goal-panel');
  await expect(goal).toBeVisible();
  const geometry=await goal.evaluate(panel=>{
   const box=(element:Element|Range)=>{const r=element.getBoundingClientRect();return {left:r.left,right:r.right,top:r.top,bottom:r.bottom,width:r.width,height:r.height};};
   const fields=Array.from(panel.querySelectorAll(':scope > label')).map(label=>{
    const text=Array.from(label.childNodes).find(node=>node.nodeType===Node.TEXT_NODE)!;
    const range=document.createRange();range.selectNodeContents(text);
    return {name:text.textContent?.trim(),label:box(label),text:box(range),input:box(label.querySelector('input')!)};
   });
   return {panel:box(panel),fields,button:box(panel.querySelector('button')!),clientWidth:panel.clientWidth,scrollWidth:panel.scrollWidth};
  });
  expect(geometry.fields.map(field=>field.name)).toEqual(['目标字数','目标章节','截止日期']);
  expect(geometry.scrollWidth).toBeLessThanOrEqual(geometry.clientWidth+1);
  for(const [index,field] of geometry.fields.entries()){
   for(const rect of [field.label,field.text,field.input]){
    expect(rect.left).toBeGreaterThanOrEqual(geometry.panel.left-1);
    expect(rect.right).toBeLessThanOrEqual(geometry.panel.right+1);
    expect(rect.top).toBeGreaterThanOrEqual(geometry.panel.top-1);
    expect(rect.bottom).toBeLessThanOrEqual(geometry.panel.bottom+1);
    expect(rect.width).toBeGreaterThan(0);expect(rect.height).toBeGreaterThan(0);
   }
   expect(field.input.top).toBeGreaterThanOrEqual(field.text.bottom);
   expect(Math.abs(field.input.width-field.label.width)).toBeLessThanOrEqual(1);
   if(index)expect(field.label.top).toBeGreaterThanOrEqual(geometry.fields[index-1].input.bottom);
  }
  expect(geometry.button.top).toBeGreaterThanOrEqual(geometry.fields[2].input.bottom);
  expect(geometry.button.right).toBeLessThanOrEqual(geometry.panel.right+1);
  await page.screenshot({path:path.join(screenshots,`export-recovery-${width}x${height}.png`),fullPage:true});
 }
});

test('R2 actual backend Draft Accept is explicit and repeat-safe, with synthetic mock output',async({request})=>{
 test.info().annotations.push({type:'verification',description:'MOCK_ONLY model, real API/persistence; no paid provider'});
 const novel=await (await request.post('http://127.0.0.1:8015/api/novels',{data:{title:'R2 Draft Accept fixture'}})).json();
 const createdChapter=await (await request.post(`http://127.0.0.1:8015/api/novels/${novel.id}/chapters`,{data:{title:'合成草稿',content:'这是原文。'}})).json();
 const chapter=await (await request.get(`http://127.0.0.1:8015/api/chapters/${createdChapter.id}`)).json();
 const job=await (await request.post('http://127.0.0.1:8015/api/generate/rewrite',{data:{novel_id:novel.id,chapter_id:chapter.id,source:'这是原文。',profile:'LOCAL_ONLY',instruction:'改写合成句子'}})).json();
 await expect.poll(async()=> (await (await request.get(`http://127.0.0.1:8015/api/generation/${job.job_id}`)).json()).status).toBe('COMPLETED');
 const before=await (await request.get(`http://127.0.0.1:8015/api/chapters/${chapter.id}`)).json();expect(before.version).toBe(chapter.version);
 const accepted=await request.post(`http://127.0.0.1:8015/api/generation/${job.job_id}/accept`,{data:{expected_version:chapter.version}});expect(accepted.ok()).toBeTruthy();
 const after=await (await request.get(`http://127.0.0.1:8015/api/chapters/${chapter.id}`)).json();expect(after.version).toBeGreaterThan(before.version);
 await request.post(`http://127.0.0.1:8015/api/generation/${job.job_id}/accept`,{data:{expected_version:chapter.version}});
 expect((await (await request.get(`http://127.0.0.1:8015/api/chapters/${chapter.id}`)).json()).version).toBe(after.version);
});
