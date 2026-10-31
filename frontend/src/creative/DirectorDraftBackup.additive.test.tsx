// @vitest-environment jsdom
import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {directorDraftBackup} from './directorDraftBackup';
import {GraphDirectorConsole,type GraphDirectorSource} from './GraphDirectorConsole';
import {newDocument,type CreativeDocument} from './types';
import {downloadPortableBlob} from '../experimental/portableProjectsClient';
vi.mock('../experimental/portableProjectsClient',()=>({downloadPortableBlob:vi.fn()}));
afterEach(()=>{cleanup();vi.clearAllMocks();});
const readBlob=(blob:Blob)=>new Promise<string>((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(String(reader.result));reader.onerror=reject;reader.readAsText(blob);});
it('backs up incomplete author input without pretending it is saved or serializing original owner metadata',async()=>{
 const draft={...newDocument('DIRECTOR'),title:'未完成',source_independent:true};
 const base={...draft,id:'source',version:3,status:'DRAFT',created_at:'',updated_at:'',actor_id:'private-actor',source_evidence:{private_field:'not-author-input'}} as CreativeDocument;
 const blob=directorDraftBackup(base,base,{id:'source',version:2,digest:'a'.repeat(64)},true),value=JSON.parse(await readBlob(blob));
 expect(value).toMatchObject({contract:'studio-director-author-draft-backup/1',server_save_confirmed:false,execution_authority:false,save_outcome:'UNKNOWN_OR_CONFLICT',base_reference:{id:'source',version:3},draft});
 expect(value.base_reference.digest).toBeUndefined();expect(value.draft.actor_id).toBeUndefined();expect(value.draft.source_evidence).toBeUndefined();expect(base.source_evidence.private_field).toBe('not-author-input');
 expect(()=>directorDraftBackup({...draft,title:'x'.repeat(2*1024*1024)},base,undefined,false)).toThrow(/超过 2 MiB/);
});
it('exports only on explicit action, keeps dirty state, and never creates or updates the owner',async()=>{
 const client={capabilities:vi.fn(async()=>({enabled:true,can_mutate:true,modes:['DIRECTOR']})),create:vi.fn(),update:vi.fn(),export:vi.fn(),history:vi.fn(),list:vi.fn(),derive:vi.fn()} as unknown as GraphDirectorSource;
 const dirty=vi.fn(),props={client,active:true,canMutate:true,busy:false,isCurrent:()=>true,read:async<T,>(work:()=>Promise<T>)=>work(),mutate:async<T,>(work:()=>Promise<T>)=>work(),onDirtyChange:dirty};
 const view=render(<GraphDirectorConsole {...props}/>);fireEvent.click(screen.getByText('打开导演总控台'));await waitFor(()=>expect((screen.getByLabelText('文档标题') as HTMLInputElement).closest('fieldset')!.disabled).toBe(false));
 fireEvent.change(screen.getByLabelText('文档标题'),{target:{value:'Local unsaved work'}});expect(downloadPortableBlob).not.toHaveBeenCalled();fireEvent.click(screen.getByText('下载导演未保存草稿备份'));
 expect(downloadPortableBlob).toHaveBeenCalledTimes(1);const value=JSON.parse(await readBlob(vi.mocked(downloadPortableBlob).mock.calls[0][0]));expect(value.draft.title).toBe('Local unsaved work');expect(value.save_outcome).toBe('LOCAL_UNSAVED');
 expect(client.create).not.toHaveBeenCalled();expect(client.update).not.toHaveBeenCalled();expect(client.export).not.toHaveBeenCalled();expect(dirty).toHaveBeenLastCalledWith(true);
 view.rerender(<GraphDirectorConsole {...props} canMutate={false}/>);fireEvent.click(screen.getByText('下载导演未保存草稿备份'));expect(downloadPortableBlob).toHaveBeenCalledTimes(1);
});
