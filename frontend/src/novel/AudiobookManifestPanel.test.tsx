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
  vi.spyOn(api,"audioProductionSettings").mockResolvedValue({novel_id:"novel-1",voice_bindings:[],pronunciation_dictionary:[]});
  const inspect=vi.fn(),summaries:any[]=[];
  const listener=(event:Event)=>summaries.push((event as CustomEvent).detail);
  window.addEventListener(TASK_SUMMARY_EVENT,listener);
  render(<AudiobookManifestPanel novelId="novel-1" onInspect={inspect}/>);
  fireEvent.click(await screen.findByRole("button",{name:"检查"}));
  expect(inspect).toHaveBeenCalledWith(expect.objectContaining({kind:"audiobook",id:"job-1",chapterId:"chapter-1",status:"FAILED",error:"合成超时"}));
  await waitFor(()=>expect(summaries.at(-1)).toMatchObject({source:"audiobook",summary:{failed:1,failures:[{id:"job-1",error:"合成超时"}]}}));
  window.removeEventListener(TASK_SUMMARY_EVENT,listener);
});

it("cancels a queued job and saves character voice and pronunciation settings",async()=>{
  vi.spyOn(api,"audiobookManifest").mockResolvedValue({ready_chapters:0,total_chapters:0,chapters:[]});
  vi.spyOn(api,"audiobookJobs").mockResolvedValue({items:[{id:"job-2",chapter_id:"chapter-2",status:"QUEUED",provider_id:"openai",model_id:"tts-1",voice:"nova",attempt:0}]});
  vi.spyOn(api,"audiobookMixPlan").mockResolvedValue({tracks:[],mix_status:"EMPTY"});
  vi.spyOn(api,"audioProductionSettings").mockResolvedValue({novel_id:"novel-1",voice_bindings:[],pronunciation_dictionary:[]});
  const cancel=vi.spyOn(api,"cancelAudiobookJob").mockResolvedValue({status:"CANCELLED"}),save=vi.spyOn(api,"updateAudioProductionSettings").mockResolvedValue({});
  render(<AudiobookManifestPanel novelId="novel-1"/>);
  fireEvent.click(await screen.findByRole("button",{name:"取消"}));
  await waitFor(()=>expect(cancel).toHaveBeenCalledWith("novel-1","job-2"));
  fireEvent.click(screen.getByText("制作配置"));
  fireEvent.change(screen.getByLabelText("角色 ID"),{target:{value:"character-1"}});
  fireEvent.click(screen.getByRole("button",{name:"保存角色声线"}));
  await waitFor(()=>expect(save).toHaveBeenCalledWith("novel-1",expect.objectContaining({voice_bindings:[expect.objectContaining({character_id:"character-1"})]})));
});
