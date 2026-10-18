// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen, within } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { GraphDirectorCompareDeck } from './GraphDirectorCompareDeck';
import { fixtureProjection } from '../director/directorWorkspaceFixtures.testFixture';
import { blankGraph } from './graphDraft';
import type { StudioGraphDefinition } from './studioGraphTypes';
const definition=():StudioGraphDefinition=>({...blankGraph(),schema_version:4,nodes:[1,2,3,4].map(i=>({id:`director${i}`,definition_id:'director_plan',definition_version:1,enabled:true,position:{x:i*400,y:0},parameters:{document_snapshot:{id:`document${i}`,version:i,digest:String(i).repeat(64)}}}))});
function fixture(){return {definition:definition(),identity:'owner',active:true,isCurrent:()=>true,read:async<T,>(work:()=>Promise<T>)=>work(),client:{readDirectorWorkspace:vi.fn(async(pin:any)=>{const value=fixtureProjection();value.document={...value.document,id:pin.id,version:pin.version,mode:'DIRECTOR',title:`Title ${pin.id}`};return value;})}};}
const choose=(id:number)=>fireEvent.click(screen.getByRole('checkbox',{name:new RegExp(`对照 director${id}`)}));
const expand=(id:number)=>fireEvent.click(within(screen.getByLabelText(`导演对照 director${id}`)).getByRole('button',{name:'展开导演控制台并核对来源'}));
afterEach(()=>{cleanup();vi.restoreAllMocks();});
it('opens independent original director projections only after explicit expansion and caps windows',async()=>{
 const props=fixture();render(<GraphDirectorCompareDeck {...props}/>);expect(props.client.readDirectorWorkspace).not.toHaveBeenCalled();
 choose(1);choose(2);choose(3);expect((screen.getByRole('checkbox',{name:/对照 director4/}) as HTMLInputElement).disabled).toBe(true);expect(props.client.readDirectorWorkspace).not.toHaveBeenCalled();
 expand(1);expand(2);await screen.findByText('Title document1');await screen.findByText('Title document2');expect(props.client.readDirectorWorkspace).toHaveBeenCalledTimes(2);
 expect(props.client.readDirectorWorkspace.mock.calls.map(([pin])=>pin.id)).toEqual(['document1','document2']);
 choose(3);expect((screen.getByRole('checkbox',{name:/对照 director4/}) as HTMLInputElement).disabled).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'关闭全部导演对照'}));expect(screen.queryByText('Title document1')).toBeNull();
});
it('switching source pins clears all private projections and aborts a pending read',async()=>{
 const props=fixture();let finish!:(value:any)=>void;props.client.readDirectorWorkspace.mockImplementation(()=>new Promise(resolve=>finish=resolve));
 const view=render(<GraphDirectorCompareDeck {...props}/>);choose(1);expand(1);const signal=(props.client.readDirectorWorkspace.mock.calls[0] as any)[1] as AbortSignal;
 const next=definition();next.nodes[0].parameters.document_snapshot!.version=5;view.rerender(<GraphDirectorCompareDeck {...props} definition={next}/>);expect(signal.aborted).toBe(true);
 const value=fixtureProjection();value.document={...value.document,id:'document1',version:1,mode:'DIRECTOR',title:'OLD PRIVATE'};await act(async()=>finish(value));expect(screen.queryByText('OLD PRIVATE')).toBeNull();expect(screen.queryByLabelText('导演对照 director1')).toBeNull();
});
it('retiring authority hides and clears previously opened consoles',async()=>{
 const props=fixture();const view=render(<GraphDirectorCompareDeck {...props}/>);choose(1);expand(1);await screen.findByText('Title document1');
 view.rerender(<GraphDirectorCompareDeck {...props} active={false}/>);expect(screen.queryByText('Title document1')).toBeNull();view.rerender(<GraphDirectorCompareDeck {...props}/>);expect(screen.queryByLabelText('导演对照 director1')).toBeNull();expect(props.client.readDirectorWorkspace).toHaveBeenCalledTimes(1);
});
it('replacing the client authority clears selection without reading through the new client',async()=>{
 const props=fixture();const view=render(<GraphDirectorCompareDeck {...props}/>);choose(1);expand(1);await screen.findByText('Title document1');
 const replacement=fixture().client;view.rerender(<GraphDirectorCompareDeck {...props} client={replacement}/>);
 expect(screen.queryByLabelText('导演对照 director1')).toBeNull();expect(replacement.readDirectorWorkspace).not.toHaveBeenCalled();
});
