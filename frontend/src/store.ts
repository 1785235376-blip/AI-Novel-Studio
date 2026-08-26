import {create} from 'zustand';
import {Actor,Scope,setCollaborationContext} from './api';
import {browserPersistenceForMode,isPackagedDesktopHost} from './packagedHost';

export type TextModelSelection={providerId:string;modelId:string}|null;
type State={novelId:string;chapterId:string;mode:'LOCAL_ONLY'|'HYBRID'|'QUALITY';textModel:TextModelSelection;actor?:Actor;scope?:Scope;sessionToken:string;setNovel:(id:string)=>void;setChapter:(id:string)=>void;setMode:(m:State['mode'])=>void;setTextModel:(selection:TextModelSelection)=>void;setCollaboration:(token:string,actor?:Actor,scope?:Scope)=>void};
const packagedHost=isPackagedDesktopHost();
const browserStorage=browserPersistenceForMode(packagedHost,typeof localStorage==='undefined'?undefined:localStorage);
const savedScope=()=>{try{return JSON.parse(browserStorage?.getItem('studio.scope')||'null') as Scope|undefined}catch{return undefined}};
const initialScope=savedScope();
const initialToken=browserStorage?.getItem('studio.session')||'';
setCollaborationContext({sessionToken:initialToken,scope:initialScope});

export const useStudio=create<State>(set=>({
 novelId:initialScope?.projectId||'',chapterId:'',mode:'LOCAL_ONLY',textModel:null,scope:initialScope,
 sessionToken:initialToken,
 setNovel:novelId=>set({novelId,chapterId:''}),
 setChapter:chapterId=>set({chapterId}),
 setMode:mode=>set({mode}),
 setTextModel:textModel=>set({textModel}),
 setCollaboration:(sessionToken,actor,scope)=>{
  browserStorage?.setItem('studio.session',sessionToken);
  if(scope)browserStorage?.setItem('studio.scope',JSON.stringify(scope));else browserStorage?.removeItem('studio.scope');
  setCollaborationContext({sessionToken,actor,scope});
  // Scope or actor changes invalidate the selected chapter. The next scoped
  // chapter query chooses a resource from the new branch only.
  set(state=>{
   const previous=state.scope;
   const sameScope=!!previous&&!!scope&&previous.workspaceId===scope.workspaceId&&previous.projectId===scope.projectId&&previous.storylineId===scope.storylineId&&previous.branchId===scope.branchId;
   return {sessionToken,actor,scope,novelId:scope?.projectId||'',chapterId:sameScope?state.chapterId:''};
  });
 }
}));
