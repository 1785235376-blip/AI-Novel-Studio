import {createRequire} from 'module';
const require=createRequire('/workspace/hr/wt-m4/frontend/');
const {chromium}=require('playwright-core');
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome',args:['--no-sandbox']});
const out=[];
for (const [w,h] of [[1366,768],[1440,900],[1920,1080]]){
  const p=await b.newPage({viewport:{width:w,height:h}});
  await p.route('**/*',r=>['GET','HEAD','OPTIONS'].includes(r.request().method())?r.continue():r.abort());
  await p.goto('http://localhost:4310/?uw=1',{waitUntil:'networkidle'}).catch(()=>{});
  await p.waitForSelector('[data-testid="uw-skip-main"]',{timeout:30000,state:'attached'});
  await p.keyboard.press('Tab');
  const r=await p.evaluate(()=>{
    const s=document.querySelector('[data-testid="uw-skip-main"]'); const t=[...document.querySelectorAll('button')].find(x=>x.textContent.includes('搜索功能'));
    const a=s.getBoundingClientRect(), c=t?.getBoundingClientRect();
    const ov=c? !(a.right<=c.left||a.left>=c.right||a.bottom<=c.top||a.top>=c.bottom):null;
    return {focused:document.activeElement===s, skip:[a.left,a.top,a.right,a.bottom].map(Math.round), search:c&&[c.left,c.top,c.right,c.bottom].map(Math.round), overlap:ov};
  });
  await p.screenshot({path:`/workspace/hr/wt-m4/logs/m4s1fix_skip_${w}x${h}.png`});
  out.push({w,h,...r}); await p.close();
}
console.log(JSON.stringify(out,null,1)); await b.close();
