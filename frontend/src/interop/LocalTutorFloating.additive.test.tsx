// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {LocalTutorDialog,type LocalTutorProps} from './LocalTutorIntegration';
import {placeFloatingTutor,tutorOverlap} from './floatingTutorPlacement';
const props:LocalTutorProps={context:{sessionToken:'synthetic-host',actor:{id:'author',displayName:'Author',workspaceId:'workspace'},scope:{workspaceId:'workspace',projectId:'project',storylineId:'story',branchId:'branch'}},projectId:'project',module:'NOVEL',surface:'editor',sourceReady:false,onNavigate:vi.fn()};
let fetcher:ReturnType<typeof vi.fn>;
beforeEach(()=>{
 fetcher=vi.fn(async()=>new Response(JSON.stringify({feature_enabled:true,enabled:false,acceptance_mode:false,product:{protocol_name:'PoemSeed Local Interop',protocol_version:'1.0',product_id:'poemseed.tutor.desktop',display_name:'Synthetic Tutor',product_version:'0.1',instance_id:'fixture',product_role:'AI_TUTOR',protocol_versions:['1.0'],capabilities:[]},capabilities:[],disabled_capabilities:['model.execute','project.write'],desktop_status:'LOCAL_REQUIRED'}),{status:200,headers:{'Content-Type':'application/json'}}));vi.stubGlobal('fetch',fetcher);
 vi.spyOn(window,'requestAnimationFrame').mockImplementation(callback=>window.setTimeout(()=>callback(performance.now()),0));vi.spyOn(window,'cancelAnimationFrame').mockImplementation(id=>window.clearTimeout(id));
});
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
it('chooses a zero-overlap candidate and preserves the viewport bounds',()=>{
 const viewport={left:0,top:0,width:1200,height:800},editor={left:650,top:0,width:550,height:800},p=placeFloatingTutor(viewport,{width:360,height:500},[editor]);expect(p.left).toBe(8);expect(tutorOverlap(p,editor)).toBe(0);expect(p.left+p.width).toBeLessThanOrEqual(viewport.width);expect(p.top+p.height).toBeLessThanOrEqual(viewport.height);
});
it('clamps tiny visual viewports and truthfully reports unavoidable overlap',()=>{
 const viewport={left:100,top:200,width:240,height:160},p=placeFloatingTutor(viewport,{width:400,height:640},[viewport]);expect(p.width).toBe(224);expect(p.height).toBe(144);expect(p.left).toBeGreaterThanOrEqual(100);expect(p.top).toBeGreaterThanOrEqual(200);expect(p.overlap).toBeGreaterThan(0);
 expect(()=>placeFloatingTutor({...viewport,width:NaN},{width:1,height:1},[])).toThrow();
});
it('keeps stable placement when scores tie and ignores invalid protected geometry',()=>{
 const viewport={left:0,top:0,width:1000,height:800},previous={left:8,top:8,width:300,height:200};const p=placeFloatingTutor(viewport,{width:300,height:200},[{left:0,top:0,width:NaN,height:9}],previous);expect(p.left).toBe(8);expect(p.top).toBe(8);expect(p.overlap).toBe(0);
});
it('changes only presentation: no modal backdrop, no new request, and external keyboard stays usable',async()=>{
 const close=vi.fn();render(<><input aria-label="Studio 编辑区" defaultValue="synthetic-private-text"/><LocalTutorDialog {...props} onClose={close}/></>);await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration'});expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');const before=fetcher.mock.calls.length;
 fireEvent.click(screen.getByText('切换为助手浮窗'));expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('false');expect(screen.getByRole('dialog').parentElement?.classList.contains('backdrop')).toBe(false);
 act(()=>screen.getByLabelText('Studio 编辑区').focus());expect(fireEvent.keyDown(document.body,{key:'Tab'})).toBe(true);expect(fireEvent.keyDown(document.body,{key:'Escape'})).toBe(true);expect(close).not.toHaveBeenCalled();expect(fetcher).toHaveBeenCalledTimes(before);
 fireEvent.click(screen.getByText('收起浮窗'));expect(screen.queryByRole('checkbox',{name:'Enable Local Tutor Integration'})).toBeNull();expect(screen.getByText('关闭并断开')).toBeTruthy();fireEvent.click(screen.getByText('展开浮窗'));expect(screen.getByRole('checkbox',{name:'Enable Local Tutor Integration'})).toBeTruthy();
 fireEvent.click(screen.getByText('返回对话框'));expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');expect(fetcher).toHaveBeenCalledTimes(before);
});
it('moves away from focused input geometry without reading or sharing its content',async()=>{
 vi.spyOn(HTMLElement.prototype,'getBoundingClientRect').mockImplementation(function(this:HTMLElement){const r=this.getAttribute('aria-label')==='Studio 编辑区'?{left:600,top:0,width:424,height:768}:this.getAttribute('role')==='dialog'?{left:0,top:0,width:400,height:240}:{left:0,top:0,width:0,height:0};return {...r,x:r.left,y:r.top,right:r.left+r.width,bottom:r.top+r.height,toJSON:()=>r} as DOMRect;});
 render(<><input aria-label="Studio 编辑区" defaultValue="synthetic-never-shared"/><LocalTutorDialog {...props} onClose={vi.fn()}/></>);await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration'});fireEvent.click(screen.getByText('切换为助手浮窗'));act(()=>screen.getByLabelText('Studio 编辑区').focus());await waitFor(()=>expect(screen.getByRole('dialog').style.left).toBe('8px'));expect(fetcher.mock.calls.every(call=>String(call[0]).includes('/status'))).toBe(true);expect(JSON.stringify(fetcher.mock.calls)).not.toContain('synthetic-never-shared');
});
it('returns to modal presentation for settings and retains original close behavior',async()=>{
 const close=vi.fn();render(<LocalTutorDialog {...props} onClose={close}/>);await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration'});fireEvent.click(screen.getByText('切换为助手浮窗'));fireEvent.click(screen.getByRole('button',{name:'集成设置'}));expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');fireEvent.click(screen.getByRole('button',{name:'关闭本机 Tutor'}));await waitFor(()=>expect(close).toHaveBeenCalledTimes(1));
});
it('forces uncertain revocation back into a visible modal instead of hiding it in a collapsed float',async()=>{
 const base=await (await fetcher()).json();fetcher.mockClear();fetcher.mockImplementation(async(url:string,init:RequestInit={})=>{const body=init.body?JSON.parse(String(init.body)):{};if(String(url).endsWith('/connect'))return new Response(JSON.stringify({request_id:body.request_id,session_id:'session',protocol_session_id:'session',product:base.product,capabilities:[],desktop_status:'LOCAL_REQUIRED',mode:'MOCK_ONLY',subscription_active:false,metadata_fields:[]}),{status:200});if(String(url).endsWith('/disconnect'))return new Response(JSON.stringify({detail:{code:'UNAVAILABLE'}}),{status:503});return new Response(JSON.stringify({...base,enabled:true}),{status:200});});
 const close=vi.fn();render(<LocalTutorDialog {...props} onClose={close}/>);await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration'});fireEvent.change(screen.getByRole('textbox',{name:'开发用本机 Tutor 地址'}),{target:{value:'http://127.0.0.1:8123'}});fireEvent.click(screen.getByRole('button',{name:'连接本机 Tutor'}));await screen.findByText('已连接 · LOCAL_ONLY');
 fireEvent.click(screen.getByText('切换为助手浮窗'));fireEvent.click(screen.getByText('收起浮窗'));fireEvent.click(screen.getByText('关闭并断开'));await screen.findByText('连接撤销尚未确认，持续共享可能仍在运行。请重试断开或关闭集成。');expect(screen.getByRole('dialog').getAttribute('aria-modal')).toBe('true');expect(screen.queryByText('展开浮窗')).toBeNull();expect(screen.getByRole('checkbox',{name:'Enable Local Tutor Integration'})).toBeTruthy();expect(close).not.toHaveBeenCalled();
});
