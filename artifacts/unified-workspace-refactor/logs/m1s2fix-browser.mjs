import {createRequire} from 'module';const r=createRequire('/workspace/hr/wt/frontend/');
const {chromium}=r('playwright-core');
const A='/workspace/hr/wt/artifacts/unified-workspace-refactor/';const out={};
const b=await chromium.launch({executablePath:'/usr/bin/google-chrome'});const p=await b.newPage({viewport:{width:1366,height:768}});
await p.goto('http://127.0.0.1:4299/?uw=1');await p.evaluate(()=>localStorage.clear());await p.reload();
await p.waitForSelector('[data-testid=dock-layout]');
const box=async s=>{const e=await p.$(s);return e?await e.boundingBox():null};
// 3 reset disabled at default
const rb=p.locator('button.uw-btn[data-action-id="layout.reset"]');
out.reset_default={disabled:await rb.isDisabled(),reason:await p.textContent('[data-testid=reset-reason]').catch(()=>null)};
await p.screenshot({path:A+'screenshots/m1s2fix_3_reset_disabled.png'});
// make left empty: drag outline to right
let h=await box('[data-testid=drag-outline]');
await p.mouse.move(h.x+20,h.y+h.height/2);await p.mouse.down();await p.mouse.move(1300,300,{steps:10});await p.mouse.up();
await p.waitForTimeout(400);
out.outline_dock=await p.getAttribute('[data-testid=panel-outline]','data-dock');
out.reset_after_change={disabled:await rb.isDisabled()};
// 1 drag inspector over empty left
h=await box('[data-testid=drag-inspector]');
await p.mouse.move(h.x+20,h.y+h.height/2);await p.mouse.down();await p.mouse.move(80,350,{steps:12});
await p.waitForTimeout(150);
out.indicator=await box('[data-testid=drop-indicator]');out.root=await box('[data-testid=dock-layout]');
out.indicator_class=await p.getAttribute('[data-testid=drop-indicator]','class').catch(()=>null);
out.indicator_bg=await p.$eval('[data-testid=drop-indicator]',e=>getComputedStyle(e).backgroundColor).catch(()=>null);
await p.screenshot({path:A+'screenshots/m1s2fix_1_empty_zone_indicator.png'});
// 2 Esc
await p.keyboard.press('Escape');await p.waitForTimeout(150);
out.after_esc={indicator:!!(await p.$('[data-testid=drop-indicator]')),ghosts:(await p.$$('[data-zone-ghost]')).length};
await p.mouse.up();await p.waitForTimeout(200);
out.inspector_dock_after_esc_up=await p.getAttribute('[data-testid=panel-inspector]','data-dock');
await p.screenshot({path:A+'screenshots/m1s2fix_2_esc_cancel.png'});
// 4 Ctrl+K
await p.mouse.click(683,20).catch(()=>{});
await p.keyboard.press('Control+k');await p.waitForTimeout(300);
const txt=await p.evaluate(()=>document.body.innerText);
out.palette_has=['恢复默认布局','分屏','重新打开','layout.'].map(k=>[k,txt.includes(k)]);
out.palette_items=await p.$$eval('[role=option],.wb-command li,.wb-command button',es=>es.map(e=>e.textContent.trim()).filter(Boolean).slice(0,20));
await p.screenshot({path:A+'screenshots/m1s2fix_4_ctrlk_palette.png'});
const opt=p.locator('[role=option],.wb-command li button,.wb-command li').filter({hasText:/默认布局/}).first();
await opt.click({force:true}).catch(()=>{});await p.waitForTimeout(400);
out.dialog=await p.$$eval('.uw-dialog',es=>es.map(e=>e.innerText));
await p.screenshot({path:A+'screenshots/m1s2fix_4_reset_confirm.png'});
const btns=await p.$$eval('.uw-dialog button',es=>es.map(e=>e.textContent));out.dialog_buttons=btns;
const c=p.locator('.uw-dialog button').filter({hasText:/恢复|确认|确定/}).first();if(await c.count()){await c.click();await p.waitForTimeout(500);}
out.after_palette_reset={outline_dock:await p.getAttribute('[data-testid=panel-outline]','data-dock'),reset_disabled:await rb.isDisabled()};
await p.screenshot({path:A+'screenshots/m1s2fix_4_after_palette_reset.png'});
console.log(JSON.stringify(out,null,1));await b.close();
