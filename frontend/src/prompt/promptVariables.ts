import { PROMPT_BOUNDS } from './promptTypes';
const tokenPattern=()=>/\{\{([\p{L}_][\p{L}\p{N}_]{0,39})\}\}/gu;
const bytes=(text:string)=>new TextEncoder().encode(text).length;
function matches(text:string){
 if(bytes(text)>PROMPT_BOUNDS.textBytes)throw new Error('原正文超过 64 KiB，请先缩短后填写变量。');
 return [...text.matchAll(tokenPattern())].filter(match=>match.index===0||text[match.index!-1]!=='\\');
}
/** Literal local substitution only. Never evaluates code, expands paths, or recursively substitutes values. */
export function promptVariableNames(text:string){
 const names=[...new Set(matches(text).map(match=>match[1]))];
 if(names.length>32)throw new Error('每次最多填写 32 个不同变量。');
 return names;
}
export function fillPromptVariables(text:string,values:Readonly<Record<string,string>>){
 const names=promptVariableNames(text),tokens=matches(text);
 if(!names.length)throw new Error('正文没有可填写的变量。');
 for(const name of names)if(!Object.hasOwn(values,name)||typeof values[name]!=='string'||values[name].length===0||values[name].length>8192)
  throw new Error(`请填写变量 ${name}（1 至 8192 字符，空格会保留）。`);
 const parts:string[]=[];let offset=0,size=0;
 function append(value:string){size+=bytes(value);if(size>PROMPT_BOUNDS.textBytes)throw new Error('填写后的正文超过 64 KiB，未修改草稿。');parts.push(value);}
 for(const match of tokens){append(text.slice(offset,match.index));append(values[match[1]]);offset=match.index!+match[0].length;}
 append(text.slice(offset));return {text:parts.join(''),bytes:size,names,replacements:tokens.length};
}
