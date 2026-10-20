import {useLayoutEffect,useRef,useState,type RefObject} from 'react';
import {placeFloatingTutor,type TutorPlacement,type TutorRect} from './floatingTutorPlacement';
const rect=(r:DOMRect):TutorRect=>({left:r.left,top:r.top,width:r.width,height:r.height});
export function useFloatingTutorPlacement(panel:RefObject<HTMLElement>,enabled:boolean,identity:string,collapsed:boolean){
 const [placement,setPlacement]=useState<TutorPlacement>(),lastOutside=useRef<HTMLElement>(),previous=useRef<TutorPlacement>();
 useLayoutEffect(()=>{
  if(!enabled)return;
  let alive=true,frame:number|undefined,observer:ResizeObserver|undefined;const element=panel.current;if(!element)return;
  const viewport=()=>{const v=window.visualViewport;return {left:v?.offsetLeft||0,top:v?.offsetTop||0,width:v?.width||window.innerWidth,height:v?.height||window.innerHeight};};
  const remember=(target:EventTarget|null)=>{if(target instanceof HTMLElement&&!element.contains(target)){const input=target.closest<HTMLElement>('textarea,input,[contenteditable="true"]');if(input&&input!==lastOutside.current){if(lastOutside.current)observer?.unobserve(lastOutside.current);lastOutside.current=input;observer?.observe(input);}}};
  remember(document.activeElement);
  const measure=()=>{frame=undefined;if(!alive||!element.isConnected)return;const view=viewport(),avoid:TutorRect[]=[];
   const outside=lastOutside.current;if(outside?.isConnected&&!element.contains(outside)){const r=outside.getBoundingClientRect();if(r.width&&r.height)avoid.push(rect(r));}
   const selection=window.getSelection();if(selection&&selection.rangeCount&&selection.anchorNode&&!element.contains(selection.anchorNode)){try{const range=selection.getRangeAt(0);if(typeof range.getBoundingClientRect==='function'){const r=range.getBoundingClientRect();if(r.height)avoid.push({left:r.left-12,top:r.top-8,width:Math.max(r.width,1)+24,height:r.height+16});}}catch{/* Detached selection supplies no geometry. */}}
   if(!avoid.length){const editor=[...document.querySelectorAll<HTMLElement>('textarea,[contenteditable="true"]')].find(node=>!element.contains(node)&&node.getBoundingClientRect().width>0);if(editor)avoid.push(rect(editor.getBoundingClientRect()));}
   for(const modal of document.querySelectorAll<HTMLElement>('[role="dialog"][aria-modal="true"]'))if(modal!==element&&!element.contains(modal)&&avoid.length<8)avoid.push(rect(modal.getBoundingClientRect()));
   const width=Math.max(1,Math.min(400,Math.max(260,view.width*.32),view.width-16)),maxHeight=Math.max(1,Math.min(640,view.height-16)),height=Math.min(element.getBoundingClientRect().height||maxHeight,maxHeight);
   try{const next=placeFloatingTutor(view,{width,height},avoid,previous.current);previous.current=next;setPlacement(old=>old&&JSON.stringify(old)===JSON.stringify(next)?old:next);}catch{/* Keep the existing bounded CSS fallback. */}
  };
  const schedule=()=>{if(alive&&frame===undefined)frame=window.requestAnimationFrame(measure);};
  const focused=(event:FocusEvent)=>{remember(event.target);schedule();};
  observer=typeof ResizeObserver==='undefined'?undefined:new ResizeObserver(schedule);observer?.observe(element);if(lastOutside.current?.isConnected)observer?.observe(lastOutside.current);
  document.addEventListener('focusin',focused);document.addEventListener('selectionchange',schedule);window.addEventListener('resize',schedule);window.addEventListener('scroll',schedule,true);window.visualViewport?.addEventListener('resize',schedule);window.visualViewport?.addEventListener('scroll',schedule);measure();
  return()=>{alive=false;if(frame!==undefined)window.cancelAnimationFrame(frame);observer?.disconnect();document.removeEventListener('focusin',focused);document.removeEventListener('selectionchange',schedule);window.removeEventListener('resize',schedule);window.removeEventListener('scroll',schedule,true);window.visualViewport?.removeEventListener('resize',schedule);window.visualViewport?.removeEventListener('scroll',schedule);};
 },[panel,enabled,identity,collapsed]);
 return enabled?placement:undefined;
}
