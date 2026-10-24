// [HERMIA-FE-20261024 M4-s1] real Chrome: 3 widths × browser zoom 80/100/125/150/200 (CSS viewport = w/zoom, DPR = zoom),
// overflow, main ≥320×200, toolbar fits; keyboard: skip link, Tab order, tab arrows, splitter keys, Esc.
import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt-m4/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt-m4/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
for(const [w,h] of [[1366,768],[1440,900],[1920,1080]]) for(const z of [0.8,1,1.25,1.5,2]){
  const p=await b.newPage({viewport:{width:Math.floor(w/z),height:Math.floor(h/z)},deviceScaleFactor:z});const nonGet=[];const errs=[];
  p.on('request',q=>{const u=q.url();if(/\/(api|experimental)\//.test(u)&&q.method()!=='GET')nonGet.push(q.method()+' '+u)});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4310/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
  await p.waitForSelector('[data-testid=dock-layout]',{timeout:15000});await p.waitForTimeout(900);
  const o=await p.evaluate(()=>{const m=document.querySelector('[data-testid=main-zone]').getBoundingClientRect();const t=document.querySelector('.uw-toolbar');
    const kids=[...t.children].map(e=>e.getBoundingClientRect());
    return {hOverflow:document.documentElement.scrollWidth>innerWidth,main:[Math.round(m.width),Math.round(m.height)],toolbarFits:kids.every(k=>k.right<=innerWidth+1),toolbarH:Math.round(t.getBoundingClientRect().height)};});
  o.mainOk=o.main[0]>=320&&o.main[1]>=200;
  const tag=`${w}_z${Math.round(z*100)}`;
  if(z===1){
    o.initialFocus=await p.evaluate(()=>document.activeElement?.textContent);await p.keyboard.press('Shift+Tab');o.shiftTabFromInitial=await p.evaluate(()=>document.activeElement?.textContent);
    o.firstTabStopIsSkip=await p.evaluate(()=>document.activeElement?.dataset.testid==='uw-skip-main');const sk=await p.$eval('[data-testid=uw-skip-main]',e=>{const r=e.getBoundingClientRect();return r.top>=0&&getComputedStyle(e).outlineStyle!=='none'});o.skipVisibleWithRing=sk;
    await p.screenshot({path:A+`screenshots/m4s1_${w}_skipfocus.png`});
    await p.keyboard.press('Enter');o.afterSkip=await p.evaluate(()=>document.activeElement?.id);
    const order=[];await p.focus('[data-testid=uw-skip-main]');for(let i=0;i<14;i++){await p.keyboard.press('Tab');order.push(await p.evaluate(()=>{const a=document.activeElement;return (a.getAttribute('role')||a.tagName)+':'+(a.getAttribute('aria-label')||a.textContent||'').trim().slice(0,12)}));}o.tabOrder=order;
    await p.focus('[data-testid=uw-main-tabs] [role=tab][tabindex="0"]');const t0=await p.evaluate(()=>document.activeElement.dataset.panelTab);
    o.tabRing=await p.evaluate(()=>getComputedStyle(document.activeElement).outlineStyle);
    await p.keyboard.press('ArrowRight');await p.waitForTimeout(500);
    o.tabArrow=await p.evaluate(()=>({from:null,to:document.activeElement.dataset.panelTab,selected:document.activeElement.getAttribute('aria-selected')}));o.tabArrow.from=t0;
    await p.focus('[data-testid=resize-outline]');const v0=await p.$eval('[data-testid=resize-outline]',e=>+e.getAttribute('aria-valuenow'));
    await p.keyboard.press('ArrowRight');await p.keyboard.press('ArrowRight');const v1=await p.$eval('[data-testid=resize-outline]',e=>+e.getAttribute('aria-valuenow'));
    await p.keyboard.press('End');const vmax=await p.$eval('[data-testid=resize-outline]',e=>[+e.getAttribute('aria-valuenow'),+e.getAttribute('aria-valuemax')]);
    await p.keyboard.press('Home');o.splitter={v0,v1,end:vmax,home:await p.$eval('[data-testid=resize-outline]',e=>+e.getAttribute('aria-valuenow'))};
    await p.screenshot({path:A+`screenshots/m4s1_${w}_splitterfocus.png`});
    const sb=await (await p.$('[data-testid=resize-outline]')).boundingBox();const before=o.splitter.home;
    await p.mouse.move(sb.x+2,sb.y+100);await p.mouse.down();await p.mouse.move(sb.x+80,sb.y+100,{steps:4});o.midDrag=await p.$eval('[data-testid=resize-outline]',e=>+e.getAttribute('aria-valuenow'));await p.keyboard.press('Escape');await p.mouse.up();
    o.escResize={before,after:await p.$eval('[data-testid=resize-outline]',e=>+e.getAttribute('aria-valuenow'))};
    const okMain=await p.evaluate(()=>{const m=document.querySelector('[data-testid=main-zone]').getBoundingClientRect();return [m.width,m.height]});o.mainAfter=okMain.map(Math.round);
  }
  await p.screenshot({path:A+`screenshots/m4s1_${tag}.png`});
  o.nonGet=nonGet;o.pageErrors=errs;out[tag]=o;await p.close();
}
console.log(JSON.stringify(out,null,1));await b.close();
