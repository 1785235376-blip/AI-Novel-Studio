import {expect,test,type APIResponse,type Page} from '@playwright/test';
import {createPageQuiescer} from './r3-fixture-lifecycle';
const API='http://127.0.0.1:8047/api';
async function checked(response:APIResponse){expect(response.ok(),`${response.status()}: ${await response.text()}`).toBeTruthy();return response.json();}
async function openReview(page:Page){
  await page.getByRole('button',{name:/功能导航/}).first().click();
  const group=page.getByRole('button',{name:/^制作与分析/});
  if(await group.getAttribute('aria-expanded')!=='true')await group.click();
  await page.getByRole('button',{name:'一致性检查',exact:true}).click();await page.keyboard.press('Escape');
  await expect(page.getByRole('region',{name:'来源绑定的问题审阅',exact:true})).toBeVisible();
}
test('original continuity review persists intentional decisions, rejects stale CAS, and opens exact source history',async({page,request},info)=>{
  const quiet=createPageQuiescer(page);let nid='';const modelCalls:string[]=[];
  page.on('request',r=>{if(r.method()==='POST'&&/\/(?:generate|generation|dispatch)\//.test(r.url()))modelCalls.push(r.url());});
  info.annotations.push({type:'verification',description:'Real app.main File API, existing React shell and source owners. Synthetic text only; no business-route mocks, provider or GPU. Canon decision/recovery coverage is in mounted API and React tests.'});
  try{
    const novel=await checked(await request.post(API+'/novels',{data:{title:`Finding review synthetic ${info.testId}`}}));nid=novel.id;
    const created=await checked(await request.post(`${API}/novels/${nid}/chapters`,{data:{title:'Synthetic review source',content:'SYNTHETIC_ORIGINAL_CLOCK_SOURCE'}}));
    const chapter=await checked(await request.get(`${API}/chapters/${encodeURIComponent(created.id)}`));
    const base=`${API}/projects/${nid}/continuity`;
    const facts={events:[{id:'clock',project_id:nid,event_type:'SCENE',title:'Synthetic clock',start_time:'day-3',end_time:'day-1',evidence_ids:['synthetic-clock-evidence']}]};
    const checkedRun=await checked(await request.post(base+'/review-checks',{data:{chapter_id:chapter.id,expected_source_version:chapter.version,facts}}));
    const row=checkedRun.items[0];expect(row.status).toBe('OPEN');expect(checkedRun.model_called).toBe(false);
    await page.goto('/');await expect(page.locator('.app-shell')).toBeVisible();
    await page.locator('.novel-tree-select').filter({hasText:'Synthetic review source'}).click();await openReview(page);
    const panel=page.getByRole('region',{name:'来源绑定的问题审阅',exact:true});
    await panel.getByRole('button',{name:'审阅此问题',exact:true}).click();
    await expect(panel.getByRole('button',{name:'确认保存审阅',exact:true})).toBeDisabled();
    await panel.getByLabel('审阅理由',{exact:true}).fill('Synthetic intentional reverse chronology');
    await panel.getByRole('button',{name:'取消审阅',exact:true}).click();
    expect((await checked(await request.get(base+`/review-findings/${row.id}`))).review_version).toBe(1);
    await panel.getByRole('button',{name:'审阅此问题',exact:true}).click();
    await panel.getByLabel('审阅理由',{exact:true}).fill('Synthetic intentional reverse chronology');await panel.getByLabel('已核对来源版本和证据',{exact:true}).check();
    const saving=page.waitForResponse(r=>r.url().endsWith(`/review-findings/${row.id}/review`)&&r.request().method()==='POST');
    await panel.getByRole('button',{name:'确认保存审阅',exact:true}).click();const accepted=await checked(await saving);expect(accepted.review_version).toBe(2);expect(accepted.suppression_active).toBe(true);
    const staleRequest=await request.post(base+`/review-findings/${row.id}/review`,{data:{expected_version:1,source_digest:row.source_digest,finding_fingerprint:row.finding_fingerprint,action:'resolve',reason:'Stale synthetic client',operation_id:'stale-browser-client',confirmed:true}});
    expect(staleRequest.status()).toBe(409);
    await page.reload();await expect(page.locator('.app-shell')).toBeVisible();await page.locator('.novel-tree-select').filter({hasText:'Synthetic review source'}).click();await openReview(page);
    await expect(panel.getByText('INTENTIONAL · v2',{exact:true})).toBeVisible();
    const changed=await checked(await request.put(`${API}/chapters/${encodeURIComponent(chapter.id)}`,{data:{version:chapter.version,content:'SYNTHETIC_NEWER_CLOCK_SOURCE'}}));expect(changed.version).toBeGreaterThan(chapter.version);
    await panel.getByRole('button',{name:'刷新审阅问题',exact:true}).click();await expect(panel.getByText(/原有意设置不再生效/)).toBeVisible();
    await panel.getByRole('button',{name:`打开确切来源 v${chapter.version}`,exact:true}).click();
    await expect(panel.getByLabel('来源正文快照',{exact:true})).toHaveValue(/SYNTHETIC_ORIGINAL_CLOCK_SOURCE/);
    await panel.getByRole('button',{name:'关闭来源',exact:true}).click();await expect(panel.getByLabel('来源正文快照',{exact:true})).toHaveCount(0);
    const canon=page.getByRole('region',{name:'原始 Canon 候选审阅',exact:true});await expect(canon.getByText('没有 Canon 候选',{exact:true})).toBeVisible();
    expect((await checked(await request.get(`${API}/projects/${nid}/pending-canon/review`))).items).toEqual([]);
    for(const[width,height]of[[1366,768],[1440,900],[1920,1080]]){
      await page.setViewportSize({width,height});await page.evaluate(()=>document.fonts.ready);
      expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);
      await page.screenshot({path:info.outputPath(`findings-canon-${width}.png`),fullPage:true});
    }
    expect(modelCalls).toEqual([]);
  }finally{await quiet();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());}
});
