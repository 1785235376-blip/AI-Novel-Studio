// [HERMIA-FE-20261024 M3-s1fix2] real Chrome: the execution canvas pans to the last sent node (pending reveal executed on
// first non-zero size), at 1366/1920 and zoom 1 / 1.1, after 1/6/12/13 sends from translate(-320,40); afterwards a manual
// pan survives tab switches away/back and a window resize (no re-reveal). No non-GET / model requests.
import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
const MODEL=/generat|model|llm|completion|chat|run|execute/i;
const X='[data-testid=uw-execution-canvas]';
for(const [w,h] of [[1366,768],[1920,1080]]) for(const zoom of [1,1.1]){
  const o={checks:[]};const tag=`${w}_k${zoom}`;const p=await b.newPage({viewport:{width:w,height:h}});const nonGet=[];const errs=[];const model=[];
  p.on('request',q=>{const u=q.url().replace(/^https?:\/\/[^/]+/,'');if(!u.startsWith('/api')&&!u.startsWith('/experimental'))return;if(q.method()!=='GET')nonGet.push(q.method()+' '+u);if(MODEL.test(u.replace('/experimental/workspace/tasks','')))model.push(u)});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
  await p.waitForSelector('[data-testid=uw-creative-canvas]',{timeout:15000});await p.waitForTimeout(800);
  const csvg=await (await p.$('[data-testid=uw-creative-canvas] svg[role=application]')).boundingBox();
  await p.mouse.click(csvg.x+120,csvg.y+100,{button:'right'});await p.click('[data-add-node-menu=rebuild] [data-node-type]');
  await p.click('[data-testid=uw-creative-canvas] [data-node-id] .box');await p.waitForTimeout(200);
  const creative=async()=>{await p.click('[data-testid=uw-main-tabs] [data-panel-tab=creative]');await p.waitForTimeout(200);};
  const exec=async()=>{await p.click('[data-testid=uw-main-tabs] [data-panel-tab=execution]');await p.waitForSelector(X);await p.waitForTimeout(300);};
  const send=async()=>{await creative();await p.click('button[data-action-id="canvas.sendToExecution"]');await p.waitForTimeout(450);};
  const tf=()=>p.$eval(`${X} svg g[transform]`,e=>e.getAttribute('transform'));
  const parse=s=>{const m=/translate\(([-\d.]+),([-\d.]+)\) scale\(([-\d.]+)\)/.exec(s);return {x:+m[1],y:+m[2],k:+m[3]};};
  const sbox=async()=>(await p.$(`${X} svg[role=application]`)).boundingBox();
  const drag=async(dx,dy)=>{const s=await sbox();const pt=await p.evaluate(([x0,y0,W,H])=>{for(const fy of [0.85,0.7,0.5,0.95])for(const fx of [0.5,0.35,0.65,0.2,0.8]){const x=x0+W*fx,y=y0+H*fy;const e=document.elementFromPoint(x,y);if(e&&(e.tagName==='svg'||(e.closest('svg[role=application]')&&!e.closest('[data-node-id]')&&e.tagName==='rect')))return [x,y,e.tagName];}return null;},[s.x,s.y,s.width,s.height]);
    o.dragHit=o.dragHit||pt;if(!pt)return;const [sx,sy]=pt;await p.mouse.move(sx,sy);await p.mouse.down();await p.mouse.move(sx+dx,sy+dy,{steps:6});await p.mouse.up();await p.waitForTimeout(200);};
  const panTo=async(tx,ty)=>{for(let i=0;i<3;i++){const v=parse(await tf());if(Math.abs(v.x-tx)<1&&Math.abs(v.y-ty)<1)break;await drag(tx-v.x,ty-v.y);}};
  const lastInView=()=>p.$eval(X,root=>{const s=root.querySelector('svg[role=application]').getBoundingClientRect();const ns=[...root.querySelectorAll('[data-node-id] .box')];const r=ns.at(-1).getBoundingClientRect();
    return {n:ns.length,inView:r.left>=s.left&&r.top>=s.top&&r.right<=s.right&&r.bottom<=s.bottom,box:[r.left,r.top,r.right,r.bottom].map(Math.round),svg:[s.left,s.top,s.right,s.bottom].map(Math.round)};});
  // first send, open exec, set zoom (one wheel notch at the svg's top-left keeps the origin math simple), pan to (-320,40)
  await send();await exec();
  if(zoom!==1){const s=await sbox();await p.mouse.move(s.x+1,s.y+1);await p.mouse.wheel(0,-100);await p.waitForTimeout(200);}
  let total=1;
  for(const target of [1,6,12,13]){
    await exec();await panTo(-320,40);const before=await tf();
    while(total<target){await send();total++;}
    if(target===1){await send();total++;} // the 1-node check: one more send from the panned view, counts as "send 1"
    await exec();const after=await tf();const L=await lastInView();
    o.checks.push({sent:target,nodes:L.n,before,after,zoomKept:parse(before).k===parse(after).k,lastInView:L.inView,lastBox:L.box,svg:L.svg});
    await p.screenshot({path:A+`screenshots/m3s1fix2_${tag}_sent${target}.png`});
  }
  // manual pan away, then switch tabs away/back and resize: view must not be pulled back to the last node
  await drag(-450,0);await drag(-450,0);await drag(-450,0);await p.waitForTimeout(100);const manual=await tf();
  await creative();await exec();const afterTab=await tf();
  await creative();await p.waitForTimeout(150);await exec();const afterTab2=await tf();
  await p.setViewportSize({width:w-40,height:h});await p.waitForTimeout(300);await p.setViewportSize({width:w,height:h});await p.waitForTimeout(300);const afterResize=await tf();
  o.manual={manual,afterTab,afterTab2,afterResize,notPulledBack:afterTab===manual&&afterTab2===manual&&afterResize===manual,lastStillOff:!(await lastInView()).inView};
  await p.screenshot({path:A+`screenshots/m3s1fix2_${tag}_after_manual_pan_tabs.png`});
  o.pass=o.checks.every(c=>c.lastInView&&c.zoomKept)&&o.manual.notPulledBack&&o.manual.lastStillOff&&!nonGet.length&&!model.length&&!errs.length;
  o.nonGet=nonGet;o.modelReqs=model;o.pageErrors=errs;out[tag]=o;await p.close();
}
console.log(JSON.stringify(out,null,1));await b.close();
