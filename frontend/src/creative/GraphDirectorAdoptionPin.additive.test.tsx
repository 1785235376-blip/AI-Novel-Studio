// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import type { ComponentProps } from 'react';
import { GraphDirectorConsole, type GraphDirectorSource } from './GraphDirectorConsole';
import type { GraphDirectorProposalReview } from './GraphDirectorProposalReview';
import { newDocument, type CreativeDocument } from './types';
const probe=vi.hoisted(()=>({review:undefined as ComponentProps<typeof GraphDirectorProposalReview>|undefined}));
vi.mock('./GraphDirectorProposalReview',()=>({hasDirectorProposalReview:()=>true,GraphDirectorProposalReview:(props:ComponentProps<typeof GraphDirectorProposalReview>)=>{probe.review=props;return null;}}));
afterEach(()=>{cleanup();probe.review=undefined;});
const pin={id:'adopted',version:1,digest:'b'.repeat(64)};
async function setup(digest=pin.digest){
 const document:CreativeDocument={...newDocument('DIRECTOR'),id:pin.id,version:pin.version,title:'Adopted draft',status:'DRAFT',actor_id:'author',created_at:'',updated_at:'',source_evidence:{}};
 const client={capabilities:vi.fn().mockResolvedValue({enabled:true,can_mutate:true,modes:['DIRECTOR']}),
 export:vi.fn().mockResolvedValue({document,document_digest:digest}),list:vi.fn(),create:vi.fn(),update:vi.fn()} as unknown as GraphDirectorSource;
 const handoff={scope:{},verificationScope:{},isVerificationCurrent:()=>true,available:true,insert:vi.fn().mockReturnValue(true)};
 render(<GraphDirectorConsole client={client} canvasHandoff={handoff} active canMutate busy={false} isCurrent={()=>true} read={work=>work()} mutate={work=>work()} onDirtyChange={vi.fn()}/>);
 fireEvent.click(screen.getByRole('button',{name:'打开导演总控台'}));await waitFor(()=>expect(probe.review).toBeTruthy());
 return {document,client,handoff};
}
const add=()=>screen.getByRole('button',{name:'将此审核草稿添加到画布'}) as HTMLButtonElement;
const inspect=()=>fireEvent.click(screen.getByRole('button',{name:'核对导演原文档版本'}));
it('retains the model adoption digest while requiring a fresh original export before insertion',async()=>{
 const e=await setup();const expected={...pin};act(()=>probe.review!.onDocument(e.document,expected));expected.digest='f'.repeat(64);
 expect(add().disabled).toBe(true);expect(e.handoff.insert).not.toHaveBeenCalled();inspect();await waitFor(()=>expect(add().disabled).toBe(false));
 fireEvent.click(add());expect(e.handoff.insert).toHaveBeenCalledWith(pin,e.handoff.scope);expect(e.client.create).not.toHaveBeenCalled();expect(e.client.update).not.toHaveBeenCalled();
});
it('rejects a same-version substituted digest and keeps the original anchor for a later exact read',async()=>{
 const e=await setup('f'.repeat(64));act(()=>probe.review!.onDocument(e.document,pin));inspect();
 await screen.findByText(/同一审核版本的摘要不匹配/);expect(add().disabled).toBe(true);expect(e.handoff.insert).not.toHaveBeenCalled();
 vi.mocked(e.client.export).mockResolvedValue({document:e.document,document_digest:pin.digest,format:'',boundary:''});inspect();await waitFor(()=>expect(add().disabled).toBe(false));
});
it.each([{...pin,id:'other'},{...pin,version:2},{...pin,digest:'invalid'}])('rejects an invalid incoming model pin before staging %o',async incoming=>{
 const e=await setup();expect(()=>act(()=>probe.review!.onDocument(e.document,incoming))).toThrow();expect(e.handoff.insert).not.toHaveBeenCalled();
 expect(screen.queryByRole('button',{name:'将此审核草稿添加到画布'})).toBeNull();
});
