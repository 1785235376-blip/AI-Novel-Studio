// Actual React/SDK/return/history UI with replayed owned CPU receipts. Does not call the CPU service.
import {createServer} from 'vite';
import {chromium,expect} from '@playwright/test';
import {mkdir,writeFile,readFile} from 'node:fs/promises';
import {dirname,resolve} from 'node:path';
import {fileURLToPath} from 'node:url';
const composite=process.argv.includes('--composite');
const frontend=resolve(dirname(fileURLToPath(import.meta.url)),'../..'),root=resolve(frontend,'../..'),evidence=resolve(root,composite?'evidence/browser-composite':'evidence/browser');
const capture=JSON.parse(await readFile(resolve(root,composite?'evidence/tests/native/card-composite.json':'evidence/tests/native/card-cutout-png.json'),'utf8'));
await mkdir(evidence,{recursive:true});
const server=await createServer({root:frontend,configFile:resolve(frontend,'vite.config.ts'),cacheDir:resolve(evidence,'vite-cache'),server:{host:'127.0.0.1',port:5243,strictPort:true},plugins:[{name:'mask-card-entry',configureServer(s){s.middlewares.use('/mask-fixture',async(_q,r,next)=>{try{const html=await s.transformIndexHtml('/mask-fixture','<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"></head><body><div id="root"></div><script>window.__maskNative='+JSON.stringify(capture).replaceAll('<',String.fromCharCode(92)+'u003c')+';</script><script type="module">import {mount} from "/src/creative/canvasImageMask.visual.fixture.tsx";mount();</script></body></html>');r.setHeader('Content-Type','text/html');r.end(html);}catch(e){next(e);}});}}]});
let browser,page;const results=[],errors=[],forbidden=[];
try{
 await server.listen();browser=await chromium.launch({headless:true});page=await browser.newPage({locale:'zh-CN',reducedMotion:'reduce'});page.on('pageerror',e=>errors.push(String(e)));
 await page.route('**/*',route=>{const u=new URL(route.request().url());if(u.origin!=='http://127.0.0.1:5243'||u.pathname.startsWith('/api/')){forbidden.push(u.pathname);return route.abort();}return route.continue();});
 async function impact(){const check=page.getByLabel('已核对本次输入变化与影响范围');await expect(check).toBeEnabled();await check.focus();await page.keyboard.press('Space');await expect(check).toBeChecked();await page.getByRole('button',{name:'确认本次输入核对'}).click();}
 for(const viewport of [{width:1366,height:768},{width:1440,height:900},{width:1920,height:1080}]){
  await page.setViewportSize(viewport);await page.goto('http://127.0.0.1:5243/mask-fixture');await page.evaluate(()=>document.fonts.ready);
  await writeFile(resolve(evidence,'initial-dom.html'),await page.content());await page.getByRole('combobox',{name:/^操作/}).selectOption(composite?'m5.image.composite':'m5.image.cutout');
  if(composite){
   await page.getByLabel(`${capture.secondary.filename} · v${capture.secondary.version}`).check();
   await expect(page.getByText(/固定在像素原点/).first()).toBeVisible();
   await page.getByLabel('第 1 层透明度（0–255）').fill('73');await page.getByLabel('第 1 层透明度（0–255）').fill('255');
   await page.getByLabel('显示第 2 层').uncheck();await page.getByLabel('显示第 2 层').check();
   await page.getByRole('button',{name:'交换上下层'}).click();await page.getByRole('button',{name:'交换上下层'}).click();
  }else{
   await expect(page.getByText(/不执行 AI 自动语义分割/).first()).toBeVisible();
   await page.getByRole('combobox',{name:/^绑定当前来源版本的遮罩/}).selectOption(capture.mask.id);
  }
  await expect(page.getByLabel(`${capture.source.filename} · v${capture.source.version}`)).toBeDisabled();
  const geometry=await page.evaluate(()=>{const r=s=>{const x=document.querySelector(s).getBoundingClientRect();return{width:x.width,height:x.height};};const m=document.querySelector('.main-workspace');return{header:r('.global-header'),context:r('.context-bar'),status:r('.status-bar'),sidebar:r('.workspace-sidebar'),inspector:r('.workspace-inspector'),pageWidth:document.documentElement.scrollWidth,mainWidth:m.clientWidth,mainScrollWidth:m.scrollWidth};});
  expect(geometry.header.height).toBe(56);expect(geometry.context.height).toBe(44);expect(geometry.status.height).toBe(32);expect(geometry.sidebar.width).toBe(248);expect(geometry.inspector.width).toBe(340);expect(geometry.pageWidth).toBeLessThanOrEqual(viewport.width);expect(geometry.mainScrollWidth).toBeLessThanOrEqual(geometry.mainWidth);
  await page.screenshot({path:resolve(evidence,`task-${viewport.width}x${viewport.height}.png`),fullPage:true});
  await page.getByRole('button',{name:'读取制作预览',exact:true}).click();await page.getByLabel('已核对本次输入、来源和处理边界').check();await impact();
  await page.getByRole('button',{name:'仅创建任务并入队'}).click();const execute=page.getByRole('button',{name:'明确执行当前入队任务'});await expect(execute).toBeDisabled();await impact();await execute.click();
  await page.getByRole('button',{name:'读取并核对候选媒体'}).click();await expect(page.getByAltText('本任务经摘要核对的图片候选')).toBeVisible();
  await page.getByLabel('已查看本次候选，确认采用当前任务版本与输出摘要').check();await page.getByRole('button',{name:'明确审核并入素材库'}).click();
  await page.getByRole('button',{name:'核验原位置与正式审核结果'}).click();await page.getByLabel('确认只采用到上述原卡片').check();await page.getByRole('button',{name:'确认采用并回填原卡片'}).click();
  await expect(page.getByLabel('原卡片当前版本')).toContainText('v2');await page.getByText('画布版本历史与恢复',{exact:true}).click();await page.getByRole('button',{name:'读取画布版本历史'}).click();
  await page.getByLabel('待恢复画布版本',{exact:true}).selectOption('1');
  await page.getByLabel('确认创建新的当前版本并退役旧预览').check();
  const restore=page.getByRole('button',{name:'恢复此画布版本为新版本'});await restore.click();await expect(page.getByLabel('原卡片当前版本')).toContainText('v3');
  const data=await page.evaluate(()=>window.__maskCheck);expect(data.calls.create).toBe(1);expect(data.calls.execute).toBe(1);expect(data.calls.review).toBe(1);expect(data.calls.save).toBe(1);expect(data.calls.restore).toBe(1);expect(data.commands[0].source_snapshots.map(x=>x.id)).toEqual([capture.source.id,(capture.mask??capture.secondary).id]);results.push({viewport,geometry,calls:data.calls});
 }
 expect(errors).toEqual([]);expect(forbidden).toEqual([]);await writeFile(resolve(evidence,'browser-check.json'),JSON.stringify({status:'PASS',boundary:'replayed owned CPU receipts; live CPU service NOT_RUN in browser',results,errors,forbidden},null,2));console.log(JSON.stringify({status:'PASS',desktopPaths:3,errors,forbidden}));
}catch(e){await writeFile(resolve(evidence,'failure-dom.html'),await page?.content()??'');await page?.screenshot({path:resolve(evidence,'failure.png'),fullPage:true});await writeFile(resolve(evidence,'browser-failure.json'),JSON.stringify({error:String(e),results,errors,forbidden},null,2));throw e;}finally{await browser?.close();await server.close();}
