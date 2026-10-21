// UI-only component check with synthetic input rows. No processing/network/dispatch.
import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../../..'),evidence=resolve(frontend,'../../evidence/panel/browser');
await mkdir(evidence,{recursive:true});
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port:5206,strictPort:true},plugins:[{name:'saved-video-input-check',configureServer(s){s.middlewares.use('/saved-video-draft-fixture',async(_q,r,next)=>{try{const html=await s.transformIndexHtml('/saved-video-draft-fixture','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script type="module">import {mount} from "/src/creative/videoDraftRecovery/visual.fixture.tsx";mount();</script></body></html>');r.setHeader('Content-Type','text/html');r.end(html);}catch(e){next(e);}});}}]});
let browser;const results=[],errors=[],forbidden=[];
try{
 await server.listen();browser=await chromium.launch({headless:true});const page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:5206'||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto('http://127.0.0.1:5206/saved-video-draft-fixture');await page.evaluate(()=>document.fonts.ready);
  expect(await page.evaluate(()=>window.__savedVideoDraft.calls)).toEqual({list:0,resume:0});
  await page.getByRole('button',{name:'读取已保存视频输入草稿'}).click();await page.getByLabel('已保存的视频输入草稿').selectOption('saved-video-draft');
  const button=page.getByRole('button',{name:'明确仅恢复输入草稿'});await expect(button).toBeDisabled();const consent=page.getByLabel('我已核对所选版本与来源，仅恢复输入草稿');await consent.focus();await page.keyboard.press('Space');await expect(consent).toBeChecked();await expect(button).toBeEnabled();await page.keyboard.press('Tab');await expect(button).toBeFocused();
  expect(await page.evaluate(()=>window.__savedVideoDraft.calls)).toEqual({list:1,resume:0});
  const geometry=await page.evaluate(()=>{const r=s=>{const x=document.querySelector(s).getBoundingClientRect();return {width:x.width,height:x.height};};const m=document.querySelector('.main-workspace');return{header:r('.global-header'),context:r('.context-bar'),status:r('.status-bar'),sidebar:r('.workspace-sidebar'),inspector:r('.workspace-inspector'),pageWidth:document.documentElement.scrollWidth,mainWidth:m.clientWidth,mainScrollWidth:m.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`saved-video-input-${viewport.width}x${viewport.height}.png`),fullPage:true});
  await page.keyboard.press('Enter');await expect.poll(()=>page.evaluate(()=>window.__savedVideoDraft.calls.resume)).toBe(1);await expect(button).toBeDisabled();results.push({viewport,geometry,calls:await page.evaluate(()=>window.__savedVideoDraft.calls)});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'synthetic UI-only input rows; no Job, API, CPU, model or dispatch',results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,'browser-failure.json'),JSON.stringify({error:String(e),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
