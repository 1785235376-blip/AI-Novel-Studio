// Local actual-panel UI check with explicitly synthetic responses. No API/model/processor.
import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../..'),evidence=resolve(frontend,'../../evidence/task-entry-browser');
await mkdir(evidence,{recursive:true});
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port:5238,strictPort:true},plugins:[{name:'cycle2-original-entry',configureServer(s){s.middlewares.use('/cycle2-fixture',async(_q,r,next)=>{try{const html=await s.transformIndexHtml('/cycle2-fixture?template-effects=1','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><script type="module">import {mount} from "/src/creative/dualCanvasCycle2.visual.fixture.tsx";mount();</script></body></html>');r.setHeader('Content-Type','text/html');r.end(html);}catch(e){next(e);}});}}]});
let browser;const results=[],errors=[],forbidden=[];
try{
 await server.listen();browser=await chromium.launch({headless:true});const page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:5238'||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 async function impact(){const check=page.getByLabel('已核对本次输入变化与影响范围');await expect(check).toBeEnabled();await check.focus();await page.keyboard.press('Space');await expect(check).toBeChecked();await page.getByRole('button',{name:'确认本次输入核对'}).click();}
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto('http://127.0.0.1:5238/cycle2-fixture?template-effects=1');await page.evaluate(()=>document.fonts.ready);
  await page.getByRole('button',{name:'读取已保存工作流',exact:true}).click();await page.getByLabel('已保存工作流',{exact:true}).selectOption('graph-audio-template');await page.getByLabel('已核对的音频截取节点').selectOption('trim');
  const apply=page.getByRole('button',{name:'核对原图并应用到本次任务'});await expect(apply).toBeDisabled();const consent=page.getByLabel('确认把此版本截取与效果参数复制到本次音频卡片任务');await consent.focus();await page.keyboard.press('Space');await expect(apply).toBeEnabled();await page.keyboard.press('Tab');await expect(apply).toBeFocused();await page.keyboard.press('Enter');
  await expect(page.getByLabel('来源起点（毫秒）',{exact:true})).toHaveValue('100');await expect(page.getByLabel('来源终点（毫秒）',{exact:true})).toHaveValue('900');
  await expect(page.getByLabel('本任务增益（-60–12 dB，可选）',{exact:true})).toHaveValue('-6.5');
  const comparison=page.getByRole('table',{name:'已应用模板与本次任务参数对照'});await expect(comparison.getByRole('row').filter({hasText:'增益'})).toContainText('与源模板一致');
  await page.getByLabel('本任务增益（-60–12 dB，可选）',{exact:true}).fill('-3.5');
  await expect(comparison.getByRole('row').filter({hasText:'增益'})).toContainText('仅本次任务覆盖');
  await expect(page.getByLabel('本任务淡入时长（毫秒，可选）',{exact:true})).toHaveValue('100');
  await expect(page.getByLabel('本任务淡出时长（毫秒，可选）',{exact:true})).toHaveValue('200');
  const geometry=await page.evaluate(()=>{const r=s=>{const x=document.querySelector(s).getBoundingClientRect();return {width:x.width,height:x.height};};const m=document.querySelector('.main-workspace');return{header:r('.global-header'),context:r('.context-bar'),status:r('.status-bar'),sidebar:r('.workspace-sidebar'),inspector:r('.workspace-inspector'),pageWidth:document.documentElement.scrollWidth,mainWidth:m.clientWidth,mainScrollWidth:m.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`task-${viewport.width}x${viewport.height}.png`),fullPage:true});
  await page.getByRole('button',{name:'读取制作预览',exact:true}).click();await page.getByLabel('已核对本次输入、来源和处理边界').check();await impact();await page.getByRole('button',{name:'仅创建任务并入队'}).click();
  await expect(page.getByRole('button',{name:'明确执行当前入队任务'})).toBeDisabled();await impact();await page.getByRole('button',{name:'明确执行当前入队任务'}).click();
  await expect.poll(()=>page.evaluate(()=>window.__cycle2.calls.execute)).toBe(1);const data=await page.evaluate(()=>window.__cycle2);expect(data.calls.create).toBe(1);expect(data.commands[0].template_ref.graph_version).toBe(3);expect(data.commands[0].parameters).toEqual({in_ms:100,out_ms:900,gain_db:-3.5,fade_in_ms:100,fade_out_ms:200});results.push({viewport,geometry,calls:data.calls,templatePin:data.commands[0].template_ref});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'synthetic UI responses; actual CPU in separate backend tests',results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,recoveryPaths:0,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,'browser-failure.json'),JSON.stringify({error:String(e),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
