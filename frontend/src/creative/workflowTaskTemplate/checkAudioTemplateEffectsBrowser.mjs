// Local synthetic module check: original React components and AppShell; no backend/model/processor.
import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../../..');
const evidence=resolve(process.env.AUDIO_TEMPLATE_EVIDENCE??resolve(frontend,'../../evidence/module/browser'));
await mkdir(evidence,{recursive:true});
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port:5237,strictPort:true},plugins:[{name:'audio-template-module-fixture',configureServer(s){s.middlewares.use('/audio-template-fixture',async(_q,r,next)=>{try{const html=await s.transformIndexHtml('/audio-template-fixture','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script type="module">import {mount} from "/src/creative/workflowTaskTemplate/audioTemplateEffects.visual.fixture.tsx";mount();</script></body></html>');r.setHeader('Content-Type','text/html');r.end(html);}catch(e){next(e);}});}}]});
let browser;const results=[],errors=[],forbidden=[];
try{
 await server.listen();browser=await chromium.launch({headless:true});const page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:5237'||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto('http://127.0.0.1:5237/audio-template-fixture');await page.evaluate(()=>document.fonts.ready);
  expect(await page.evaluate(()=>window.__audioTemplate.calls)).toEqual({list:0,read:0,apply:0});
  await page.getByRole('button',{name:'读取已保存工作流',exact:true}).click();await page.getByLabel('已保存工作流',{exact:true}).selectOption('graph-audio-template');await page.getByLabel('已核对的音频截取节点').selectOption('trim');
  const table=page.getByRole('table',{name:'模板参数与本次任务对照'});await expect(table.getByRole('row',{name:/增益/})).toContainText('-6 dB（本次覆盖）');
  const apply=page.getByRole('button',{name:'核对原图并应用到本次任务'});await expect(apply).toBeDisabled();const consent=page.getByLabel('确认把此版本截取与效果参数复制到本次音频卡片任务');await consent.focus();await page.keyboard.press('Space');await expect(consent).toBeChecked();await page.keyboard.press('Tab');await expect(apply).toBeFocused();await page.keyboard.press('Enter');
  const applied=page.getByRole('table',{name:'已应用模板与本次任务参数对照'});await expect(applied).toBeVisible();await expect(applied.getByText('与源模板一致',{exact:true})).toHaveCount(5);
  await page.getByLabel('夹具本次增益',{exact:true}).fill('-3');await expect(applied.getByRole('row',{name:/增益/})).toContainText('仅本次任务覆盖');await expect(applied.getByText('与源模板一致',{exact:true})).toHaveCount(4);
  const data=await page.evaluate(()=>window.__audioTemplate);expect(data.calls).toEqual({list:1,read:2,apply:1});expect(data.frozen).toBe(true);expect(data.originalUnchanged).toBe(true);expect(data.copied.parameters).toEqual({in_ms:100,out_ms:900,gain_db:-6,fade_in_ms:100,fade_out_ms:200});
  const geometry=await page.evaluate(()=>{const r=s=>{const x=document.querySelector(s).getBoundingClientRect();return {width:x.width,height:x.height};};const m=document.querySelector('.main-workspace');return{header:r('.global-header'),context:r('.context-bar'),status:r('.status-bar'),sidebar:r('.workspace-sidebar'),inspector:r('.workspace-inspector'),pageWidth:document.documentElement.scrollWidth,mainWidth:m.clientWidth,mainScrollWidth:m.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`applied-${viewport.width}x${viewport.height}.png`),fullPage:true});results.push({viewport,geometry,calls:data.calls,sourceFrozen:data.frozen,sourceUnchanged:data.originalUnchanged});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'synthetic module only; no API/CPU/job/model',results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,`browser-failure-${Date.now()}.json`),JSON.stringify({error:String(e),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
