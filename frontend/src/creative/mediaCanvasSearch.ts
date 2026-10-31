import { clampGraphPosition, clampGraphZoom } from './graphCanvasGeometry';
import { MEDIA_CARD_HEIGHT, MEDIA_CARD_WIDTH } from './mediaCanvasGeometry';
import type { CanvasDefinition } from './studioCanvasViewClient';
export function searchCanvasCards(definition: CanvasDefinition, query: string) {
  const needle=query.trim().toLocaleLowerCase();
  if (!needle) return [];
  return definition.cards.filter(card=>card.id.toLocaleLowerCase().includes(needle)||card.asset?.asset_id.toLocaleLowerCase().includes(needle));
}
/** Explicit presentation edit: reveal only the selected card's ancestor groups. */
export function focusCanvasCard(definition: CanvasDefinition, id: string, width: number, height: number): CanvasDefinition {
  const card=definition.cards.find(row=>row.id===id);
  if (!card || !Number.isFinite(width) || !Number.isFinite(height) || width<=0 || height<=0) throw new Error('当前卡片或视口不可定位。');
  const x=card.position.x+MEDIA_CARD_WIDTH/2,y=card.position.y+MEDIA_CARD_HEIGHT/2;
  const bound=(center:number,screen:number)=>center>0?(100000+screen/2)/center:center<0?(100000-screen/2)/-center:2.5;
  const zoom=clampGraphZoom(Math.min(definition.viewport.zoom,bound(x,width),bound(y,height)));
  const reveal=new Set<string>(),groups=definition.groups??[];
  let group=groups.find(row=>row.card_ids.includes(id));
  for(let depth=0;group&&depth<8;depth++){reveal.add(group.id);group=groups.find(row=>row.id===group!.parent_id);}
  return {...definition,viewport:{x:clampGraphPosition(width/2-x*zoom),y:clampGraphPosition(height/2-y*zoom),zoom},
    ...(definition.groups?{groups:groups.map(row=>reveal.has(row.id)?{...row,collapsed:false}:row)}:{})};
}
