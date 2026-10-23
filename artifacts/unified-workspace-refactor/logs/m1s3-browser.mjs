import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});
for(const [w,h] of [[1366,768],[1440,900],[1920,1080]]){
  const o={};const p=await b.newPage({viewport:{width:w,height:h}});const nonGet=[];const errs=[];
  p.on('request',q=>{if(q.method()!=='GET')nonGet.push(q.method()+' '+q.url())});
  p.on('pageerror',e=>errs.push(String(e)));
  await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
  await p.waitForSelector('[data-testid=uw-outline] [data-chapter-id]',{timeout:15000});
  o.novel=await p.$eval('[aria-label=选择作品]',e=>e.selectedOptions[0].textContent);
  o.chapters=await p.$$eval('[data-testid=uw-outline] [data-chapter-id]',es=>es.map(e=>e.textContent.trim()));
  o.inspector_before=await p.textContent('[data-testid=panel-inspector]');
  await p.click('[data-testid=uw-outline] [data-chapter-id]');
  await p.waitForSelector('[data-testid=uw-inspector]');
  o.inspector=await p.$eval('[data-testid=uw-inspector]',e=>e.innerText);
  await p.screenshot({path:A+`screenshots/m1s3_${w}_real_panels.png`});
  await p.fill('[aria-label=章节标题]','来信（未保存）');
  await p.selectOption('[aria-label="「章节属性」停靠位置"]','bottom');await p.waitForTimeout(200);
  o.redock={dock:await p.getAttribute('[data-testid=panel-inspector]','data-dock'),value:await p.inputValue('[aria-label=章节标题]')};
  await p.selectOption('[aria-label="「章节属性」停靠位置"]','left');await p.waitForTimeout(200);
  o.redock2={dock:await p.getAttribute('[data-testid=panel-inspector]','data-dock'),value:await p.inputValue('[aria-label=章节标题]')};
  await p.screenshot({path:A+`screenshots/m1s3_${w}_redock_dirty.png`});
  await p.click('[aria-label="关闭「章节属性」"]');await p.waitForTimeout(200);
  o.dialog=await p.$$eval('.uw-dialog',es=>es.map(e=>e.innerText));
  await p.screenshot({path:A+`screenshots/m1s3_${w}_dirty_close_confirm.png`});
  await p.click('.uw-dialog button:has-text("取消")');await p.waitForTimeout(150);
  o.after_cancel=await p.inputValue('[aria-label=章节标题]');
  await p.click('[aria-label="关闭「章节属性」"]');await p.click('.uw-dialog button:has-text("放弃修改")');await p.waitForTimeout(200);
  o.after_discard_panel=!!(await p.$('[data-testid=panel-inspector]'));
  await p.click('[data-testid=uw-outline] button[data-action-id="novel.chapters.refresh"]');await p.waitForTimeout(600);
  o.refresh=await p.$eval('[data-testid=uw-outline]',e=>e.innerText.includes('已刷新'));
  await p.keyboard.press('Control+k');await p.waitForTimeout(300);
  o.palette_text_has_raw_ids=await p.evaluate(()=>/(panel\.open\.|layout\.|novel\.|workspace\.open\.)/.test(document.querySelector('[data-testid=command-search-overlay]')?.innerText??''));
  o.palette_groups=await p.$$eval('[data-command-group]',es=>es.map(e=>e.getAttribute('data-command-group')+':'+e.querySelectorAll('[role=option]').length));
  await p.screenshot({path:A+`screenshots/m1s3_${w}_palette.png`});
  o.overflow=await p.evaluate(()=>document.documentElement.scrollWidth>innerWidth);
  o.nonGet=nonGet;o.pageErrors=errs;out[w]=o;await p.close();
}
// legacy UI without flag
{const p=await b.newPage({viewport:{width:1366,height:768}});const nonGet=[];p.on('request',q=>{if(q.method()!=='GET')nonGet.push(q.url())});
 await p.goto('http://127.0.0.1:4299/');await p.waitForTimeout(3000);
 out.legacy={has_dock:!!(await p.$('[data-testid=dock-layout]')),has_uw_outline:!!(await p.$('[data-testid=uw-outline]')),title:await p.title(),nonGet};
 await p.screenshot({path:A+'screenshots/m1s3_legacy_noflag.png'});await p.close();}
console.log(JSON.stringify(out,null,1));await b.close();
