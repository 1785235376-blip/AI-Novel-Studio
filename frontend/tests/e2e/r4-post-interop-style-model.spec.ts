import { expect, test, type APIResponse, type Page } from '@playwright/test';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API='http://127.0.0.1:8022/api', UI='http://127.0.0.1:5182';
const headers={'X-Session-Token':'r4-broker-test-session'};
async function body(response:APIResponse){expect(response.ok(),`HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();return response.json();}
async function tools(page:Page){
  await page.getByRole('button',{name:/功能导航/}).first().click(); const group=page.getByRole('button',{name:/^Experimental/});
  if(await group.getAttribute('aria-expanded')!=='true')await group.click();
  await page.getByRole('button',{name:'实验工作台',exact:true}).click(); await page.keyboard.press('Escape');
  await page.getByRole('navigation',{name:'实验功能'}).getByRole('button',{name:'风格档案',exact:true}).click();
}
test('registered Style opinions use exact selected ranges, explicit consent, original job recovery and review-only annotations',async({page,request},info)=>{
  const quiesce=createPageQuiescer(page);let nid='',jobId='';
  info.annotations.push({type:'verification',description:'Real React + production File/AuthorPreparer/Broker/JobManager/style_analyses. Explicit synthetic protocol. No response mocks, paid API or real model claim. Hosted Chromium required; local platform block not retried.'});
  try{
    await page.setExtraHTTPHeaders(headers);await page.goto(UI);await page.getByPlaceholder('小说名称').fill('A02 explicit synthetic Style opinions');
    const creating=page.waitForResponse(r=>r.url().endsWith('/api/novels')&&r.request().method()==='POST');await page.getByRole('button',{name:'创建小说',exact:true}).click();nid=(await body(await creating)).id;
    const base=`${API}/novels/${nid}/experimental`,selected='  雨水敲着窗沿，她停下来听了一会儿。';const content=`EXCLUDED_PRIVATE_OPENING\n${selected}\nEXCLUDED_PRIVATE_ENDING`;
    const created=await body(await request.post(`${API}/novels/${nid}/chapters`,{headers,data:{title:'合成雨声',content}}));
    const chapter=await body(await request.get(`${API}/chapters/${created.id}`,{headers}));
    const profile=await body(await request.post(`${base}/style-analysis/profiles`,{headers,data:{title:'合成克制文风',instructions:'保留具体动作与停顿。',chapter_ids:[chapter.id]}}));
    const start=Array.from(content.slice(0,content.indexOf(selected))).length,end=start+Array.from(selected).length;
    const analysis=await body(await request.post(`${base}/style-analysis/analyses`,{headers,data:{style_id:profile.id,expected_style_version:1,language:'zh',samples:[{chapter_id:chapter.id,expected_version:chapter.version,start,end}]}}));
    const metrics=analysis.metrics;await tools(page);
    const panel=page.getByRole('region',{name:'文风分析与档案',exact:true}),model=panel.getByRole('region',{name:`文风模型意见 ${analysis.id}`,exact:true});
    await expect(panel.getByText('Deterministic Metric · 确定性测量',{exact:true})).toBeVisible();
    await model.getByRole('button',{name:'查看文风解读本地模型',exact:true}).click();
    const catalog=await body(await request.get(`${base}/style-analysis/model/catalog`,{headers}));const route=catalog.routes.find((r:any)=>r.provider_id==='mock');expect(route.synthetic).toBe(true);
    await model.getByLabel(`文风解读模型 ${analysis.id}`,{exact:true}).selectOption(route.route_id);
    const preparing=page.waitForResponse(r=>r.url().endsWith(`/analyses/${analysis.id}/model/preview`)&&r.request().method()==='POST');await model.getByRole('button',{name:'准备准确文风模型预览',exact:true}).click();
    const prepared=await body(await preparing),preview=prepared.model_preview;
    expect(preview.request.context).toEqual({});expect(JSON.stringify(preview)).not.toContain('EXCLUDED_PRIVATE_OPENING');expect(JSON.stringify(preview)).not.toContain('EXCLUDED_PRIVATE_ENDING');
    const exact=JSON.parse(preview.author.instruction.split('STYLE_ANALYSIS_OPINIONS_V1\n')[1]);expect(exact.samples[0].fragments[0].quote).toBe(selected);
    await expect(model.getByLabel(`准确文风模型请求 ${analysis.id}`,{exact:true})).toHaveValue(JSON.stringify(preview.request,null,2));
    await expect(model.getByRole('button',{name:'明确发送此次文风解读',exact:true})).toBeDisabled();expect((await body(await request.get(`${base}/model-broker/history`,{headers}))).ledger).toHaveLength(0);
    for(const[width,height]of[[1366,768],[1440,900],[1920,1080]]){await page.setViewportSize({width,height});await page.evaluate(()=>document.fonts.ready);await model.scrollIntoViewIfNeeded();expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`style-model-preview-${width}.png`)});}
    await model.getByLabel('已核对文风原文范围、档案、模型与零费用预占',{exact:true}).check();
    const sending=page.waitForResponse(r=>r.url().endsWith(`/analyses/${analysis.id}/model/dispatch`)&&r.request().method()==='POST');await model.getByRole('button',{name:'明确发送此次文风解读',exact:true}).click();
    const running=await body(await sending);jobId=running.model_execution.job_id;
    await expect.poll(async()=>(await body(await request.get(`${base}/model-broker/jobs/${running.model_execution.reservation_id}`,{headers}))).ledger.status,{timeout:90000}).toBe('SETTLED');
    const refreshing=page.waitForResponse(r=>r.url().endsWith(`/analyses/${analysis.id}/model/refresh`)&&r.request().method()==='POST');await model.getByRole('button',{name:'查询原任务并核对文风证据',exact:true}).click();
    const result=await body(await refreshing);expect(result.metrics).toEqual(metrics);expect(result.model_execution.status).toBe('COMPLETED');expect(result.model_assessments).toHaveLength(1);
    const opinion=result.model_assessments[0];expect(opinion.origin).toBe('MODEL_DERIVED');expect(opinion.quality_verification).toBe('SYNTHETIC_PROTOCOL_ONLY');
    await model.getByLabel(`文风意见审核理由 ${opinion.id}`,{exact:true}).fill('仅验证合成协议，保留风格档案与正文。');await model.getByRole('button',{name:'忽略此文风意见',exact:true}).click();
    await expect(model.getByRole('region',{name:`文风意见 ${opinion.id}`,exact:true})).toContainText('IGNORED');
    expect((await request.post(`${API}/generation/${jobId}/accept`,{headers,data:{}})).status()).toBe(409);expect((await body(await request.get(`${API}/chapters/${chapter.id}`,{headers}))).content).toBe(content);
    const styles=await body(await request.get(`${base}/style-analysis/catalog`,{headers}));expect(styles.styles[0].version).toBe(profile.version);expect(styles.styles[0].instructions).toBe(profile.instructions);
    await quiesce.drain();await page.reload();await tools(page);await expect(model).toContainText(jobId);expect((await body(await request.get(`${base}/model-broker/history`,{headers}))).ledger).toHaveLength(1);
    await body(await request.put(`${API}/chapters/${chapter.id}`,{headers,data:{version:chapter.version,content:'新的合成正文，旧文风意见应隐藏。'}}));
    await panel.getByRole('button',{name:'刷新风格与来源（保留输入）',exact:true}).click();await expect(panel.getByText('旧来源的派生指标已隐藏。核对最新章节与档案版本，再重新选择样本创建报告。',{exact:true})).toBeVisible();
    await expect(model.getByLabel(`准确文风模型请求 ${analysis.id}`,{exact:true})).toHaveCount(0);await expect(model.getByRole('region',{name:`文风意见 ${opinion.id}`,exact:true})).toHaveCount(0);
  }finally{
    if(!page.isClosed()&&info.status!==info.expectedStatus)await page.screenshot({path:info.outputPath('style-model-failure.png'),fullPage:true}).catch(()=>{});
    if(jobId)await request.post(`${API}/generation/${jobId}/cancel`,{headers}).catch(()=>{});await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`,{headers})).status());
  }
});
