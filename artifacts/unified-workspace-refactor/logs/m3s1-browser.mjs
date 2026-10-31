// [HERMIA-FE-20261024 M3-s1] real Chrome: creative/execution selection → inspector, rename via inspector (local draft, read back),
// exec pan/zoom kept across sends, 4+ sent nodes do not overlap, no non-GET / model requests.
import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
const MODEL=/generat|model|llm|completion|chat|run|execute/i;
for(const [w,h] of [[1366,768],[1440,900],[1920,1080]]){
  const o={};const p=await b.newPage({viewport:{width:w,height:h}});const nonGet=[];const errs=[];const model=[];
  p.on('request',q=>{const u=q.url().replace(/^https?:\/\/[^/]+/,'');if(!u.startsWith('/api')&&!u.startsWith('/experimental'))return;if(q.method()!=='GET')nonGet.push(q.method()+' '+u);if(MODEL.test(u.replace('/experimental/workspace/tasks','')))model.push(u)});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
  await p.waitForSelector('[data-testid=uw-creative-canvas]',{timeout:15000});await p.waitForTimeout(800);
  const svg=await p.$('[data-testid=uw-creative-canvas] svg[role=application]');const bb=await svg.boundingBox();
  await p.mouse.click(bb.x+120,bb.y+100,{button:'right'});await p.click('[data-add-node-menu=rebuild] [data-node-type]');
  await p.click('[data-testid=uw-creative-canvas] [data-node-id] .box');await p.waitForTimeout(200);
  o.inspCreative=await p.$eval('[data-testid=uw-node-inspector]',e=>({canvas:e.dataset.canvas,title:e.querySelector('input').value,type:e.querySelector('[data-testid=uw-node-type]').textContent}));
  await p.fill('[data-testid=uw-node-inspector] input','雾港封面·夜');await p.click('[data-testid=uw-node-inspector] button[type=submit]');await p.waitForTimeout(300);
  o.saveMsg=await p.textContent('[data-testid=uw-node-msg]');
  o.canvasTitle=await p.textContent('[data-testid=uw-creative-canvas] [data-node-id] .ttl');
  o.stillSelected=await p.$eval('[data-testid=uw-creative-canvas] [data-node-id]',e=>e.dataset.sel);
  await p.screenshot({path:A+`screenshots/m3s1_${w}_creative_inspector.png`});
  // first send, then zoom the execution canvas, then 4 more sends → viewport kept, no overlaps
  const send=async()=>{await p.click('[data-testid=uw-main-tabs] [data-panel-tab=creative]');await p.waitForTimeout(150);await p.click('button[data-action-id="canvas.sendToExecution"]');await p.waitForTimeout(450);};
  await send();await p.click('[data-testid=uw-open-execution]');await p.waitForSelector('[data-testid=uw-execution-canvas]');
  const es=await (await p.$('[data-testid=uw-execution-canvas] svg[role=application]')).boundingBox();
  await p.mouse.move(es.x+es.width-40,es.y+es.height-40);await p.mouse.down();await p.mouse.move(es.x+es.width-100,es.y+es.height-70,{steps:5});await p.mouse.up();await p.waitForTimeout(200);
  const tf=()=>p.$eval('[data-testid=uw-execution-canvas] svg g[transform]',e=>e.getAttribute('transform'));
  o.execTfBefore=await tf();
  for(let i=0;i<6;i++)await send();
  await p.click('[data-testid=uw-open-execution]');await p.waitForSelector('[data-testid=uw-execution-canvas]');await p.waitForTimeout(200);
  o.execTfAfter=await tf();
  const rects=await p.$$eval('[data-testid=uw-execution-canvas] [data-node-id] .box',es=>es.map(e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]}));
  o.sentCount=rects.length;o.overlaps=0;for(let i=0;i<rects.length;i++)for(let j=i+1;j<rects.length;j++){const a=rects[i],c=rects[j];if(a[0]<c[2]&&c[0]<a[2]&&a[1]<c[3]&&c[1]<a[3])o.overlaps++;}
  const sv=await p.$eval('[data-testid=uw-execution-canvas] svg[role=application]',e=>{const r=e.getBoundingClientRect();return [r.left,r.top,r.right,r.bottom]});
  o.first3InView=rects.slice(0,3).every(r=>r[0]>=sv[0]&&r[1]>=sv[1]&&r[2]<=sv[2]&&r[3]<=sv[3]);
  await p.click('[data-testid=uw-execution-canvas] [data-node-id] .box');await p.waitForTimeout(200);
  o.inspExec=await p.$eval('[data-testid=uw-node-inspector]',e=>({canvas:e.dataset.canvas,title:e.querySelector('input').value,type:e.querySelector('[data-testid=uw-node-type]').textContent}));
  await p.screenshot({path:A+`screenshots/m3s1_${w}_execution_inspector.png`});
  o.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  o.nonGet=nonGet;o.modelReqs=model;o.pageErrors=errs;out[w]=o;await p.close();
}
console.log(JSON.stringify(out,null,1));await b.close();
