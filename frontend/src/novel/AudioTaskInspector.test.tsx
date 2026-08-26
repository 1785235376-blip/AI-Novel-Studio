// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { AudioTaskInspector } from "./AudioTaskInspector";

afterEach(cleanup);

it("plays only a real speech result",()=>{
  render(<AudioTaskInspector novelId="novel-1" inspection={{kind:"speech",id:"speech-task",status:"SUCCEEDED",providerId:"openai",modelId:"gpt-4o-mini-tts",voice:"alloy",emotion:"neutral",audioUri:"https://example.test/audio.mp3"}}/>);
  expect(screen.getByLabelText("当前语音生成结果").getAttribute("src")).toBe("https://example.test/audio.mp3");
  expect(screen.getByText("alloy")).toBeTruthy();
});

it("shows an audiobook failure without fabricating audio",()=>{
  render(<AudioTaskInspector novelId="novel-1" inspection={{kind:"audiobook",id:"job-1",status:"FAILED",chapterId:"chapter-2",error:"合成超时"}}/>);
  expect(screen.queryByLabelText("当前语音生成结果")).toBeNull();
  expect(screen.getByRole("alert").textContent).toContain("合成超时");
  expect(screen.getByText("chapter-2")).toBeTruthy();
});
