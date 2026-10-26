// [HERMIA-FE-20261024 M2-s1fix] real Chrome: sent node inside execution view, palette aria-disabled + 显示面板, Mod+Alt+T focus, single tasks GET.
import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
for(const [w,h] of [[1366,768],[1440,900],[1920,1080]]){
  const o={};const p=await b.newPage({viewport:{width:w,height:h}});const nonGet=[];const errs=[];const tasksGets=[];
  p.on('request',q=>{if(q.method()!=='GET')nonGet.push(q.method()+' '+q.url());if(/\/experimental\/workspace\/tasks/.test(q.url()))tasksGets.push(q.url().replace(/^https?:\/\/[^/]+/,''))});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());tasksGets.length=0;await p.reload();
  await p.waitForSelector('[data-testid=uw-creative-canvas]',{timeout:15000});await p.waitForTimeout(800);
  o.tasksGetsOnMount=[...tasksGets];
  // palette: disabled send is aria-disabled
  await p.click('.wb-command__trigger');await p.waitForSelector('[role=option]');
  o.palette=await p.$$eval('[role=option]',es=>es.filter(e=>/canvas\.|tasks\.|layout\.showPanel/.test(e.dataset.actionId)).map(e=>e.textContent+':'+(e.getAttribute('aria-disabled')||'-')));
  await p.screenshot({path:A+`screenshots/m2s1fix_${w}_palette.png`});
  await p.keyboard.press('Escape');
  // send a node
  const svg=await p.$('[data-testid=uw-creative-canvas] svg[role=application]');const bb=await svg.boundingBox();
  await p.mouse.click(bb.x+120,bb.y+100,{button:'right'});
  await p.click('[data-add-node-menu=rebuild] [data-node-type]');
  await p.click('[data-testid=uw-creative-canvas] [data-node-id] .box');await p.waitForTimeout(150);
  await p.dblclick('button[data-action-id="canvas.sendToExecution"]');await p.waitForTimeout(500);
  await p.click('[data-testid=uw-open-execution]');await p.waitForSelector('[data-testid=uw-execution-canvas]');await p.waitForTimeout(300);
  o.sent=await p.$$eval('[data-testid=uw-execution-canvas] [data-node-id^=ref-]',es=>es.map(e=>{const s=e.closest('svg').getBoundingClientRect(),r=e.getBoundingClientRect();return {n:es.length,inside:r.left>=s.left&&r.right<=s.right&&r.top>=s.top&&r.bottom<=s.bottom,node:[Math.round(r.left-s.left),Math.round(r.top-s.top),Math.round(r.width)],svg:[Math.round(s.width),Math.round(s.height)]};}));
  await p.screenshot({path:A+`screenshots/m2s1fix_${w}_sent_in_view.png`});
  // Mod+Alt+T → focus in task panel; Mod+Alt+P rotates main tabs
  await p.keyboard.press('Control+Alt+KeyT');await p.waitForTimeout(500);
  o.focusAfterT=await p.evaluate(()=>document.activeElement?.closest('[data-panel-id]')?.dataset.panelId||document.activeElement?.tagName);
  const tab=()=>p.$eval('[data-testid=uw-main-tabs] [aria-pressed=true]',e=>e.dataset.panelTab);
  o.tabBeforeP=await tab();await p.keyboard.press('Control+Alt+KeyP');await p.waitForTimeout(500);o.tabAfterP=await tab();
  await p.screenshot({path:A+`screenshots/m2s1fix_${w}_tasks_focus.png`});
  o.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  o.nonGet=nonGet;o.pageErrors=errs;out[w]=o;await p.close();
}
console.log(JSON.stringify(out,null,1));await b.close();
