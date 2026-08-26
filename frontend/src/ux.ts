export const splitParagraphs=(text:string)=>text.split(/\n\s*\n/).filter(Boolean);
export const acceptedParagraphs=(paragraphs:string[],accepted:boolean[])=>paragraphs.filter((_,i)=>accepted[i]).join('\n\n');
export const isVersionConflict=(error:any)=>error?.status===409;
