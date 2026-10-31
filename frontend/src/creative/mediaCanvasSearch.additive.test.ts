import { expect,it } from 'vitest';
import { focusCanvasCard,searchCanvasCards } from './mediaCanvasSearch';
import { visibleMediaCards,MEDIA_RENDER_LIMIT } from './mediaCanvasGeometry';
import type { CanvasDefinition } from './studioCanvasViewClient';
const definition=():CanvasDefinition=>({schema_version:1,title:'Search',viewport:{x:0,y:0,zoom:2.5},cards:[{id:'Far',position:{x:100000,y:-100000},asset:{asset_id:'source-A',version:1,digest:'a'.repeat(64),kind:'image'}}],groups:[{id:'Root',name:'Root',card_ids:[],collapsed:true},{id:'Child',name:'Child',parent_id:'Root',card_ids:['Far'],collapsed:true},{id:'Other',name:'Other',card_ids:[],collapsed:true}]});
it('finds off-screen nested cards and reveals only their ancestors within camera bounds',()=>{
 const source=definition(),before=structuredClone(source);expect(visibleMediaCards(source,800,480,'Far').cards).toEqual([]);expect(searchCanvasCards(source,'SOURCE-a')).toHaveLength(1);
 const next=focusCanvasCard(source,'Far',800,480);expect(next.groups!.map(g=>g.collapsed)).toEqual([false,false,true]);expect(visibleMediaCards(next,800,480,'Far').cards[0].id).toBe('Far');
 expect(Math.abs(next.viewport.x)).toBeLessThanOrEqual(100000);expect(Math.abs(next.viewport.y)).toBeLessThanOrEqual(100000);expect(next.viewport.zoom).toBeGreaterThanOrEqual(.35);expect(source).toEqual(before);expect(next.cards).toBe(source.cards);
});
it('prioritizes the selected overlap without exceeding the DOM cap',()=>{
 const source=definition();delete source.groups;source.viewport={x:0,y:0,zoom:1};source.cards=Array.from({length:1000},(_,i)=>({id:`Card_${i}`,position:{x:0,y:0}}));
 const shown=visibleMediaCards(source,800,480,'','Card_999');expect(shown.cards).toHaveLength(MEDIA_RENDER_LIMIT);expect(shown.cards.at(-1)!.id).toBe('Card_999');expect(shown.clipped).toBe(true);expect(source.cards).toHaveLength(1000);
});
it('rejects a missing card and invalid viewport instead of moving to an arbitrary point',()=>{expect(()=>focusCanvasCard(definition(),'missing',800,480)).toThrow();expect(()=>focusCanvasCard(definition(),'Far',NaN,480)).toThrow();expect(searchCanvasCards(definition(),'')).toEqual([]);});
