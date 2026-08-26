import { useState } from "react";
import type { Asset } from "../api";
import { AssetInspector } from "../novel/AssetInspector";
import { AssetLibraryPanel } from "../novel/AssetLibraryPanel";
import { AppShell, type ScopeLabels, type StudioModule } from "./AppShell";

export function AssetWorkspaceRoute({ module, onModuleChange, scope, actor, novelId }: { module: StudioModule; onModuleChange: (module: StudioModule) => void; scope: ScopeLabels; actor: string; novelId: string }) {
  const [selected, setSelected] = useState<Asset>();
  return <AppShell module={module} onModuleChange={onModuleChange} scope={scope} actor={actor} sidebar={<></>} main={<AssetLibraryPanel novelId={novelId} selectedAssetId={selected?.id} onSelectAsset={setSelected}/>} inspector={<AssetInspector asset={selected} novelId={novelId}/>} status={<>资产库</>}/>;
}
