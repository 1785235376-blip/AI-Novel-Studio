import {expect,test,type APIResponse} from '@playwright/test';
import {createPageQuiescer} from './r3-fixture-lifecycle';
const API='http://127.0.0.1:8047/api';
async function checked(response:APIResponse){expect(response.ok(),`HTTP ${response.status()}: ${await response.text()}`).toBeTruthy();return response.json();}
test('original Adaptation retains conflict drafts, binds human review, and cancels/recoveries without replay',async({page,request},info)=>{
  const quiet=createPageQuiescer(page);let nid='',targetId='';
  info.annotations.push({type:'verification',description:'Real File API and original React Adaptation; synthetic local preparation only. No mocked business responses or model dispatch.'});
  try{
    const novel=await checked(await request.post(`${API}/novels`,{data:{title:`Adaptation surface ${info.testId}`}}));nid=novel.id;
    const source=await checked(await request.post(`${API}/novels/${nid}/chapters`,{data:{title:'Bound source',content:'SYNTHETIC SOURCE PROSE'}}));
    await page.goto('/');await page.getByRole('button',{name:'切换本机作品',exact:true}).click();await page.getByRole('button',{name:novel.title,exact:true}).click();
    await expect(page.getByRole('textbox',{name:'章节正文',exact:true})).toContainText('SYNTHETIC SOURCE PROSE');
    await page.getByRole('button',{name:/功能导航/}).first().click();const group=page.getByRole('button',{name:'制作与分析',exact:true});if(await group.getAttribute('aria-expanded')!=='true')await group.click();
    await page.getByRole('button',{name:'智能改编',exact:true}).click();await page.keyboard.press('Escape');
    const surface=page.locator('.novel-adaptation-panel');await expect(surface.getByText('暂无改编方案')).toBeVisible();await expect(surface.getByText(/模型改写：NOT_CONFIGURED/)).toBeVisible();
    await surface.getByLabel('改编方案名称',{exact:true}).fill('Original adaptation');
    const creating=page.waitForResponse(r=>r.url().endsWith(`/novels/${nid}/adaptations`)&&r.request().method()==='POST');await surface.getByRole('button',{name:'创建改编方案',exact:true}).click();const proposal=await(await creating).json();
    const base=`${API}/novels/${nid}/adaptations/${proposal.id}`;const article=surface.getByRole('article',{name:'改编方案 Original adaptation',exact:true});
    await article.getByText('编辑改编蓝图',{exact:true}).click();const focus=article.getByLabel('改编重点',{exact:true});await focus.fill('Retained local adaptation draft');
    await checked(await request.put(`${base}/blueprint`,{data:{...proposal.blueprint,focus:'Other writer',expected_revision:proposal.revision}}));
    const conflict=page.waitForResponse(r=>r.url().endsWith(`/adaptations/${proposal.id}/blueprint`)&&r.request().method()==='PUT');await article.getByRole('button',{name:'保存蓝图修订',exact:true}).click();expect((await conflict).status()).toBe(409);await expect(focus).toHaveValue('Retained local adaptation draft');
    await surface.getByRole('button',{name:'读取最新状态',exact:true}).click();await expect(article.getByText(/服务器已有版本 2/)).toBeVisible();await expect(focus).toHaveValue('Retained local adaptation draft');
    await article.getByRole('button',{name:'放弃本地编辑并加载最新蓝图',exact:true}).click();await expect(focus).toHaveValue('Other writer');
    const approving=page.waitForResponse(r=>r.url().endsWith(`/adaptations/${proposal.id}/approve`));await article.getByRole('button',{name:'批准方案',exact:true}).click();expect((await approving).status()).toBe(200);
    const materializing=page.waitForResponse(r=>r.url().endsWith(`/adaptations/${proposal.id}/materialize`));await article.getByRole('button',{name:'生成改编版本',exact:true}).click();const created=await materializing;expect(created.status()).toBe(201);targetId=(await created.json()).id;
    await article.getByText('查看改编执行清单',{exact:true}).click();const generating=page.waitForResponse(r=>r.url().includes('/tasks/')&&r.url().endsWith('/generate'));await article.getByRole('button',{name:'生成本地准备稿',exact:true}).click();const task=await(await generating).json();expect(task.status).toBe('AWAITING_REVIEW');
    await article.getByText('审阅草稿正文与来源绑定',{exact:true}).click();await expect(article.getByText('SYNTHETIC SOURCE PROSE',{exact:true})).toBeVisible();
    const reviewing=page.waitForResponse(r=>r.url().endsWith(`/tasks/${task.id}/review`));await article.getByRole('button',{name:'接受草稿',exact:true}).click();expect((await reviewing).status()).toBe(200);
    const target=await checked(await request.get(`${API}/chapters/${encodeURIComponent(task.target_chapter_id)}`));
    const updated=await checked(await request.put(`${API}/chapters/${encodeURIComponent(target.id)}`,{data:{version:target.version,document:{type:'doc',content:[{type:'paragraph',content:[{type:'text',text:'NEWER HUMAN TARGET'}]}]},source:'MANUAL_SAVE'}}));
    const applying=page.waitForResponse(r=>r.url().endsWith(`/tasks/${task.id}/apply`));await article.getByRole('button',{name:'写入工作副本',exact:true}).click();expect((await applying).status()).toBe(409);expect((await checked(await request.get(`${API}/chapters/${encodeURIComponent(target.id)}`))).document).toEqual(updated.document);
    const cancelling=page.waitForResponse(r=>r.url().endsWith(`/tasks/${task.id}/actions/cancel`));await article.getByRole('button',{name:'取消此任务',exact:true}).click();expect((await(await cancelling).json()).status).toBe('CANCELLED');
    const recovering=page.waitForResponse(r=>r.url().endsWith(`/tasks/${task.id}/actions/recover`));await article.getByRole('button',{name:'核对并恢复任务',exact:true}).click();expect((await(await recovering).json()).status).toBe('PENDING_REWRITE');
    await article.getByText('查看方案修订与恢复记录',{exact:true}).click();await expect(article.getByText(/COMPLETED/)).toBeVisible();
    for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){
      await page.setViewportSize({width,height});await page.emulateMedia({reducedMotion:'reduce'});await page.evaluate(()=>document.fonts.ready);await surface.scrollIntoViewIfNeeded();
      const metrics=await surface.evaluate(node=>({overflow:document.documentElement.scrollWidth-innerWidth,header:document.querySelector('.global-header')!.getBoundingClientRect().height,context:document.querySelector('.context-bar')!.getBoundingClientRect().height,status:document.querySelector('.status-bar')!.getBoundingClientRect().height,width:node.getBoundingClientRect().width}));
      expect(metrics.overflow).toBeLessThanOrEqual(1);expect(metrics.header).toBe(56);expect(metrics.context).toBe(44);expect(metrics.status).toBe(32);expect(metrics.width).toBeGreaterThan(400);await page.screenshot({path:info.outputPath(`adaptation-original-${width}.png`)});
    }
    const saved=await checked(await request.get(`${API}/novels/${nid}/adaptations`));expect(saved.find((p:any)=>p.id===proposal.id).execution_manifest[0].id).toBe(task.id);
    expect((await checked(await request.get(`${API}/chapters/${encodeURIComponent(source.id)}`))).content).toContain('SYNTHETIC SOURCE PROSE');
    await page.reload();await page.getByRole('button',{name:/功能导航/}).first().click();await page.getByRole('button',{name:'智能改编',exact:true}).click();await page.keyboard.press('Escape');await expect(surface.getByText('Original adaptation',{exact:true})).toBeVisible();
  }finally{await quiet();for(const id of [targetId,nid])if(id)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${id}`)).status());}
});
