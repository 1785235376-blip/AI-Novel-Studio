import type {AiVariantDraft} from './novel/AiWritingPanel';

export type RecoverableGeneration={
  chapterId:string;
  jobId?:string;
  original?:string;
  baseChapterVersion?:number;
  variants?:AiVariantDraft[];
};

const memory=new Map<string,string>();
const storage={
  getItem:(key:string)=>typeof sessionStorage==='undefined'?memory.get(key)??null:sessionStorage.getItem(key),
  setItem:(key:string,value:string)=>typeof sessionStorage==='undefined'?void memory.set(key,value):sessionStorage.setItem(key,value),
  removeItem:(key:string)=>typeof sessionStorage==='undefined'?void memory.delete(key):sessionStorage.removeItem(key),
};
const key=(namespace:string,chapterId:string)=>`ai-novel-studio:generation:${namespace}:${chapterId}`;

export const generationRecovery={
  load(namespace:string,chapterId:string):RecoverableGeneration|undefined{
    try{const value=storage.getItem(key(namespace,chapterId));return value?JSON.parse(value):undefined}catch{return undefined}
  },
  save(namespace:string,value:RecoverableGeneration){storage.setItem(key(namespace,value.chapterId),JSON.stringify(value))},
  remove(namespace:string,chapterId:string){storage.removeItem(key(namespace,chapterId))},
};
