import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {resolve,dirname} from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../../..'),evidence=resolve(frontend,'../../evidence/panel/browser');await mkdir(evidence,{recursive:true});
const port=5242,origin=`http://127.0.0.1:${port}`;
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port,strictPort:true},plugins:[{name:'saved-audio-panel-fixture',configureServer(s){s.middlewares.use('/audio-draft-fixture',async(_q,r,next)=>{try{r.setHeader('Content-Type','text/html');r.end(await s.transformIndexHtml('/audio-draft-fixture','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script type="module">import {mount} from "/src/creative/audioDraftRecovery/visual.fixture.tsx";mount();</script></body></html>'));}catch(e){next(e);}});}}]});
const results=[],errors=[],forbidden=[];let browser;
try{
 await server.listen();browser=await chromium.launch({headless:true});const page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!==origin||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto(origin+'/audio-draft-fixture');await page.evaluate(()=>document.fonts.ready);
  async function select(){await page.getByRole('button',{name:'读取已保存音频输入草稿'}).click();await page.getByLabel('已保存的音频输入草稿',{exact:true}).selectOption('saved-audio');}
  await select();const apply=page.getByRole('button',{name:'明确仅恢复音频输入草稿'});await expect(apply).toBeDisabled();const consent=page.getByRole('checkbox',{name:'我已核对所选版本与来源，同意用已保存草稿替换当前会话输入'});
  await consent.focus();await page.keyboard.press('Space');await expect(apply).toBeEnabled();await page.getByRole('button',{name:'修改当前会话输入'}).click();await page.getByRole('button',{name:'修改当前会话输入'}).click();await expect(page.getByLabel('已保存的音频输入草稿',{exact:true})).toHaveCount(0);expect(await page.evaluate(()=>window.__audioDraftPanel.calls.resume)).toBe(0);
  await select();await consent.focus();await page.keyboard.press('Space');await page.keyboard.press('Tab');await expect(apply).toBeFocused();await page.keyboard.press('Enter');await expect(page.getByText(/已提交仅恢复输入的意图/)).toBeVisible();await expect(apply).toBeDisabled();
  const data=await page.evaluate(()=>window.__audioDraftPanel);expect(data.calls).toEqual({list:2,resume:1});expect(data.restored[0]).toMatchObject({gainDb:-6.5,fadeInMs:200,fadeOutMs:300,sourceVersion:3,templateVersion:5});
  const geometry=await page.evaluate(()=>{const box=s=>{const r=document.querySelector(s).getBoundingClientRect();return{width:r.width,height:r.height};};const main=document.querySelector('.main-workspace');return{header:box('.global-header'),context:box('.context-bar'),sidebar:box('.workspace-sidebar'),inspector:box('.workspace-inspector'),status:box('.status-bar'),width:document.documentElement.scrollWidth,mainWidth:main.clientWidth,mainScroll:main.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.status.height).toBe(32);expect(geometry.width).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScroll).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`audio-draft-${viewport.width}x${viewport.height}.png`),fullPage:true});results.push({viewport,geometry,calls:data.calls,restored:data.restored});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'pure checked summaries and callbacks; no server owner/CPU/model',results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,'failure.json'),JSON.stringify({error:String(e),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
