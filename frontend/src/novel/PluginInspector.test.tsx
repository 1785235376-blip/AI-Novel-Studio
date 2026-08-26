// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, expect, it } from "vitest";
import { PluginInspector } from "./PluginInspector";
afterEach(cleanup);
it("renders manifest capabilities and truthful execution boundary",()=>{render(<PluginInspector inspection={{id:"story-tools",name:"故事工具",version:"1.0.0",status:"MANIFEST_ACTIVE",capabilities:["context"],requestedPermissions:["novel.read"],grantedPermissions:["novel.read"],executionSupported:false,sandbox:"NOT_CONFIGURED",isolation:"DENY_ALL"}}/>);expect(screen.getByText("故事工具")).toBeTruthy();expect(screen.getByText(/代码执行：当前禁止/)).toBeTruthy();expect(screen.getAllByText("novel.read")).toHaveLength(2);expect(screen.getByText("context")).toBeTruthy();});
