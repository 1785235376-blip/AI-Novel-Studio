// Local original-panel replay of generated CPU evidence. No processor/API/model in this browser test.
import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {createHash} from 'node:crypto';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../..'),evidence=resolve(frontend,'../../evidence/browser');
const capture=JSON.parse(await readFile(process.env.STUDIO_VIDEO_RECOVERY_CAPTURE??resolve(evidence,'../backend/native-derived.json'),'utf8'));
await mkdir(evidence,{recursive:true});
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port:5203,strictPort:true},plugins:[{name:'video-failed-original-entry',configureServer(s){s.middlewares.use('/video-recovery-fixture',async(_q,r,next)=>{try{const html=await s.transformIndexHtml('/video-recovery-fixture','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script>window.__videoRecoveryNative='+JSON.stringify(capture).replaceAll('<','\\u003c')+'</script><script type="module">import {mount} from "/src/creative/videoRecovery.visual.fixture.tsx";mount();</script></body></html>');r.setHeader('Content-Type','text/html');r.end(html);}catch(e){next(e);}});}}]});
let browser,page;const results=[],errors=[],forbidden=[];
try{
 await server.listen();browser=await chromium.launch({headless:true});page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:5203'||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 async function impact(){const check=page.getByLabel('已核对本次输入变化与影响范围');await expect(check).toBeEnabled();await check.focus();await page.keyboard.press('Space');await expect(check).toBeChecked();await page.getByRole('button',{name:'确认本次输入核对'}).click();}
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto('http://127.0.0.1:5203/video-recovery-fixture');await page.evaluate(()=>document.fonts.ready);
  const derive=page.getByRole('button',{name:'派生新的预览草稿',exact:true});await expect(derive).toBeDisabled();const consent=page.getByLabel('我已核对原失败记录、视频范围、音轨选择和原画布位置，准备一个新草稿');await consent.focus();await page.keyboard.press('Space');await expect(derive).toBeEnabled();await page.keyboard.press('Tab');await expect(derive).toBeFocused();await page.keyboard.press('Enter');
  expect(await page.evaluate(()=>window.__videoRecovery.calls)).toMatchObject({save:0,queue:0,execute:0,review:0});
  await expect(page.getByText('本次派生来源：',{exact:false})).toBeVisible();
  await page.getByLabel('来源终点（毫秒）',{exact:true}).fill(String(capture.derived_command.parameters.out_ms));await page.getByRole('button',{name:'应用截取配置',exact:true}).click();
  await expect(page.getByRole('button',{name:'读取视频截取预览',exact:true})).toBeEnabled();await page.getByRole('button',{name:'读取视频截取预览',exact:true}).click();await page.getByLabel('已核对本次视频范围、来源和重新编码边界').check();await impact();await page.getByRole('button',{name:'仅创建视频任务并入队'}).click();
  const execute=page.getByRole('button',{name:'明确执行本次视频截取',exact:true});await expect(execute).toBeDisabled();await expect(page.getByRole('button',{name:'读取视频截取预览',exact:true})).toBeEnabled();await page.getByRole('button',{name:'读取视频截取预览',exact:true}).click();await page.getByLabel('已核对本次视频范围、来源和重新编码边界').check();await impact();await execute.click();
  await page.getByRole('button',{name:'读取并核对候选视频'}).click();
  const review=page.getByLabel('已查看本次视频候选，确认审核当前 Job 版本与输出摘要');await expect(review).toBeEnabled();
  const decoded=await page.locator('video').evaluate(v=>({width:v.videoWidth,height:v.videoHeight,duration:v.duration,readyState:v.readyState}));expect(decoded.width).toBe(capture.executed.media_measurement.width);expect(decoded.height).toBe(capture.executed.media_measurement.height);expect(Math.abs(decoded.duration*1000-capture.executed.media_measurement.duration_ms)).toBeLessThanOrEqual(120);
  const geometry=await page.evaluate(()=>{const r=s=>{const x=document.querySelector(s).getBoundingClientRect();return{width:x.width,height:x.height};};const m=document.querySelector('.main-workspace');return{header:r('.global-header'),context:r('.context-bar'),status:r('.status-bar'),sidebar:r('.workspace-sidebar'),inspector:r('.workspace-inspector'),pageWidth:document.documentElement.scrollWidth,mainWidth:m.clientWidth,mainScrollWidth:m.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`video-recovery-${viewport.width}x${viewport.height}.png`),fullPage:true});
  await review.check();await page.getByRole('button',{name:'明确审核视频并入素材库'}).click();
  await expect.poll(()=>page.evaluate(()=>window.__videoRecovery.calls.review)).toBe(1);const calls=await page.evaluate(()=>window.__videoRecovery.calls);expect(calls).toMatchObject({save:1,preview:2,queue:1,execute:1,candidate:1,review:1});results.push({viewport,geometry,decoded,calls});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'replayed native CPU DTOs; actual browser H264 decode; no real API in browser',candidate_sha256:createHash('sha256').update(Buffer.from(capture.candidate_base64,'base64')).digest('hex'),results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,decoded:true,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,'browser-failure.json'),JSON.stringify({error:String(e),body:await page?.locator('body').innerText(),calls:await page?.evaluate(()=>window.__videoRecovery),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
