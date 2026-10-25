// @vitest-environment jsdom
// [HERMIA-FE-20261025 DUI P0-4] Normal mode: human copy on screen, protocol codes only inside the collapsed 「技术详情」.
import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {LocalTutorDialog,type LocalTutorProps} from './LocalTutorIntegration';
const props:LocalTutorProps={context:{sessionToken:'synthetic-host',actor:{id:'author',displayName:'Author',workspaceId:'workspace'},scope:{workspaceId:'workspace',projectId:'project',storylineId:'story',branchId:'branch'}},projectId:'project',module:'NOVEL',surface:'editor',sourceReady:false,onNavigate:vi.fn()};
beforeEach(()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({feature_enabled:true,enabled:false,acceptance_mode:false,product:{protocol_name:'PoemSeed Local Interop',protocol_version:'1.0',product_id:'poemseed.tutor.desktop',display_name:'Synthetic Tutor',product_version:'0.1',instance_id:'fixture',product_role:'AI_TUTOR',protocol_versions:['1.0'],capabilities:[]},capabilities:[],disabled_capabilities:[],desktop_status:'LOCAL_REQUIRED'}),{status:200,headers:{'Content-Type':'application/json'}})));});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
const visibleText=()=>{const c=document.querySelector('.local-tutor-dialog')!.cloneNode(true) as HTMLElement;c.querySelectorAll('details:not([open])').forEach(d=>Array.from(d.children).forEach(ch=>{if(ch.tagName!=='SUMMARY')ch.remove();}));return c.textContent||'';};
it('simple: human disconnected card, technical codes folded away',async()=>{
  render(<LocalTutorDialog {...props} simple onClose={vi.fn()}/>);
  await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration',hidden:true});
  expect(screen.getByText('本机助手未连接',{selector:'strong'})).toBeTruthy();
  expect(screen.getByRole('button',{name:'重试'})).toBeTruthy();
  const details=document.querySelector('[data-local-tutor-details]') as HTMLDetailsElement;
  expect(details).toBeTruthy(); expect(details.open).toBe(false);
  expect(visibleText()).not.toMatch(/LOCAL_REQUIRED|Named Pipe|Local Tutor|UNKNOWN|Unknown|LOCAL_ONLY/);
  expect(details.textContent).toMatch(/LOCAL_REQUIRED/); // still honest & reachable
});
it('pro (default): unchanged technical surface',async()=>{
  render(<LocalTutorDialog {...props} onClose={vi.fn()}/>);
  await screen.findByRole('checkbox',{name:'Enable Local Tutor Integration'});
  expect(document.querySelector('[data-local-tutor-details]')).toBeNull();
  expect(screen.getByText('问助手 · Local Tutor')).toBeTruthy();
});
