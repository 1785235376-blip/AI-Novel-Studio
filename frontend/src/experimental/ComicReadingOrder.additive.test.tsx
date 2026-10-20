// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { previewComicReadingOrder } from './comicReadingOrder';
import { ComicReadingOrderPanel } from './ComicReadingOrderPanel';
import { ComicLayoutsPanel } from './ComicLayoutsPanel';
import { experimentalClient } from './api';
import { comicPreset } from './comicLayoutsClient';
const source={id:'screenplay',title:'Fixture',edit_version:4,shot_status:'APPROVED',checks:[],shots:[1,2,3].map(n=>({id:`shot-${n}`,number:n,scene_id:'scene',shot_size:'MEDIUM',camera_angle:'EYE_LEVEL',camera_motion:'STATIC',duration_seconds:5}))};
const preset={width:800,height:1120,safe_area:24,segment_height:1120};
const fixture=()=>comicPreset(source,'PAGE',preset);
beforeEach(()=>vi.stubGlobal('URL',class extends URL { static revokeObjectURL=vi.fn(); static createObjectURL=vi.fn(()=> 'blob:fixture'); }));
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('repairs repeated/missing numbers using stable original coordinates without moving or rebinding content',()=>{
 const doc=fixture();doc.panels[0].order=3;doc.panels[1].order=3;doc.panels[2].order=0;const before=structuredClone(doc),result=previewComicReadingOrder(doc);
 expect(result.document.panels.map(row=>row.order)).toEqual([1,2,3]);expect(result.changes).toHaveLength(3);expect(doc).toEqual(before);
 for(let i=0;i<3;i++)expect({...result.document.panels[i],order:before.panels[i].order}).toEqual(before.panels[i]);
 expect(previewComicReadingOrder(result.document).changes).toHaveLength(0);
});
it('matches y then x with stable ties and refuses unknown geometry',()=>{
 const doc=fixture();doc.panels.forEach(row=>{row.y=50;});doc.panels[0].x=200;doc.panels[1].x=100;doc.panels[2].x=100;
 expect(previewComicReadingOrder(doc).document.panels.map(row=>row.order)).toEqual([3,1,2]);doc.panels[0].x=NaN;expect(()=>previewComicReadingOrder(doc)).toThrow();
});
const button=(name:string)=>screen.getByRole('button',{name,hidden:true});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
function preview(){fireEvent.click(button('预览按坐标整理编号'));fireEvent.click(screen.getByLabelText('已核对编号，只修改阅读顺序'));}
it('requires separate confirmation and applies only once through supplied owner',()=>{
 const doc=fixture();doc.panels[0].order=2;const onApply=vi.fn(()=>true);render(<ComicReadingOrderPanel document={doc} scope={{}} disabled={false} getRevision={()=>1} onApply={onApply}/>);preview();expect(onApply).not.toHaveBeenCalled();const apply=handler(button('应用阅读编号到本地草稿'));act(()=>{apply();apply();});expect(onApply).toHaveBeenCalledTimes(1);
});
it('retires retained apply on revocation and original generation changes',()=>{
 let revision=1;const doc=fixture();doc.panels[0].order=2;const onApply=vi.fn(()=>true);render(<ComicReadingOrderPanel document={doc} scope={{}} disabled={false} getRevision={()=>revision} onApply={onApply}/>);preview();const apply=handler(button('应用阅读编号到本地草稿'));
 fireEvent.click(screen.getByLabelText('已核对编号，只修改阅读顺序'));act(()=>apply());expect(onApply).not.toHaveBeenCalled();fireEvent.click(screen.getByLabelText('已核对编号，只修改阅读顺序'));revision++;act(()=>apply());expect(onApply).not.toHaveBeenCalled();
});
it('integrates with original layout history without saving or approving automatically',async()=>{
 const doc=fixture();doc.panels[0].order=3;doc.panels[2].order=1;
 const record={id:'layout',version:1,status:'DRAFT',stale:false,document:doc,history_versions:[]};
 const catalog={screenplays:[source],characters:[],assets:[],presets:{PAGE:preset,WEBTOON:preset},renderer:{available:true},font:{available:true}};
 const fetch=vi.fn(async(url:string,init:RequestInit)=>new Response(JSON.stringify(url.endsWith('/catalog')?catalog:{items:[record]}),{status:200}));vi.stubGlobal('fetch',fetch);
 render(<ComicLayoutsPanel client={experimentalClient('project',{sessionToken:'trusted'})}/>);fireEvent.click(await screen.findByRole('button',{name:/打开布局/}));preview();fireEvent.click(button('应用阅读编号到本地草稿'));
 expect((screen.getByLabelText('格框 1 阅读顺序') as HTMLInputElement).value).toBe('1');fireEvent.click(screen.getByRole('button',{name:'撤销本地排版'}));expect((screen.getByLabelText('格框 1 阅读顺序') as HTMLInputElement).value).toBe('3');
 expect(fetch.mock.calls.every(([,init])=>init.method==='GET')).toBe(true);
});
