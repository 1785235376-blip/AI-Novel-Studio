import { expect, test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
const evidence=process.env.NLE_CUT_NAVIGATION_EVIDENCE_DIR;
if(!evidence)throw new Error('NLE_CUT_NAVIGATION_EVIDENCE_DIR must point to the task-private real runtime');
const runtime=JSON.parse(readFileSync(path.join(evidence,'runtime-ports.json'),'utf8'));
const seed=JSON.parse(readFileSync(path.join(evidence,'seed-result.json'),'utf8'));
const privateHost=JSON.parse(readFileSync(path.join(runtime.profile,'host.private.json'),'utf8'));

test('real original File timelines: local cut navigation, input/IME isolation, second document/version edges and zero writes',async({page,browser},info)=>{
 const calls:{method:string;path:string;status:number;response?:unknown}[]=[],errors:string[]=[],pending:Promise<void>[]=[],geometry:unknown[]=[],jumps:unknown[]=[];
 let phase='OPEN_ORIGINAL_ENTRY';
 page.on('pageerror',error=>errors.push(error.message));
 page.on('response',response=>{
  const pathname=new URL(response.url()).pathname;if(!pathname.startsWith('/api/'))return;
  pending.push((async()=>{let body;if(pathname.includes('/production/timelines'))try{body=await response.json();}catch{body={non_json:true};}
   calls.push({method:response.request().method(),path:pathname,status:response.status(),response:body});})());
 });
 const editor=page.locator('[aria-label="Studio 多轨时间线编辑器"]'),ruler=editor.locator('[aria-label="时间线标尺"]');
 const next=()=>ruler.getByRole('button',{name:'下一个剪切点',exact:true}),previous=()=>ruler.getByRole('button',{name:'上一个剪切点',exact:true});
 const head=async(ms:number)=>{await expect(ruler).toHaveAttribute('data-playhead-ms',String(ms));jumps.push({phase,ms});};
 const screenshot=async(name:string)=>{await page.evaluate(()=>document.fonts.ready);await ruler.scrollIntoViewIfNeeded();await page.screenshot({path:info.outputPath(name+'.png')});};
 const verifyHost=async()=>{
  await page.getByRole('tab',{name:'小说',exact:true}).click();await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
  const group=page.getByRole('button',{name:/^协作(?:\s*当前)?$/});if(await group.getAttribute('aria-expanded')!=='true')await group.click();
  await page.getByRole('button',{name:'Agent 团队',exact:true}).click();await page.getByRole('button',{name:'关闭功能导航',exact:true}).click();
  await page.getByLabel('本机访问凭证',{exact:true}).fill(privateHost.token);
  const response=page.waitForResponse(r=>new URL(r.url()).pathname==='/api/local-session');await page.getByRole('button',{name:'验证并绑定本机会话',exact:true}).click();expect((await response).status()).toBe(200);
  await expect(page.getByText('已验证本机身份：synthetic-nle-cut-navigation-host',{exact:true})).toBeVisible();await page.getByRole('tab',{name:'图片',exact:true}).click();
 };
 const adopt=async(document:any)=>{
  await editor.getByRole('button',{name:'刷新时间线列表',exact:true}).click();const select=editor.getByLabel('读取已保存时间线');
  await expect(select.locator(`option[value="${document.id}"]`)).toHaveText(document.title+` · v${document.version}`);await select.selectOption(document.id);
  const review=editor.locator('[aria-label="核对服务端时间线"]');await expect(review.getByRole('heading',{name:document.title+` · v${document.version}`,exact:true})).toBeVisible();
  await review.getByLabel('已核对服务端内容与本地输入，确认以下选择',{exact:true}).check();await review.getByRole('button',{name:'采用服务端时间线',exact:true}).click();await expect(select).toHaveValue(document.id);
 };
 const unchangedHistory=async()=>{await expect(editor.getByRole('button',{name:'撤销本地编辑',exact:true})).toBeDisabled();await expect(editor.getByRole('button',{name:'保存时间线',exact:true})).toBeDisabled();};
 try{
  await page.goto('/',{waitUntil:'networkidle'});await verifyHost();await page.getByRole('button',{name:'制作操作',exact:true}).click();await page.getByRole('button',{name:'读取当前素材版本',exact:true}).click();await expect(editor).toBeVisible();await adopt(seed.first);
  await head(0);await unchangedHistory();await expect(previous()).toBeDisabled();
  phase='FIRST_REAL_BOUNDARIES';await next().click();await head(1000);
  await next().press('Enter');await head(1400);await previous().press('Space');await head(1000);
  for(const ms of seed.points_first.slice(2)){await ruler.focus();await ruler.press('ArrowDown');await head(ms);}
  await expect(next()).toBeDisabled();await ruler.press('ArrowDown');await head(6000);await screenshot('01-first-document-last-boundary');
  for(const ms of [...seed.points_first].reverse().slice(1)){await ruler.press('ArrowUp');await head(ms);}
  await expect(previous()).toBeDisabled();await ruler.press('ArrowUp');await head(0);
  phase='LOCAL_INPUT_AND_IME_ISOLATION';const input=ruler.getByLabel('播放头（毫秒）',{exact:true});await input.fill('123');await input.press('ArrowDown');await head(0);
  await page.getByRole('button',{name:'制作操作',exact:true}).focus();await page.keyboard.press('ArrowDown');await head(0);
  await ruler.focus();await ruler.press('Control+ArrowDown');await head(0);await ruler.press('Meta+ArrowDown');await head(0);
  await ruler.evaluate(element=>element.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:'中'})));await ruler.press('ArrowDown');await head(0);
  await ruler.evaluate(element=>element.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'中'})));
  await ruler.evaluate(element=>element.dispatchEvent(new KeyboardEvent('keydown',{bubbles:true,key:'ArrowDown',isComposing:true})));await head(0);
  await ruler.press('ArrowDown');await head(1000);await expect(input).toHaveValue('1000');await ruler.press('ArrowUp');await head(0);await unchangedHistory();
  phase='SECOND_SAVED_DOCUMENT_VERSION';expect(seed.second.version).toBe(2);await adopt(seed.second);await head(0);
  for(const ms of seed.points_second.slice(1)){await ruler.focus();await ruler.press('ArrowDown');await head(ms);}
  await screenshot('02-second-document-current-v2-boundaries');
  for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080},{width:2560,height:1440}]){
   phase='GEOMETRY';await page.setViewportSize(viewport);await ruler.focus();await ruler.press('ArrowUp');await head(5000);
   const size=await ruler.evaluate(element=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,left:element.getBoundingClientRect().left,right:element.getBoundingClientRect().right,focused:document.activeElement===element}));
   expect(size.scrollWidth).toBeLessThanOrEqual(viewport.width);expect(size.left).toBeGreaterThanOrEqual(0);expect(size.right).toBeLessThanOrEqual(viewport.width);expect(size.focused).toBe(true);geometry.push({...viewport,...size});
   await screenshot(`03-local-focused-navigation-${viewport.width}x${viewport.height}`);await ruler.press('ArrowDown');await head(6000);
  }
  await unchangedHistory();await Promise.all(pending);expect(errors).toEqual([]);expect(calls.filter(call=>call.method!=='GET')).toEqual([]);
  for(const row of [seed.first,seed.second])expect(calls.find(call=>call.path.endsWith('/production/timelines/'+row.id))?.response).toEqual(row);
  const persisted=await page.evaluate(()=>[...Object.values(localStorage),...Object.values(sessionStorage)]);expect(persisted.some(value=>value.includes(privateHost.token))).toBe(false);
  phase='PASS';writeFileSync(path.join(evidence,'live-result.json'),JSON.stringify({status:'PASS',browser_version:browser.version(),proof:'REAL_ORIGINAL_APP_HTTP_FILE_NO_API_INTERCEPTION',project:seed.project.id,documents:[seed.first,seed.second],points:[seed.points_first,seed.points_second],geometry,jumps,calls,errors,browser_write_count:0,history_unchanged:true,model_gpu_render_called:false,credential_persisted:false,native_os_ime_acceptance:false},null,2));
 }catch(error){if(!page.isClosed()){await page.screenshot({path:info.outputPath('failure-current-real-ui.png')});writeFileSync(path.join(evidence,'failure-dom.txt'),await page.locator('body').innerText());}throw error;}
 finally{await Promise.allSettled(pending);writeFileSync(path.join(evidence,'live-attempt.json'),JSON.stringify({phase,calls,errors,geometry,jumps},null,2));}
});
