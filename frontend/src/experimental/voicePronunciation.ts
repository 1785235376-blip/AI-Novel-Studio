export type PronunciationRule = {term:string;pronunciation:string};
const length=(value:string)=>Array.from(value).length;
/** Same line syntax used by the original segment editor; no trimming of authored terms. */
export function parsePronunciationRules(value:string):PronunciationRule[]{
 const lines=value.split('\n').filter(line=>line.trim());
 if(lines.length>100)throw new Error('发音规则最多 100 条。');
 const seen=new Set<string>();
 return lines.map(line=>{const i=line.indexOf('=');if(i<1)throw new Error('每行需要 原词=读音');
  const term=line.slice(0,i),pronunciation=line.slice(i+1);
  if(length(term)>160||length(pronunciation)<1||length(pronunciation)>240||/[<>\x00-\x1f\x7f]/.test(term+pronunciation))throw new Error('原词须为 1–160 字符，读音须为 1–240 字符；不接受标记或控制字符。');
  if(seen.has(term))throw new Error('同一原词不能重复设置发音规则。');seen.add(term);return {term,pronunciation};
 });
}
/** Literal simultaneous replacement, longest original term first; replacement text is never rescanned. */
export function pronunciationPreview(text:string,rules:PronunciationRule[],limit=4000){
 if(length(text)>20000)throw new Error('朗读文本超过 20000 字符，请缩短后预览。');
 if(!Number.isSafeInteger(limit)||limit<1||limit>4000)throw new Error('预览显示上限无效。');
 let count=0,visible=0;const chunks:string[]=[];
 const append=(value:string)=>{const points=Array.from(value);count+=points.length;if(visible<limit){const part=points.slice(0,limit-visible);chunks.push(part.join(''));visible+=part.length;}};
 if(!rules.length)append(text);
 else{
  const mapping=new Map(rules.map(row=>[row.term,row.pronunciation]));
  if(mapping.size!==rules.length||rules.some(row=>!row.term))throw new Error('发音规则身份无效。');
  const escaped=[...mapping.keys()].sort((a,b)=>length(b)-length(a)).map(value=>value.replace(/[.*+?^${}()|[\]\\]/g,'\\$&'));
  const pattern=new RegExp(escaped.join('|'),'gu');let offset=0;
  for(const match of text.matchAll(pattern)){append(text.slice(offset,match.index));append(mapping.get(match[0])!);offset=match.index!+match[0].length;}
  append(text.slice(offset));
 }
 return {text:chunks.join(''),characters:count,truncated:count>limit};
}
