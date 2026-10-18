// @vitest-environment jsdom
import {act,cleanup,fireEvent,render,screen} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {DirectorWorkspace} from './DirectorWorkspace';
import {fixtureProjection} from './directorWorkspaceFixtures.testFixture';
import type {DirectorWorkspaceProjection} from './directorWorkspaceTypes';
afterEach(cleanup);
it('keeps explicit local camera selection visible and discards it on exact source refresh',async()=>{
 const client={readDirectorWorkspace:vi.fn(async()=>fixtureProjection())};render(<DirectorWorkspace client={client} documentId="doc-1"/>);await screen.findByLabelText('镜头卡');const select=screen.getAllByLabelText('景别')[0] as HTMLSelectElement;
 fireEvent.change(select,{target:{value:'CLOSE_UP'}});expect(select.value).toBe('CLOSE_UP');expect(screen.getByText(/本地镜头语言草稿 1 项/)).toBeTruthy();
 fireEvent.click(screen.getByText('重新读取原文档'));await screen.findByLabelText('镜头卡');expect((screen.getAllByLabelText('景别')[0] as HTMLSelectElement).value).toBe('WIDE');expect(screen.queryByText(/本地镜头语言草稿 1 项/)).toBeNull();
});
it('does not expose old source or local drafts while a different document is pending',async()=>{
 let finish!:(p:DirectorWorkspaceProjection)=>void;const client={readDirectorWorkspace:vi.fn((id:string)=>id==='doc-1'?Promise.resolve(fixtureProjection()):new Promise<DirectorWorkspaceProjection>(resolve=>{finish=resolve;}))};const view=render(<DirectorWorkspace client={client} documentId="doc-1"/>);await screen.findByLabelText('镜头卡');fireEvent.change(screen.getAllByLabelText('景别')[0],{target:{value:'CLOSE_UP'}});view.rerender(<DirectorWorkspace client={client} documentId="doc-2"/>);expect(screen.queryByLabelText('镜头卡')).toBeNull();const other=fixtureProjection();other.document={...other.document,id:'doc-2',title:'Other'};await act(async()=>finish(other));expect(screen.queryByText(/本地镜头语言草稿 1 项/)).toBeNull();
});

it('explicit reset restores stored values and refresh retires even a reused result object',async()=>{
 const same=fixtureProjection(),client={readDirectorWorkspace:vi.fn(async()=>same)};render(<DirectorWorkspace client={client} documentId="doc-1"/>);await screen.findByLabelText('镜头卡');fireEvent.change(screen.getAllByLabelText('景别')[0],{target:{value:'CLOSE_UP'}});fireEvent.click(screen.getByText('清除本次镜头语言草稿'));expect((screen.getAllByLabelText('景别')[0] as HTMLSelectElement).value).toBe('WIDE');fireEvent.change(screen.getAllByLabelText('景别')[0],{target:{value:'MEDIUM'}});fireEvent.click(screen.getByText('重新读取原文档'));await screen.findByLabelText('镜头卡');expect(screen.queryByText(/本地镜头语言草稿 1 项/)).toBeNull();expect(same.shot_cards[0].camera.shot_size).toBe('WIDE');
});
it('client replacement and inactive transition immediately retire the old projection and draft',async()=>{
 const client={readDirectorWorkspace:vi.fn(async()=>fixtureProjection())};const view=render(<DirectorWorkspace client={client} documentId="doc-1"/>);await screen.findByLabelText('镜头卡');fireEvent.change(screen.getAllByLabelText('景别')[0],{target:{value:'CLOSE_UP'}});view.rerender(<DirectorWorkspace client={client} documentId="doc-1" active={false}/>);expect(screen.queryByLabelText('镜头卡')).toBeNull();view.rerender(<DirectorWorkspace client={client} documentId="doc-1"/>);await screen.findByLabelText('镜头卡');expect(screen.queryByText(/本地镜头语言草稿 1 项/)).toBeNull();let finish!:(p:DirectorWorkspaceProjection)=>void;const replacement={readDirectorWorkspace:vi.fn(()=>new Promise<DirectorWorkspaceProjection>(r=>{finish=r;}))};view.rerender(<DirectorWorkspace client={replacement} documentId="doc-1"/>);expect(screen.queryByLabelText('镜头卡')).toBeNull();view.unmount();await act(async()=>finish(fixtureProjection()));expect(screen.queryByLabelText('镜头卡')).toBeNull();
});
