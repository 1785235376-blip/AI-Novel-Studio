// @vitest-environment jsdom
import { StrictMode } from 'react';
import { act, cleanup, render, screen, waitFor } from '@testing-library/react';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import { RevisionHistory } from './App';
import { api, setCollaborationContext, type Chapter } from './api';
import { useStudio } from './store';
const doc = (text:string) => ({type:'doc',content:[{type:'paragraph',content:[{type:'text',text}]}]});
const chapter:Chapter={id:'audit-novel:1',novel_id:'audit-novel',number:1,title:'Synthetic',version:2,content:'CURRENT',document:doc('CURRENT'),word_count:7,status:'DRAFT'};
const revision={version:1,timestamp:'2026-10-05T00:00:00Z',source:'USER',operator:'Synthetic',document:doc('HISTORY CANARY')};
let query:QueryClient;
beforeEach(()=>{localStorage.clear();useStudio.getState().setCollaboration('');useStudio.setState({novelId:chapter.novel_id,chapterId:chapter.id});query=new QueryClient({defaultOptions:{queries:{retry:false,staleTime:Infinity}}});});
afterEach(()=>{cleanup();query.clear();vi.restoreAllMocks();vi.unstubAllGlobals();});
function renderHistory(strict:boolean){const child=<QueryClientProvider client={query}><RevisionHistory chapter={chapter} sessionToken='' onRestored={vi.fn()} /></QueryClientProvider>;return render(strict?<StrictMode>{child}</StrictMode>:child);}
it.each([false,true])('initial history remains visible through live-root StrictMode=%s',async strict=>{
 let resolve!:(rows:any[])=>void;
 const pending=new Promise<any[]>(done=>{resolve=done});
 const spy=vi.spyOn(api,'legacyHistory').mockReturnValue(pending);
 renderHistory(strict);
 await waitFor(()=>expect(spy).toHaveBeenCalled());
 await act(async()=>resolve([revision]));
 expect(await screen.findByRole('button',{name:/版本 1/})).toBeTruthy();
});
it('history and restore fetch use captured context rather than changed API globals',async()=>{
 const calls:{url:string;headers:any}[]=[];
 const fetcher=vi.fn(async(url:string,init?:RequestInit)=>{calls.push({url,headers:init?.headers});return {ok:true,status:200,json:async()=>url.includes('/restore')?{...chapter,version:3}:url.includes('/revisions/1')?revision:{items:[revision]}};});
 vi.stubGlobal('fetch',fetcher);
 const scope={workspaceId:'w-a',projectId:'audit-novel',storylineId:'s-a',branchId:'b-a'};
 const context={sessionToken:'synthetic-token-a',scope,actor:{id:'actor-a',displayName:'Synthetic',workspaceId:'w-a'}};
 setCollaborationContext({sessionToken:'synthetic-token-b',scope:{...scope,branchId:'b-b'}});
 await api.history(scope,chapter.id,context);await api.revisionDetail(scope,chapter.id,1,context);await api.restore(chapter.id,1,2,context);
 expect(calls).toHaveLength(3);
 expect(calls.every(call=>call.headers['X-Session-Token']==='synthetic-token-a'&&call.headers['X-Branch-Id']==='b-a')).toBe(true);
});
