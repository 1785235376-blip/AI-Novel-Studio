import type { ComicDocument } from './comicLayoutsClient';
/** Match the original raster preflight's stable (y, x) order without moving content. */
export function previewComicReadingOrder(document:ComicDocument){
 const panels=document.panels;
 if(!Array.isArray(panels)||!panels.length||panels.length>24||new Set(panels.map(row=>row.id)).size!==panels.length
  ||panels.some(row=>!row||typeof row.id!=='string'||!/^[A-Za-z0-9_-]{1,80}$/.test(row.id)
    ||!Number.isSafeInteger(row.x)||!Number.isSafeInteger(row.y)||row.x<0||row.y<0||row.x>12000||row.y>12000))
  throw new Error('请先修正格框标识和坐标，再预览阅读顺序。');
 const ordered=panels.map((panel,index)=>({panel,index})).sort((a,b)=>a.panel.y-b.panel.y||a.panel.x-b.panel.x||a.index-b.index);
 const orders=new Map(ordered.map(({panel},index)=>[panel.id,index+1]));
 const changes=panels.filter(row=>row.order!==orders.get(row.id)).map(row=>({id:row.id,before:row.order,after:orders.get(row.id)!}));
 return {document:{...document,panels:panels.map(row=>({...row,order:orders.get(row.id)!}))},changes};
}
