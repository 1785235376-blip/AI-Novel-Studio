// @vitest-environment jsdom
import { act, cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { InteractiveStoryPreview } from './InteractiveStoryPreview';
import type { interactiveStoryClient, InteractiveStory, StoryPlay } from './interactiveStoryClient';
afterEach(cleanup);
const story:InteractiveStory={id:'story',version:1,status:'APPROVED',stale:false,content_withheld:false};
const play=(path:string[]):StoryPlay=>({node:{node_id:'node',node_version:1,title:path.length?'Ending':'Entry',dialogue:'Original story',character_id:null,background_asset_id:null,music_asset_id:null,ending:path.length?'Done':''},choices:path.length?[]:[{id:'go',label:'Proceed',enabled:true}],variables:{score:path.length},steps:path.length,max_steps:4,status:path.length?'ENDING':'PLAYING',path:[...path]});
const handler=(element:HTMLElement)=>(element as any)[Object.keys(element).find(k=>k.startsWith('__reactProps$'))!].onClick;
it('replays the shorter path through the original service and uses its returned variables',async()=>{
 const run=vi.fn(async(_story:InteractiveStory,path:string[])=>play(path));const api={play:run} as unknown as ReturnType<typeof interactiveStoryClient>;
 render(<InteractiveStoryPreview api={api} story={story} blocked={false}/>);expect(run).not.toHaveBeenCalled();
 fireEvent.click(screen.getByRole('button',{name:'从开头试玩'}));fireEvent.click(await screen.findByRole('button',{name:'Proceed'}));
 fireEvent.click(await screen.findByRole('button',{name:'回退一步并重新核验'}));await screen.findByRole('button',{name:'Proceed'});
 expect(run.mock.calls.map(row=>row[1])).toEqual([[],['go'],[]]);expect(screen.getByText('score = 0')).toBeTruthy();expect(story.version).toBe(1);
});
it('rejects a retained choice after another request has consumed the displayed path',async()=>{
 let resolve!:(value:StoryPlay)=>void;
 const run=vi.fn().mockResolvedValueOnce(play([])).mockImplementation(()=>new Promise<StoryPlay>(done=>{resolve=done;}));const api={play:run} as unknown as ReturnType<typeof interactiveStoryClient>;
 render(<InteractiveStoryPreview api={api} story={story} blocked={false}/>);fireEvent.click(screen.getByRole('button',{name:'从开头试玩'}));const choose=handler(await screen.findByRole('button',{name:'Proceed'}));
 act(()=>{choose();choose();});expect(run).toHaveBeenCalledTimes(2);await act(async()=>resolve(play(['go'])));act(()=>choose());expect(run).toHaveBeenCalledTimes(2);
});
it('hides old results and rejects retained actions and late data across client ownership changes',async()=>{
 const first=vi.fn(async()=>play(['go']));const api={play:first} as unknown as ReturnType<typeof interactiveStoryClient>;const view=render(<InteractiveStoryPreview api={api} story={story} blocked={false}/>);
 fireEvent.click(screen.getByRole('button',{name:'从开头试玩'}));const back=handler(await screen.findByRole('button',{name:'回退一步并重新核验'}));
 const second=vi.fn(async()=>play([]));view.rerender(<InteractiveStoryPreview api={{play:second} as unknown as ReturnType<typeof interactiveStoryClient>} story={story} blocked={false}/>);
 expect(screen.queryByLabelText('互动故事播放')).toBeNull();act(()=>back());expect(first).toHaveBeenCalledTimes(1);expect(second).not.toHaveBeenCalled();
});
it.each(['stale','content_withheld'] as const)('does not replay a %s source',field=>{
 const run=vi.fn();render(<InteractiveStoryPreview api={{play:run} as unknown as ReturnType<typeof interactiveStoryClient>} story={{...story,[field]:true}} blocked={false}/>);
 fireEvent.click(screen.getByRole('button',{name:'从开头试玩'}));expect(run).not.toHaveBeenCalled();
});

it('does not display late owner data or claim a stale request updated the new preview',async()=>{
 let resolve!:(value:StoryPlay)=>void;const api={play:vi.fn(()=>new Promise<StoryPlay>(done=>{resolve=done;}))} as unknown as ReturnType<typeof interactiveStoryClient>;
 const view=render(<InteractiveStoryPreview api={api} story={story} blocked={false}/>);fireEvent.click(screen.getByRole('button',{name:'从开头试玩'}));
 view.rerender(<InteractiveStoryPreview api={api} story={{...story,version:2}} blocked={false}/>);await act(async()=>resolve(play(['go'])));
 expect(screen.queryByLabelText('互动故事播放')).toBeNull();expect(screen.queryByText('预览状态已更新。')).toBeNull();
});
