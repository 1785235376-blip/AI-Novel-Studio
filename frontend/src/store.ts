import {create} from 'zustand';
import {Actor,Scope,setCollaborationContext} from './api';
import {browserPersistenceForMode,isPackagedDesktopHost} from './packagedHost';

export type TextModelSelection={providerId:string;modelId:string}|null;
export type WritingInputs={styleProfileId?:string;plotPlanId?:string};
type State={writingInputs:WritingInputs;setWritingInputs:(inputs:WritingInputs)=>void;novelId:string;chapterId:string;mode:'LOCAL_ONLY'|'HYBRID'|'QUALITY';textModel:TextModelSelection;actor?:Actor;scope?:Scope;sessionToken:string;setNovel:(id:string)=>void;setChapter:(id:string)=>void;setMode:(m:State['mode'])=>void;setTextModel:(selection:TextModelSelection)=>void;setCollaboration:(token:string,actor?:Actor,scope?:Scope)=>void};
const packagedHost=isPackagedDesktopHost();
// BACKPORT CANDIDATE (U02): property access itself can throw in a blocked
// browser origin. Packaged hosts must not read browser session tokens at all.
const browserStorage=(()=>{try{return browserPersistenceForMode(packagedHost,packagedHost?undefined:globalThis.localStorage)}catch{return undefined}})();
const savedScope=()=>{try{return JSON.parse(browserStorage?.getItem('studio.scope')||'null') as Scope|undefined}catch{return undefined}};
const initialScope=savedScope();
const initialToken=(()=>{try{return browserStorage?.getItem('studio.session')||''}catch{return ''}})();
setCollaborationContext({sessionToken:initialToken,scope:initialScope});

export const useStudio=create<State>(set=>({
 writingInputs:{},setWritingInputs:writingInputs=>set({writingInputs}),
 novelId:initialScope?.projectId||'',chapterId:'',mode:'LOCAL_ONLY',textModel:null,scope:initialScope,
 sessionToken:initialToken,
 setNovel:novelId=>set({novelId,chapterId:'',writingInputs:{}}),
 setChapter:chapterId=>set({chapterId}),
 setMode:mode=>set({mode}),
 setTextModel:textModel=>set({textModel}),
 setCollaboration:(sessionToken,actor,scope)=>{
  try {
   browserStorage?.setItem('studio.session',sessionToken);
   if(scope)browserStorage?.setItem('studio.scope',JSON.stringify(scope));else browserStorage?.removeItem('studio.scope');
  } catch { /* Continue with the explicitly selected in-memory session/scope. */ }
  setCollaborationContext({sessionToken,actor,scope});
  // Scope or actor changes invalidate the selected chapter. The next scoped
  // chapter query chooses a resource from the new branch only.
  set(state=>{
   const previous=state.scope;
   const sameScope=!!previous&&!!scope&&previous.workspaceId===scope.workspaceId&&previous.projectId===scope.projectId&&previous.storylineId===scope.storylineId&&previous.branchId===scope.branchId;
   return {sessionToken,actor,scope,novelId:scope?.projectId||'',chapterId:sameScope?state.chapterId:'',writingInputs:sameScope&&sessionToken===state.sessionToken?state.writingInputs:{}};
  });
 }
}));
