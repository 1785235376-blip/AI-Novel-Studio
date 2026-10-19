import { expect, test } from '@playwright/test';
import { readFileSync, writeFileSync } from 'node:fs';
import path from 'node:path';
const evidence = process.env.NLE_SELECTION_EVIDENCE_DIR;
if (!evidence) throw new Error('NLE_SELECTION_EVIDENCE_DIR must point to the task-private real runtime');
const seed = JSON.parse(readFileSync(path.join(evidence, process.env.NLE_SELECTION_SEED_FILE ?? 'seed-result.json'), 'utf8'));
const runtime = JSON.parse(readFileSync(path.join(evidence, 'runtime-ports.json'), 'utf8'));
const privateHost = JSON.parse(readFileSync(path.join(runtime.profile, 'host.private.json'), 'utf8'));

test('production cross-track subset -> original atomic move and history -> one CAS save -> same File timeline reopened', async ({ page, browser }, info) => {
  const calls: { method:string;path:string;status:number;request?:any;response?:any }[] = [];
  const pending:Promise<void>[]=[], errors:string[]=[],geometry:unknown[]=[];
  const timelinePath=`/api/projects/${seed.project.id}/studio/production/timelines/${seed.timeline.id}`;
  const title=seed.timeline.title;let saved:any,phase='OPEN_ORIGINAL_ENTRY';
  page.on('pageerror',error=>errors.push(error.message));
  page.on('response',response=>{
    const url=new URL(response.url());if(!url.pathname.startsWith('/api/'))return;
    pending.push((async()=>{
      let body,request;
      if(url.pathname.includes('/production/timelines'))try{body=await response.json();}catch{body={non_json:true};}
      try{request=response.request().postDataJSON();}catch{/* GET */}
      calls.push({method:response.request().method(),path:url.pathname,status:response.status(),request,response:body});
    })());
  });
  const screenshot=async(name:string)=>{await page.evaluate(()=>document.fonts.ready);await page.screenshot({path:info.outputPath(name+'.png')});};
  const verifyHost=async()=>{
    await page.getByRole('tab',{name:'小说',exact:true}).click();
    await expect(page.getByRole('tab',{name:'小说',exact:true})).toHaveAttribute('aria-selected','true');
    await page.getByRole('button',{name:'打开功能导航',exact:true}).click();
    const group=page.getByRole('button',{name:/^协作(?:\s*当前)?$/});if(await group.getAttribute('aria-expanded')!=='true')await group.click();
    await page.getByRole('button',{name:'Agent 团队',exact:true}).click();await page.getByRole('button',{name:'关闭功能导航',exact:true}).click();
    await page.getByLabel('本机访问凭证',{exact:true}).fill(privateHost.token);
    const verification=page.waitForResponse(response=>new URL(response.url()).pathname==='/api/local-session');
    await page.getByRole('button',{name:'验证并绑定本机会话',exact:true}).click();expect((await verification).status()).toBe(200);
    await expect(page.getByText('已验证本机身份：synthetic-nle-selection-host',{exact:true})).toBeVisible();
    await page.getByRole('tab',{name:'图片',exact:true}).click();
  };
  const editor=page.locator('[aria-label="Studio 多轨时间线编辑器"]');
  const tracks=editor.locator('[aria-label="轨道头"]');
  const clip=(id:string)=>tracks.getByRole('button',{name:id,exact:true});
  const selected=()=>tracks.locator('button[aria-pressed="true"]').allTextContents();
  const adopt=async(target:{id:string;title:string;version:number})=>{
    await editor.getByRole('button',{name:'刷新时间线列表',exact:true}).click();
    const select=editor.getByLabel('读取已保存时间线');
    await expect(select.locator(`option[value="${target.id}"]`)).toHaveText(target.title+` · v${target.version}`);await select.selectOption(target.id);
    const review=editor.locator('[aria-label="核对服务端时间线"]');await expect(review.getByRole('heading',{name:target.title+` · v${target.version}`,exact:true})).toBeVisible();
    await review.getByLabel('已核对服务端内容与本地输入，确认以下选择',{exact:true}).check();await review.getByRole('button',{name:'采用服务端时间线',exact:true}).click();
    await expect(select).toHaveValue(target.id);
  };
  const open=async(version:number)=>{
    await page.getByRole('button',{name:'制作操作',exact:true}).click();await page.getByRole('button',{name:'读取当前素材版本',exact:true}).click();
    await expect(editor).toBeVisible();await adopt({...seed.timeline,version});
  };
  const beforePositions=seed.timeline.timeline.tracks.flatMap((track:any)=>track.clips.map((clip:any)=>clip.start_ms));
  const afterPositions=seed.timeline.timeline.tracks.flatMap((track:any)=>track.clips.map((clip:any)=>clip.start_ms+(seed.selected_ids.includes(clip.id)?seed.offset_ms:0)));
  const beforeVersion=seed.timeline.version,afterVersion=beforeVersion+1;
  const positions=async(values:number[])=>{
    for(const [index,[track,clipIndex]] of [[1,1],[1,2],[2,1],[2,2]].entries())
      await expect(editor.getByRole('region',{name:`轨道 ${track} 片段 ${clipIndex}`,exact:true}).getByLabel('放入时间线（毫秒）',{exact:true})).toHaveValue(String(values[index]));
  };
  try{
    await page.goto('/',{waitUntil:'networkidle'});await verifyHost();await open(beforeVersion);await positions(beforePositions);
    phase='SELECT_SUBSET';await clip('v2-b').click();await clip('v1-a').click({modifiers:['Control']});expect(await selected()).toEqual(['v1-a','v2-b']);
    await clip('v1-a').click({modifiers:['Control']});expect(await selected()).toEqual(['v2-b']);await clip('v1-a').click({modifiers:['Meta']});expect(await selected()).toEqual(['v1-a','v2-b']);
    await clip('v1-b').click();expect(await selected()).toEqual(['v1-b']);
    await clip('v1-a').focus();await clip('v1-a').press('Enter');expect(await selected()).toEqual(['v1-a']);
    await clip('v2-b').focus();await clip('v2-b').press('Control+Enter');expect(await selected()).toEqual(['v1-a','v2-b']);
    await clip('v1-b').focus();await clip('v1-b').press('Control+Space');expect(await selected()).toEqual(['v1-a','v1-b','v2-b']);await clip('v1-b').press('Control+Space');expect(await selected()).toEqual(['v1-a','v2-b']);
    await clip('v1-b').evaluate(button=>{button.dispatchEvent(new CompositionEvent('compositionstart',{bubbles:true,data:'中'}));(button as HTMLButtonElement).click();button.dispatchEvent(new CompositionEvent('compositionend',{bubbles:true,data:'中'}));});
    expect(await selected()).toEqual(['v1-a','v2-b']);
    const selectionPreview=editor.locator('[aria-label="播放头拆分预览"]');await expect(selectionPreview).toContainText('v1-a');await expect(selectionPreview).toContainText('v2-b');await expect(selectionPreview).not.toContainText('v1-b');
    await tracks.scrollIntoViewIfNeeded();await screenshot('01-real-cross-track-subset');
    phase='LOCAL_ATOMIC_MOVE';await editor.getByLabel('整体移动增量（毫秒，可为负）',{exact:true}).fill('500');
    await editor.getByRole('button',{name:'整体移动所选片段',exact:true}).click();await expect(page.getByText('整体移动已应用到本地草稿；一次撤销可恢复，保存前不会写入服务端。',{exact:true})).toBeVisible();
    await positions(afterPositions);await editor.getByRole('button',{name:'撤销本地编辑',exact:true}).click();await positions(beforePositions);await expect(editor.getByRole('button',{name:'撤销本地编辑',exact:true})).toBeDisabled();
    await editor.getByRole('button',{name:'重做本地编辑',exact:true}).click();await positions(afterPositions);await screenshot('02-original-atomic-history-before-save');
    await Promise.all(pending);expect(calls.filter(c=>c.method!=='GET')).toEqual([]);
    phase='SAVE_SENT';const response=page.waitForResponse(r=>new URL(r.url()).pathname===timelinePath&&r.request().method()==='PUT');
    await editor.getByRole('button',{name:'保存时间线',exact:true}).click();const receipt=await response;expect(receipt.status()).toBe(200);saved=await receipt.json();phase='SAVE_ACKNOWLEDGED';
    expect(saved.version).toBe(afterVersion);expect(saved.id).toBe(seed.timeline.id);const expected=structuredClone(seed.timeline.timeline);
    for(const track of expected.tracks)for(const c of track.clips)if(seed.selected_ids.includes(c.id))c.start_ms+=seed.offset_ms;
    expect(receipt.request().postDataJSON()).toEqual({expected_version:beforeVersion,title,timeline:expected});expect(saved.timeline).toEqual(expected);
    await screenshot(`03-original-cas-save-v${afterVersion}`);
    phase='REFRESH_REOPEN';await page.reload({waitUntil:'networkidle'});await verifyHost();await open(afterVersion);await positions(afterPositions);expect(await selected()).toEqual([]);
    await screenshot('04-real-file-same-id-reopened');
    for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
      await page.setViewportSize(viewport);await clip('v2-b').click();await clip('v1-a').click({modifiers:['Control']});expect(await selected()).toEqual(['v1-a','v2-b']);await tracks.scrollIntoViewIfNeeded();
      const size=await tracks.evaluate(element=>({width:innerWidth,scrollWidth:document.documentElement.scrollWidth,panelLeft:element.getBoundingClientRect().left,panelRight:element.getBoundingClientRect().right}));
      expect(size.scrollWidth).toBeLessThanOrEqual(viewport.width);expect(size.panelLeft).toBeGreaterThanOrEqual(0);expect(size.panelRight).toBeLessThanOrEqual(viewport.width);geometry.push({...viewport,...size});
      const colors=await tracks.evaluate(element=>{const picked=element.querySelector('button[aria-pressed="true"]')!,plain=element.querySelector('button[aria-pressed="false"]')!;return {picked:getComputedStyle(picked).backgroundColor,plain:getComputedStyle(plain).backgroundColor};});expect(colors.picked).not.toBe(colors.plain);
      await screenshot(`05-selected-${viewport.width}x${viewport.height}`);await tracks.getByRole('button',{name:'清除片段选择',exact:true}).click();expect(await selected()).toEqual([]);
    }
    if(seed.second_timeline){
      phase='SWITCH_SAME_CLIP_IDS_DOCUMENT';
      expect(seed.second_timeline.id).not.toBe(seed.timeline.id);expect(seed.second_timeline.timeline).toEqual(saved.timeline);
      await clip('v1-a').click();await clip('v2-b').click({modifiers:['Control']});expect(await selected()).toEqual(['v1-a','v2-b']);
      await adopt(seed.second_timeline);expect(await selected()).toEqual([]);await positions(afterPositions);
      await tracks.scrollIntoViewIfNeeded();await screenshot('06-second-document-same-clip-ids-selection-cleared');
    }
    await Promise.all(pending);expect(errors).toEqual([]);expect(calls.filter(c=>c.method!=='GET').map(c=>[c.method,c.path,c.status])).toEqual([['PUT',timelinePath,200]]);
    const persisted=await page.evaluate(()=>[...Object.values(localStorage),...Object.values(sessionStorage)]);expect(persisted.some(value=>value.includes(privateHost.token)),'Host credential must remain memory only').toBe(false);
    phase='PASS';writeFileSync(path.join(evidence,'live-result.json'),JSON.stringify({status:'PASS',browser_version:browser.version(),proof:'REAL_ORIGINAL_APP_HTTP_FILE_NO_API_INTERCEPTION',project:seed.project.id,timeline_id:seed.timeline.id,before:seed.timeline,after:saved,second_document:seed.second_timeline?.id,same_clip_ids_document_selection_cleared:!!seed.second_timeline,selected_ids:seed.selected_ids,unselected_ids:seed.unselected_ids,offset_ms:500,relative_offset_ms:5500,geometry,calls,errors,model_called:false,render_called:false,credential_persisted:false,native_os_ime_acceptance:false},null,2));
  }catch(error){
    if(!page.isClosed()){await screenshot('failure-current-real-ui');writeFileSync(path.join(evidence,'failure-dom.txt'),await page.locator('body').innerText());}throw error;
  }finally{await Promise.allSettled(pending);writeFileSync(path.join(evidence,'live-attempt.json'),JSON.stringify({phase,saved,calls,errors,geometry},null,2));}
});
