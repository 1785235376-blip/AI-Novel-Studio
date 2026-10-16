import { expect, test, type APIResponse, type Page } from '@playwright/test';
import fs from 'node:fs/promises';
import { createPageQuiescer } from './r3-fixture-lifecycle';
const API='http://127.0.0.1:8019/api';
async function body(response:APIResponse){expect(response.ok(),await response.text()).toBeTruthy();return response.json();}
async function open(page:Page,name:string){
 await page.getByRole('button',{name:/功能导航/}).first().click();const group=page.getByRole('button',{name:/^Experimental/});if(await group.getAttribute('aria-expanded')!=='true')await group.click();
 await page.getByRole('button',{name:'实验工作台',exact:true}).click();await page.keyboard.press('Escape');await page.getByRole('navigation',{name:'实验功能'}).getByRole('button',{name,exact:true}).click();
}
function wav(){const b=Buffer.alloc(44+16000*2);b.write('RIFF');b.writeUInt32LE(b.length-8,4);b.write('WAVEfmt ',8);b.writeUInt32LE(16,16);b.writeUInt16LE(1,20);b.writeUInt16LE(1,22);b.writeUInt32LE(8000,24);b.writeUInt32LE(16000,28);b.writeUInt16LE(2,32);b.writeUInt16LE(16,34);b.write('data',36);b.writeUInt32LE(32000,40);return b;}
test('B03/B04 real File API voice correction, actual PCM waveform, subtitle edit/split/merge/export and source invalidation',async({page,request},info)=>{
 const quiesce=createPageQuiescer(page);let nid='';info.annotations.push({type:'verification',description:'Authored real File API/UI journey. Synthetic PCM bytes only; no TTS model/quality, external subtitle software or real voice cloning claim.'});
 try{
  await page.goto('/');await page.getByPlaceholder('小说名称').fill('Synthetic B03 B04');const created=page.waitForResponse(r=>r.url().endsWith('/api/novels')&&r.request().method()==='POST');await page.getByRole('button',{name:'创建小说',exact:true}).click();nid=(await body(await created)).id;
  const base=`${API}/novels/${nid}/experimental`;
  const chapter=await body(await page.request.post(`${API}/novels/${nid}/chapters`,{data:{title:'Synthetic chapter',content:'你好。Hello 🌙'}}));
  const profile=await body(await page.request.post(`${base}/audiobook/profiles`,{data:{display_name:'Synthetic fixture voice',provider_id:'fixture-unconfigured',model_id:'not-a-real-model',voice_id:'synthetic',license_note:'Original synthetic acceptance fixture'}}));
  await body(await page.request.post(`${base}/audiobook/mappings`,{data:{character_id:'__narrator__',profile_id:profile.id}}));
  const plan=await body(await page.request.post(`${base}/audiobook/plans`,{data:{chapter_id:chapter.id,title:'Synthetic directed plan'}}));
  await open(page,'声音导演');await page.getByLabel('声音导演有声计划',{exact:true}).selectOption(plan.id);await page.getByLabel('此片段审核朗读文本',{exact:true}).fill('你好。Hello moon');await page.getByLabel('已审核此片段朗读文本',{exact:true}).check();await page.getByLabel('已确认此声音的使用授权',{exact:true}).check();await page.getByRole('button',{name:'保存声音方向',exact:true}).click();await expect(page.getByText('当前片段已保存，只有该片段的旧音频失效')).toBeVisible();
  const updated=(await body(await page.request.get(`${base}/voice-direction/catalog`))).plans[0];expect(updated.segments[0].direction.reviewed_text).toBe('你好。Hello moon');
  const asset=await body(await page.request.post(`${API}/novels/${nid}/assets`,{data:{novel_id:nid,filename:'synthetic-pcm.wav',content_base64:wav().toString('base64'),media_type:'audio/wav',kind:'audio'}}));
  await page.getByRole('navigation',{name:'实验功能'}).getByRole('button',{name:'字幕时间轴',exact:true}).click();await page.getByLabel('字幕绑定媒体',{exact:true}).selectOption(asset.id);await page.getByLabel('字幕说话人来源计划',{exact:true}).selectOption(plan.id);await page.getByRole('button',{name:'创建字幕草稿',exact:true}).click();
  await page.getByText('实测 PCM16 波形',{exact:true}).click();await expect(page.getByRole('img',{name:'实际音频采样峰值波形'})).toBeVisible();
  await page.getByRole('button',{name:'添加人工字幕行',exact:true}).click();await page.getByLabel('字幕 1 文本',{exact:true}).fill('你好。Hello 🌙');await page.getByLabel('字幕 1 结束 tick',{exact:true}).fill('1500');await page.getByRole('button',{name:'保存字幕版本',exact:true}).click();await expect(page.getByText('字幕已保存；来源版本和媒体绑定保持校验')).toBeVisible();
  await page.getByText('拆分 / 合并字幕 1',{exact:true}).click();await page.getByLabel('字幕 1 拆分 tick',{exact:true}).fill('750');await page.getByLabel('字幕 1 拆分左文',{exact:true}).fill('你好。');await page.getByLabel('字幕 1 拆分右文',{exact:true}).fill('Hello 🌙');await page.getByRole('button',{name:'拆分字幕 1',exact:true}).click();await expect(page.getByLabel('字幕 2 文本',{exact:true})).toHaveValue('Hello 🌙');await page.getByRole('button',{name:'合并下一条字幕',exact:true}).first().click();await expect(page.getByLabel('字幕 1 文本',{exact:true})).toHaveValue('你好。\nHello 🌙');
  const downloaded=page.waitForEvent('download');await page.getByRole('button',{name:'下载 VTT',exact:true}).click();const file=await downloaded;const text=await fs.readFile((await file.path())!,'utf8');expect(text).toContain('WEBVTT');expect(text).toContain('00:00:00.000 --> 00:00:01.500');expect(text).toContain('Hello 🌙');
  for(const [width,height] of [[1366,768],[1440,900],[1920,1080]]){await page.setViewportSize({width,height});expect(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth)).toBe(true);await page.screenshot({path:info.outputPath(`voice-subtitle-${width}.png`)});}
  const current=await body(await page.request.get(`${API}/chapters/${chapter.id}`));await body(await page.request.put(`${API}/chapters/${chapter.id}`,{data:{version:current.version,content:'Changed current source'}}));await page.getByRole('button',{name:'刷新字幕来源与记录',exact:true}).click();await expect(page.getByText(/媒体、说话人或原文已变化/)).toBeVisible();await expect(page.getByRole('button',{name:'下载 VTT',exact:true})).toHaveCount(0);
 }finally{await quiesce();if(nid)expect([200,204,404]).toContain((await request.delete(`${API}/novels/${nid}`)).status());}
});
