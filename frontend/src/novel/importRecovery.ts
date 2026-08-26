import type {NovelImportPlan} from './NovelImportPanel';

export type ImportRecovery={nextIndex:number;pending?:{index:number;chapter:{id:string;version:number}}};

export async function importChaptersWithRecovery(options:{
  plan:NovelImportPlan;
  recovery:ImportRecovery;
  persist:(state:ImportRecovery)=>void;
  create:(title:string)=>Promise<{id:string;version:number}>;
  save:(chapter:{id:string;version:number},content:string)=>Promise<void>;
  report?:(message:string)=>void;
}){
  const {plan,recovery,persist,create,save,report}=options;
  for(let index=recovery.nextIndex;index<plan.chapters.length;index++){
    const item=plan.chapters[index];report?.(`正在导入 ${index+1}/${plan.chapters.length}：${item.title}`);
    let chapter=recovery.pending?.index===index?recovery.pending.chapter:undefined;
    if(!chapter){chapter=await create(item.title);recovery.pending={index,chapter};persist(recovery)}
    if(item.content)await save(chapter,item.content);
    recovery.nextIndex=index+1;delete recovery.pending;persist(recovery);
  }
  return recovery;
}
