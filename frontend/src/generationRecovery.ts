import type {AiVariantDraft} from './novel/AiWritingPanel';

export type RecoverableGeneration={
  chapterId:string;
  jobId?:string;
  original?:string;
  baseChapterVersion?:number;
  variants?:AiVariantDraft[];
  actorId?:string;
  retryOf?:string;
  job?:Record<string,any>;
};

// Session storage may be denied or full. Keep the candidate in memory without
// claiming reload durability; this never persists a session token/credential.
const memory=new Map<string,string|null>();
const storage={
  getItem(key:string){if(memory.has(key))return memory.get(key)??null;try{return globalThis.sessionStorage?.getItem(key)??null}catch{return null}},
  setItem(key:string,value:string){memory.set(key,value);try{if(globalThis.sessionStorage){sessionStorage.setItem(key,value);if(sessionStorage.getItem(key)===value)memory.delete(key)}}catch{/* volatile recovery remains */}},
  removeItem(key:string){memory.set(key,null);try{if(globalThis.sessionStorage){sessionStorage.removeItem(key);if(sessionStorage.getItem(key)===null)memory.delete(key)}}catch{/* do not resurrect it in this session */}},
};
const key=(namespace:string,chapterId:string)=>`ai-novel-studio:generation:${namespace}:${chapterId}`;
const identity=(value:RecoverableGeneration)=>value.jobId??value.variants?.map(item=>item.id).join('|');
function read<T>(key:string):T|undefined {try{const value=storage.getItem(key);return value?JSON.parse(value):undefined}catch{return undefined}}

export const generationRecovery={
  load(namespace:string,chapterId:string):RecoverableGeneration|undefined{return read(key(namespace,chapterId))},
  // Late creation responses still have a real server task. Preserve the origin
  // metadata without replacing a newer active task's recovery record.
  save(namespace:string,value:RecoverableGeneration,background=false){
    const current=this.load(namespace,value.chapterId);
    const replacesRetriedTask=!!value.retryOf&&(current?.jobId===value.retryOf||current?.variants?.some(item=>item.id===value.retryOf));
    if(background&&current&&identity(current)!==identity(value)&&!replacesRetriedTask){
      const history=this.history(namespace,value.chapterId).filter(item=>identity(item)!==identity(value));
      storage.setItem(`${key(namespace,value.chapterId)}:retained`,JSON.stringify([...history,value]));
      return;
    }
    if(current&&identity(current)!==identity(value)){
      const history=this.history(namespace,value.chapterId).filter(item=>identity(item)!==identity(current));
      storage.setItem(`${key(namespace,value.chapterId)}:retained`,JSON.stringify([...history,current]));
    }
    storage.setItem(key(namespace,value.chapterId),JSON.stringify(value));
  },
  history(namespace:string,chapterId:string):RecoverableGeneration[]{return read(`${key(namespace,chapterId)}:retained`)??[]},
  remove(namespace:string,chapterId:string){storage.removeItem(key(namespace,chapterId))},
};
