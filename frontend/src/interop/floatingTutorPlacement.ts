export type TutorRect={left:number;top:number;width:number;height:number};
export type TutorPlacement=TutorRect&{overlap:number};
const valid=(r:TutorRect)=>[r.left,r.top,r.width,r.height].every(Number.isFinite)&&r.width>=0&&r.height>=0;
export function tutorOverlap(a:TutorRect,b:TutorRect){return Math.max(0,Math.min(a.left+a.width,b.left+b.width)-Math.max(a.left,b.left))*Math.max(0,Math.min(a.top+a.height,b.top+b.height)-Math.max(a.top,b.top));}
/** CSS-pixel geometry only; no text, permissions, persistence or model state. */
export function placeFloatingTutor(view:TutorRect,size:{width:number;height:number},avoid:TutorRect[],previous?:TutorRect):TutorPlacement{
 if(!valid(view)||view.width<=0||view.height<=0||!Number.isFinite(size.width)||!Number.isFinite(size.height)||size.width<=0||size.height<=0)throw new Error('Invalid floating viewport');
 const margin=Math.min(8,view.width/4,view.height/4),width=Math.min(size.width,view.width-margin*2),height=Math.min(size.height,view.height-margin*2);
 const left=view.left+margin,right=view.left+view.width-margin-width,top=view.top+margin,bottom=view.top+view.height-margin-height,middle=(top+bottom)/2;
 const candidates=[{left:right,top:bottom},{left,top:bottom},{left:right,top},{left,top},{left:right,top:middle},{left,top:middle}].map(p=>({left:p.left,top:p.top,width,height}));
 const blockers=avoid.filter(valid).slice(0,8);let best: TutorPlacement|undefined,bestDistance=Infinity;
 for(const candidate of candidates){const overlap=blockers.reduce((sum,r)=>sum+tutorOverlap(candidate,r),0),distance=previous?Math.abs(candidate.left-previous.left)+Math.abs(candidate.top-previous.top):0;
  if(!best||overlap<best.overlap||overlap===best.overlap&&distance<bestDistance){best={...candidate,overlap};bestDistance=distance;}}
 return best!;
}
