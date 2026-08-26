// @vitest-environment jsdom
import {afterEach,describe,expect,it} from 'vitest';
import {generationRecovery} from './generationRecovery';

afterEach(()=>sessionStorage.clear());
describe('generation recovery metadata',()=>{
  it('persists only resumable task metadata in session storage',()=>{
    generationRecovery.save('file',{chapterId:'n:1',jobId:'job-1',original:'正文',baseChapterVersion:2});
    expect(generationRecovery.load('file','n:1')).toEqual({chapterId:'n:1',jobId:'job-1',original:'正文',baseChapterVersion:2});
    expect(sessionStorage.getItem('ai-novel-studio:generation:file:n:1')).not.toContain('credential');
  });
  it('isolates chapters and clears completed work',()=>{
    generationRecovery.save('branch-a',{chapterId:'c1',jobId:'a'});
    expect(generationRecovery.load('branch-b','c1')).toBeUndefined();
    generationRecovery.remove('branch-a','c1');
    expect(generationRecovery.load('branch-a','c1')).toBeUndefined();
  });
});
