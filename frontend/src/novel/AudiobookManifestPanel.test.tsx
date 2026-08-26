// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { TASK_SUMMARY_EVENT } from "../ui/taskSummary";
import { AudiobookManifestPanel } from "./AudiobookManifestPanel";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

it("publishes audiobook jobs separately and inspects one chapter",async()=>{
  vi.spyOn(api,"audiobookManifest").mockResolvedValue({ready_chapters:0,total_chapters:0,chapters:[]});
  vi.spyOn(api,"audiobookJobs").mockResolvedValue({items:[{id:"job-1",chapter_id:"chapter-1",status:"FAILED",voice:"alloy",error:"合成超时"}]});
  vi.spyOn(api,"audiobookMixPlan").mockResolvedValue({tracks:[],mix_status:"EMPTY"});
  const inspect=vi.fn(),summaries:any[]=[];
  const listener=(event:Event)=>summaries.push((event as CustomEvent).detail);
  window.addEventListener(TASK_SUMMARY_EVENT,listener);
  render(<AudiobookManifestPanel novelId="novel-1" onInspect={inspect}/>);
  fireEvent.click(await screen.findByRole("button",{name:"检查 chapter-1"}));
  expect(inspect).toHaveBeenCalledWith(expect.objectContaining({kind:"audiobook",id:"job-1",chapterId:"chapter-1",status:"FAILED",error:"合成超时"}));
  await waitFor(()=>expect(summaries.at(-1)).toMatchObject({source:"audiobook",summary:{failed:1,failures:[{id:"job-1",error:"合成超时"}]}}));
  window.removeEventListener(TASK_SUMMARY_EVENT,listener);
});
