import {expect,test,type APIResponse,type Page} from '@playwright/test';
import {createPageQuiescer} from './r3-fixture-lifecycle';
const API=process.env.R4_API_URL||'http://127.0.0.1:8019/api';
async function checked(response:APIResponse):Promise<any>{expect(response.ok(),`HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();return response.json();}
async function workbench(page:Page,label:string){
 await page.getByRole('button',{name:/功能导航/}).first().click();const group=page.getByRole('button',{name:/^Experimental/});
 if(await group.getAttribute('aria-expanded')!=='true')await group.click();
 await page.getByRole('button',{name:'实验工作台',exact:true}).click();await page.keyboard.press('Escape');
 await page.getByRole('navigation',{name:'实验功能'}).getByRole('button',{name:label,exact:true}).click();
}
const doc=(text:string)=>({type:'doc',content:[{type:'paragraph',content:[{type:'text',text}]}]});

test('Post-interop A04/A05 scene boundaries use original planning scenes and hide later knowledge',async({page,request},info)=>{
 const quiesce=createPageQuiescer(page);let nid='';const generations:string[]=[];
 page.on('request',r=>{if(r.method()==='POST'&&/author-context\/generate/.test(r.url()))generations.push(r.url());});
 try{
  const novel=await checked(await request.post(`${API}/novels`,{data:{title:'Scene mind continuation synthetic'}}));nid=novel.id;
  const prior=await checked(await request.post(`${API}/novels/${nid}/chapters`,{data:{title:'前章',content:'世界规则已存在。'}}));
  const chapter=await checked(await request.post(`${API}/novels/${nid}/chapters`,{data:{title:'本章两个场景',content:'先询问，再发现。'}}));
  for(const[id,name]of[['alice','阿澄'],['bob','沈墨']])await checked(await request.put(`${API}/novels/${nid}/characters/${id}`,{data:{name}}));
  await checked(await request.put(`${API}/novels/${nid}/locations/city`,{data:{name:'月港'}}));
  const base=`${API}/novels/${nid}/experimental`;
  const graph=await checked(await request.post(base+'/planning/graphs',{data:{title:'Original scene plan'}}));
  const volume=await checked(await request.post(base+'/planning/nodes',{data:{graph_id:graph.id,parent_id:graph.root_node_id,level:'VOLUME',title:'Volume'}}));
  const parent=await checked(await request.post(base+'/planning/nodes',{data:{graph_id:graph.id,parent_id:volume.id,level:'CHAPTER',title:'Chapter',links:{chapter_ids:[chapter.id]}}}));
  const scenes=[];
  for(const[title,position]of[['揭示前',10],['揭示后',20]]as const)scenes.push(await checked(await request.post(base+'/planning/nodes',{data:{graph_id:graph.id,parent_id:parent.id,level:'SCENE',title,position,links:{chapter_ids:[chapter.id]}}})));
  const approve=async(row:any)=>checked(await request.post(base+`/story-graph/records/${row.id}/approve`,{data:{expected_version:row.version}}));
  const secret='后场景口令是蓝鲸。';
  const relation=await approve(await checked(await request.post(base+'/story-graph/records',{data:{kind:'STORY_RELATION',title:'秘密规则',chapter_id:prior.id,data:{subject:{kind:'CHARACTER',id:'bob'},object:{kind:'LOCATION',id:'city'},relation:'KNOWS',layer:'WORLD_FACT',statement:secret}}})));
  await approve(await checked(await request.post(base+'/story-graph/records',{data:{kind:'KNOWLEDGE_EVENT',title:'后场景获知',chapter_id:chapter.id,data:{scene_id:scenes[1].id,character_id:'alice',operation:'LEARN',category:'SECRET',relation_id:relation.id}}})));
  await page.goto('/');await expect(page.getByRole('textbox',{name:'章节正文',exact:true})).toBeVisible();await workbench(page,'故事图谱');
  await page.getByRole('button',{name:'人物可知视图',exact:true}).click();await page.getByLabel('查询章节 ID',{exact:true}).fill(chapter.id);await page.getByLabel('视角人物 ID',{exact:true}).fill('alice');
  await page.getByLabel('查询场景 ID（留空为章末）',{exact:true}).fill(scenes[0].id);await page.getByRole('button',{name:'查询当前视图',exact:true}).click();
  await expect(page.getByRole('region',{name:'时间化关系图'})).toContainText('可见关系：0');await expect(page.getByText(secret,{exact:true})).toHaveCount(0);
  await page.getByLabel('查询场景 ID（留空为章末）',{exact:true}).fill(scenes[1].id);await page.getByRole('button',{name:'查询当前视图',exact:true}).click();await expect(page.getByRole('region',{name:'人物上下文预览'})).toContainText(secret);
  const received=await checked(await request.post(base+'/story-graph/character-context',{data:{chapter_id:chapter.id,character_id:'alice',scene_id:scenes[1].id}}));expect(received.scene_boundary.position).toBe(20);expect(generations).toEqual([]);
  await page.screenshot({path:info.outputPath('scene-knowledge-boundary.png'),fullPage:true});
 }finally{await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());}
});

test('Post-interop A11 original A/B evidence interpretations persist and reopen without manuscript writes',async({page,request},info)=>{
 const quiesce=createPageQuiescer(page);let nid='';const generationCalls:string[]=[];
 page.on('request',r=>{if(r.method()==='POST'&&/(?:generate|\/apply$)/.test(r.url()))generationCalls.push(r.url());});
 try{
  const novel=await checked(await request.post(`${API}/novels`,{data:{title:'Version comparison continuation synthetic'}}));nid=novel.id;
  const created=await checked(await request.post(`${API}/novels/${nid}/chapters`,{data:{title:'版本比较章',content:'旧稿'}}));
  let chapter=await checked(await request.get(`${API}/chapters/${created.id}`));
  const before=await checked(await request.put(`${API}/chapters/${chapter.id}`,{data:{version:chapter.version,document:doc('旧事实。')}}));
  chapter=await checked(await request.put(`${API}/chapters/${chapter.id}`,{data:{version:before.version,document:doc('新事实。')}}));
  await page.goto('/');await expect(page.getByRole('textbox',{name:'章节正文',exact:true})).toContainText('新事实。');await workbench(page,'选区修订与保护');
  await page.getByRole('button',{name:'比较原历史版本',exact:true}).click();await page.getByLabel('比较版本 A',{exact:true}).selectOption(String(before.version));await page.getByRole('button',{name:'预览原版本对比',exact:true}).click();
  await expect(page.locator('[aria-label="原版本文字差异"]')).toContainText('新');await page.getByLabel('版本比较名称',{exact:true}).fill('原版本事实变化');await page.getByRole('button',{name:'添加有证据的语义解释',exact:true}).click();
  await page.getByLabel('解释 1 来源',{exact:true}).selectOption('IMPORTED_MODEL_ASSESSMENT');await page.getByLabel('解释 1 声明模型',{exact:true}).fill('synthetic-declared-model');await page.getByLabel('解释 1 判断',{exact:true}).fill('导入的事实新增判断，需作者复审。');await page.getByLabel('解释 1 B 原文证据',{exact:true}).fill('新事实。');await page.getByRole('button',{name:'保存版本比较与解释',exact:true}).click();
  await page.getByRole('button',{name:'确认已读解读',exact:true}).click();await expect(page.getByRole('button',{name:'重新审核此比较',exact:true})).toBeVisible();
  await page.reload();await workbench(page,'选区修订与保护');await page.getByRole('button',{name:'比较原历史版本',exact:true}).click();await page.getByRole('button',{name:'打开此版本比较',exact:true}).click();await expect(page.getByText(/模型身份为用户声明/)).toBeVisible();
  const base=`${API}/novels/${nid}/experimental/revisions`;const rows=await checked(await request.get(base+'/comparisons'));expect(rows.items).toHaveLength(1);
  const saved=await checked(await request.get(base+'/comparisons/'+rows.items[0].id));expect(saved.changes[0].interpretation).toBe('MODEL_DERIVED');expect(saved.changes[0].provenance_verification).toBe('DECLARED_NOT_VERIFIED');expect(saved.status).toBe('ACKNOWLEDGED');expect(saved.history).toHaveLength(1);expect(await checked(await request.get(`${API}/chapters/${chapter.id}`))).toEqual(chapter);expect(generationCalls).toEqual([]);
  for(const[width,height]of[[1366,768],[1440,900],[1920,1080]]){await page.setViewportSize({width,height});await page.evaluate(()=>window.document.fonts.ready);expect(await page.evaluate(()=>window.document.documentElement.scrollWidth-innerWidth)).toBe(0);await page.screenshot({path:info.outputPath(`version-comparison-${width}.png`),fullPage:true});}
 }finally{await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());}
});

test('Post-interop A11 registered local model preview, consent, original job and review-only interpretation',async({page,request},info)=>{
 const api='http://127.0.0.1:8022/api',ui='http://127.0.0.1:5182',headers={'X-Session-Token':'r4-broker-test-session'};const quiesce=createPageQuiescer(page);let nid='',jobId='';
 try{
  await page.setExtraHTTPHeaders(headers);const novel=await checked(await request.post(`${api}/novels`,{headers,data:{title:'A11 registered opinion synthetic'}}));nid=novel.id;
  const created=await checked(await request.post(`${api}/novels/${nid}/chapters`,{headers,data:{title:'原版本模型章',content:'A calm synthetic beginning.'}}));
  const before=await checked(await request.get(`${api}/chapters/${created.id}`,{headers}));
  const chapter=await checked(await request.put(`${api}/chapters/${created.id}`,{headers,data:{version:before.version,content:'A tense synthetic beginning.'}}));
  const base=`${api}/novels/${nid}/experimental`,comparison={chapter_id:chapter.id,current_version:chapter.version,before_version:before.version,after_version:chapter.version};
  const deterministic=await checked(await request.post(base+'/revisions/comparisons/preview',{headers,data:comparison}));
  const saved=await checked(await request.post(base+'/revisions/comparisons',{headers,data:{comparison,preview_digest:deterministic.preview_digest,title:'Original model comparison'}}));
  await page.goto(ui);await expect(page.getByRole('textbox',{name:'章节正文',exact:true})).toBeVisible();await workbench(page,'选区修订与保护');await page.getByRole('button',{name:'比较原历史版本',exact:true}).click();await page.getByRole('button',{name:'打开此版本比较',exact:true}).click();
  const model=page.getByRole('region',{name:'已注册版本比较模型',exact:true});await model.getByRole('button',{name:'查看已注册版本比较模型',exact:true}).click();
  const catalog=await checked(await request.get(base+'/revisions/comparisons-model/catalog',{headers}));const route=catalog.routes.find((r:any)=>r.provider_id==='mock');expect(route.synthetic).toBe(true);await model.getByLabel('本地版本比较模型',{exact:true}).selectOption(route.route_id);
  const previewing=page.waitForResponse(r=>r.url().endsWith(`/comparisons/${saved.id}/model/preview`));await model.getByRole('button',{name:'准备准确版本模型预览',exact:true}).click();const prepared=await checked(await previewing);expect(prepared.model_preview.request.context).toEqual({});expect(prepared.model_preview.sources.versions.before.version).toBe(before.version);
  await expect(model.getByRole('button',{name:'明确发送此次本地版本比较',exact:true})).toBeDisabled();expect((await checked(await request.get(base+'/model-broker/history',{headers}))).ledger).toHaveLength(0);
  await model.getByLabel('已核对原版本全文、模型身份与零费用预占',{exact:true}).check();const sending=page.waitForResponse(r=>r.url().endsWith(`/comparisons/${saved.id}/model/dispatch`));await model.getByRole('button',{name:'明确发送此次本地版本比较',exact:true}).click();const running=await checked(await sending);jobId=running.model_execution.job_id;
  await expect.poll(async()=>(await checked(await request.get(base+'/model-broker/jobs/'+running.model_execution.reservation_id,{headers}))).ledger.status,{timeout:90000}).toBe('SETTLED');await model.getByRole('button',{name:'核对原版本模型任务',exact:true}).click();await expect(model.getByText('Model-derived · 实际原模型任务',{exact:true})).toBeVisible();
  const accepting=page.waitForResponse(r=>r.url().includes(`/comparisons/${saved.id}/model/opinions/`)&&r.url().endsWith('/accept'));await model.getByRole('button',{name:'接受为解读（不改稿）',exact:true}).click();const accepted=await checked(await accepting);expect(accepted.model_assessments[0].source).toBe('EXECUTED_MODEL_ASSESSMENT');expect(accepted.model_assessments[0].quality_verification).toBe('SYNTHETIC_PROTOCOL_ONLY');expect(accepted.model_assessments[0].decision).toBe('ACCEPTED_INTERPRETATION');
  expect((await request.post(`${api}/generation/${jobId}/accept`,{headers,data:{}})).status()).toBe(409);expect(await checked(await request.get(`${api}/chapters/${chapter.id}`,{headers}))).toEqual(chapter);
  await page.reload();await workbench(page,'选区修订与保护');await page.getByRole('button',{name:'比较原历史版本',exact:true}).click();await page.getByRole('button',{name:'打开此版本比较',exact:true}).click();await expect(model).toContainText(jobId);expect((await checked(await request.get(base+'/model-broker/history',{headers}))).ledger).toHaveLength(1);await page.screenshot({path:info.outputPath('revision-original-model-opinion.png'),fullPage:true});
 }finally{if(jobId)await request.post(`${api}/generation/${jobId}/cancel`,{headers}).catch(()=>{});await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${api}/novels/${nid}`,{headers})).status());}
});
