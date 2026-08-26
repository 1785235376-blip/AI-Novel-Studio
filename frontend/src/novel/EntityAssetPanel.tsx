import {AssetLibraryPanel} from './AssetLibraryPanel';

export function EntityAssetPanel({novelId,characterId,sceneId}:{novelId:string;characterId?:string;sceneId?:string}){
  return <AssetLibraryPanel novelId={novelId} characterId={characterId} sceneId={sceneId}/>;
}
