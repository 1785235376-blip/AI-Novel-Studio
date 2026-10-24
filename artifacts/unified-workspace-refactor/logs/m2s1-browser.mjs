// [HERMIA-FE-20261024 M2-s1] real Chrome check of the ?uw=1 preview: real panels, N5 exec entry, N4 CSS-zoom clamp.
import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
for(const [w,h] of [[1366,768],[1440,900],[1920,1080]]){
  const o={};const p=await b.newPage({viewport:{width:w,height:h}});const nonGet=[];const errs=[];const urls=[];
  p.on('request',q=>{urls.push(q.method()+' '+q.url().replace(/^https?:\/\/[^/]+/,''));if(q.method()!=='GET')nonGet.push(q.method()+' '+q.url())});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
  await p.waitForSelector('[data-testid=uw-creative-canvas]',{timeout:15000});
  o.placeholders=await p.$$eval('[data-state=not-connected]',es=>es.map(e=>e.textContent));
  o.panels=await p.$$eval('[data-testid^=panel-]',es=>es.map(e=>e.dataset.testid+':'+e.dataset.dock));
  o.tabs=await p.$$eval('[data-testid=uw-main-tabs] button',es=>es.map(e=>e.textContent+':'+e.getAttribute('aria-pressed')));
  o.sendReason=await p.textContent('[data-testid=uw-send-reason]').catch(()=>null);
  o.tasksText=(await p.innerText('[data-testid=panel-tasks]')).slice(0,160);
  await p.screenshot({path:A+`screenshots/m2s1_${w}_real_panels.png`});
  // add a node on the creative canvas (local), select it, send to execution
  const svg=await p.$('[data-testid=uw-creative-canvas] svg[role=application]');const bb=await svg.boundingBox();
  await p.mouse.click(bb.x+120,bb.y+100,{button:'right'});
  await p.click('[data-add-node-menu=rebuild] [data-node-type]');
  await p.click('[data-testid=uw-creative-canvas] [data-node-id] .box');await p.waitForTimeout(150);
  o.sendEnabled=await p.$eval('button[data-action-id="canvas.sendToExecution"]',e=>!e.disabled);
  await p.dblclick('button[data-action-id="canvas.sendToExecution"]');await p.waitForTimeout(500);
  o.status=await p.textContent('[data-testid=uw-studio-status]').catch(()=>null);
  await p.click('[data-testid=uw-open-execution]');await p.waitForSelector('[data-testid=uw-execution-canvas]');await p.waitForTimeout(200);
  o.execNodes=await p.$$eval('[data-testid=uw-execution-canvas] [data-node-id]',es=>es.length);
  o.tabsAfter=await p.$$eval('[data-testid=uw-main-tabs] button',es=>es.map(e=>e.textContent+':'+e.getAttribute('aria-pressed')));
  await p.screenshot({path:A+`screenshots/m2s1_${w}_exec_canvas.png`});
  // N4: float the inspector to the lower right, then apply CSS zoom 2 on <html>
  await p.selectOption('[aria-label="「章节属性」停靠位置"]','float');await p.waitForTimeout(200);
  const hd=await (await p.$('[data-testid=drag-inspector]')).boundingBox();
  await p.mouse.move(hd.x+20,hd.y+10);await p.mouse.down();await p.mouse.move(w*0.7,h*0.75,{steps:6});await p.mouse.up();await p.waitForTimeout(200);
  const rect=()=>p.$eval('[data-testid=panel-inspector]',e=>{const r=e.getBoundingClientRect();return {dock:e.dataset.dock,left:e.style.left,top:e.style.top,right:Math.round(r.left+48),bottom:Math.round(r.top+48),iw:innerWidth,ih:innerHeight};});
  o.floatBefore=await rect();
  await p.evaluate(()=>{document.documentElement.style.zoom='2';});await p.waitForTimeout(400);
  o.floatZoom2=await rect();
  // Chrome (standardized CSS zoom) reports getBoundingClientRect in window px: 48px header corner must be inside the window.
  o.floatZoom2.headerVisible=o.floatZoom2.right<=o.floatZoom2.iw&&o.floatZoom2.bottom<=o.floatZoom2.ih;
  o.floatBefore.headerVisible=o.floatBefore.right<=o.floatBefore.iw&&o.floatBefore.bottom<=o.floatBefore.ih;
  await p.screenshot({path:A+`screenshots/m2s1_${w}_zoom200_float.png`});
  await p.evaluate(()=>{document.documentElement.style.zoom='';});await p.waitForTimeout(300);
  o.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  o.nonGet=nonGet;o.pageErrors=errs;o.modelish=urls.filter(u=>!u.startsWith('GET /src/')&&!u.startsWith('GET /node_modules/')&&/generat|llm|completion|\/run\b|execute/i.test(u));out[w]=o;await p.close();
}
console.log(JSON.stringify(out,null,1));await b.close();
