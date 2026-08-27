// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { api } from "../api";
import { TASK_SUMMARY_EVENT } from "../ui/taskSummary";
import { SpeechSynthesisPanel } from "./SpeechSynthesisPanel";

afterEach(()=>{cleanup();vi.restoreAllMocks();});

it("publishes speech lifecycle and a minimal inspector contract",async()=>{
  vi.spyOn(api,"audioProviders").mockResolvedValue({domain:"AUDIO",routing_policy:"LOCAL_FIRST",items:[]});
  vi.spyOn(api,"speechGenerations").mockResolvedValue({items:[]});
  vi.spyOn(api,"speechSynthesize").mockResolvedValue({provider_id:"openai",model_id:"gpt-4o-mini-tts",voice:"alloy",audio_uri:"https://example.test/voice.mp3"});
  const inspect=vi.fn(),summaries:any[]=[];
  const listener=(event:Event)=>summaries.push((event as CustomEvent).detail);
  window.addEventListener(TASK_SUMMARY_EVENT,listener);
  render(<SpeechSynthesisPanel novelId="novel-1" onInspect={inspect}/>);
  fireEvent.click(screen.getByRole("button",{name:"生成语音"}));
  expect(await screen.findByLabelText("当前语音生成结果")).toBeTruthy();
  await waitFor(()=>expect(inspect).toHaveBeenLastCalledWith(expect.objectContaining({kind:"speech",id:expect.stringMatching(/^speech-/),status:"SUCCEEDED",audioUri:"https://example.test/voice.mp3"})));
  expect(inspect.mock.calls.at(-1)?.[0]).not.toHaveProperty("text");
  expect(summaries.at(-1)).toMatchObject({source:"speech",summary:{succeeded:1}});
  window.removeEventListener(TASK_SUMMARY_EVENT,listener);
});

it("publishes a failed speech task without audio",async()=>{
  vi.spyOn(api,"audioProviders").mockResolvedValue({domain:"AUDIO",routing_policy:"LOCAL_FIRST",items:[]});
  vi.spyOn(api,"speechGenerations").mockResolvedValue({items:[]});
  vi.spyOn(api,"speechSynthesize").mockRejectedValue(new Error("offline"));
  render(<SpeechSynthesisPanel novelId="novel-1"/>);
  fireEvent.click(screen.getByRole("button",{name:"生成语音"}));
  expect(await screen.findByRole("alert")).toBeTruthy();
  expect(screen.queryByLabelText("当前语音生成结果")).toBeNull();
});

it("lists configured cloud speech providers from the control center catalog",async()=>{
  vi.spyOn(api,"audioProviders").mockResolvedValue({domain:"AUDIO",routing_policy:"LOCAL_FIRST",items:[{provider_id:"custom-audio",display_name:"自定义声音云",endpoint:"https://audio.example/v1",default_model:"voice-pro",local:false,requires_credential:true,configured:true,capabilities:["TTS"]}]});
  render(<SpeechSynthesisPanel/>);
  expect(await screen.findByRole("option",{name:"自定义声音云"})).toBeTruthy();
  fireEvent.change(screen.getByLabelText("语音 Provider"),{target:{value:"custom-audio"}});
  expect((screen.getByDisplayValue("voice-pro") as HTMLInputElement).value).toBe("voice-pro");
});
