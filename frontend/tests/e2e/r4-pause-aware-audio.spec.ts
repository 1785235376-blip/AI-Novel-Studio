import { expect, test, type APIResponse, type Page } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API='http://127.0.0.1:8019/api';
async function body(response:APIResponse){expect(response.ok(),await response.text()).toBeTruthy();return response.json();}
async function open(page:Page){
 await page.getByRole('button',{name:/功能导航/}).first().click();const group=page.getByRole('button',{name:/^Experimental/});if(await group.getAttribute('aria-expanded')!=='true')await group.click();
 await page.getByRole('button',{name:'实验工作台',exact:true}).click();await page.keyboard.press('Escape');await page.getByRole('navigation',{name:'实验功能'}).getByRole('button',{name:'声音导演',exact:true}).click();
}
function wav(sample:number){const b=Buffer.alloc(44+1600);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(8000,24);b.writeUInt32LE(16000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(1600,40);for(let i=44;i<b.length;i+=2)b.writeInt16LE(sample,i);return b;}
test('B03 explicit pause-aware PCM preview, actual WAV download, review and stale rejection',async({page,request},info)=>{
 const quiesce=createPageQuiescer(page);let nid='';info.annotations.push({type:'verification',description:'Production local PCM mixer and real File API/UI. Synthetic samples only, no TTS voice-quality assertion. Hosted browser execution required.'});
 try{
  await page.goto('/');await page.getByPlaceholder('小说名称').fill('Synthetic pause-aware audio');const created=page.waitForResponse(r=>r.url().endsWith('/api/novels')&&r.request().method()==='POST');await page.getByRole('button',{name:'创建小说',exact:true}).click();nid=(await body(await created)).id;
  const base=`${API}/novels/${nid}/experimental`;
  const chapter=await body(await page.request.post(`${API}/novels/${nid}/chapters`,{data:{title:'Synthetic chapter',content:'First narration. “Quoted text.” Final narration.'}}));
  const profile=await body(await page.request.post(`${base}/audiobook/profiles`,{data:{display_name:'Synthetic manual voice',provider_id:'not-configured',model_id:'not-a-real-model',voice_id:'synthetic',license_note:'Synthetic PCM fixture only'}}));
  let plan=await body(await page.request.post(`${base}/audiobook/plans`,{data:{chapter_id:chapter.id,title:'Pause-aware plan'}}));expect(plan.segments.length).toBe(3);
  const ids=plan.segments.map((s:{id:string})=>s.id);let expectedFrames=0;
  for(let i=0;i<ids.length;i++){
   const s=plan.segments.find((s:{id:string})=>s.id===ids[i]);const pause=125+i*100;
   plan=await body(await page.request.put(`${base}/voice-direction/plans/${plan.id}/segments/${s.id}`,{data:{expected_version:plan.version,kind:'NARRATION',profile_id:profile.id,reviewed_text:s.text,attribution_reviewed:true,text_reviewed:true,voice_authorized:true,pause_ms:pause}}));
   const asset=await body(await page.request.post(`${API}/novels/${nid}/assets`,{data:{novel_id:nid,filename:`synthetic-${i}.wav`,content_base64:wav(100*(i+1)).toString('base64'),media_type:'audio/wav',kind:'audio'}}));
   plan=await body(await page.request.put(`${base}/audiobook/plans/${plan.id}/segments/${s.id}/audio`,{data:{expected_version:plan.version,asset_id:asset.id}}));expectedFrames+=800+(i+1<ids.length?pause*8:0);
  }
  plan=await body(await page.request.post(`${base}/audiobook/plans/${plan.id}/approve`,{data:{expected_version:plan.version}}));
  await open(page);await page.getByLabel('声音导演有声计划',{exact:true}).selectOption(plan.id);
  const mixedResponse=page.waitForResponse(r=>r.url().endsWith(`/voice-direction/plans/${plan.id}/mix`)&&r.request().method()==='POST');await page.getByRole('button',{name:'生成含停顿混音候选',exact:true}).click();const mixed=await body(await mixedResponse);expect(mixed.status).toBe('PENDING_REVIEW');
  await page.getByRole('button',{name:'试听含停顿混音',exact:true}).click();await expect(page.getByRole('status').filter({hasText:'已读取含停顿混音，请试听完整轨道'})).toBeVisible();
  const download=page.waitForEvent('download');await page.getByRole('button',{name:'下载混音 WAV',exact:true}).click();const bytes=await fs.readFile((await (await download).path())!);expect(bytes.toString('ascii',0,4)).toBe('RIFF');expect(bytes.readUInt32LE(40)).toBe(expectedFrames*2);expect(bytes.readInt16LE(44)).toBe(100);expect(bytes.readInt16LE(44+1600)).toBe(0);expect(bytes.readInt16LE(44+(800+125*8)*2)).toBe(200);
  await page.getByRole('button',{name:'批准混音资产',exact:true}).click();await expect(page.getByText('混音已批准加入原资产库，保留来源与版本',{exact:true})).toBeVisible();
  for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){await page.setViewportSize({width,height});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`pause-aware-audio-${width}.png`)});}
  const catalog=await body(await page.request.get(`${base}/voice-direction/catalog`));const accepted=catalog.mixes.find((r:{id:string})=>r.id===mixed.id);expect(accepted.status).toBe('APPROVED');
  const current=await body(await page.request.get(`${API}/chapters/${chapter.id}`));await body(await page.request.put(`${API}/chapters/${chapter.id}`,{data:{version:current.version,content:'Changed current manuscript'}}));await page.getByRole('button',{name:'刷新声音来源与任务',exact:true}).click();await expect(page.getByText(/旧片段已隐藏/)).toBeVisible();await expect(page.getByRole('button',{name:'下载混音 WAV',exact:true})).toHaveCount(0);
  expect((await page.request.get(`${base}/voice-direction/mixes/${mixed.id}/audio?expected_version=${accepted.version}`)).status()).toBe(409);
 }finally{await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());}
});
