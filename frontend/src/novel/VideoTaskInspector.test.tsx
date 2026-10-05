// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it, vi } from "vitest";
import { motionTaskInspection } from "./ScreenplayPanel";
import {api} from "../api";
import { VideoTaskInspector } from "./VideoTaskInspector";

afterEach(()=>{cleanup();vi.restoreAllMocks()});

it("maps and renders an authenticated Motion Task asset", async () => {
  const download=vi.spyOn(api,"assetDownload").mockResolvedValue(new Blob(["fixture"],{type:"video/mp4"}));
  Object.defineProperty(URL,"createObjectURL",{configurable:true,value:vi.fn(()=>"blob:verified-video")});
  Object.defineProperty(URL,"revokeObjectURL",{configurable:true,value:vi.fn()});
  const inspection=motionTaskInspection({id:"motion-1",status:"SUCCEEDED",transition_id:"transition-1",provider_id:"seedance",model_id:"video-2.5",progress:100,start_frame:"https://example.test/start.png",end_frame:"https://example.test/end.png",result:{url:"https://example.test/result.mp4",asset_id:"asset-video-1"}},"screenplay-1");
  render(<VideoTaskInspector inspection={inspection} novelId="novel-1"/>);
  expect((await screen.findByLabelText("当前视频生成结果")).getAttribute("src")).toBe("blob:verified-video");
  expect(download).toHaveBeenCalledWith("asset-video-1","novel-1");
  expect(screen.getByAltText("Motion Task 起始帧")).toBeTruthy();
  expect(screen.getByText("asset-video-1")).toBeTruthy();
  expect(inspection).not.toHaveProperty("prompt");
});

it("shows running progress without fabricating a video", () => {
  render(<VideoTaskInspector inspection={{id:"motion-2",status:"RUNNING",progress:42}} novelId="novel-1"/>);
  expect(screen.getByRole("progressbar").getAttribute("aria-valuenow")).toBe("42");
  expect(screen.queryByLabelText("当前视频生成结果")).toBeNull();
  expect(screen.getByText("尚无真实视频结果")).toBeTruthy();
});

it("announces a safe failure summary", () => {
  render(<VideoTaskInspector inspection={{id:"motion-3",status:"FAILED",error:"Provider 超时"}} novelId="novel-1"/>);
  expect(screen.getByRole("alert").textContent).toContain("Provider 超时");
});
