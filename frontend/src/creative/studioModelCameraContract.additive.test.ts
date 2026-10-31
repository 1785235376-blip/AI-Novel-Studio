import {createHash,webcrypto} from 'node:crypto';
import {afterEach,beforeEach,expect,it,vi} from 'vitest';
import {checkedModelCameras,checkedModelCameraExport,checkedModelCameraSelection,modelCameraSelection,type ModelCameras,type ModelCameraExport} from './studioModelCameraContract';
import {cameraAsset,cameraReview,cameraChoice,cameraExport,rewriteCameraDocument} from './studioModelCamera.testFixtures';
import {studioClient,type StudioAsset} from './studioClient';
import wire from './modelCameraWire.testFixture.json';

beforeEach(()=>{vi.stubGlobal('crypto',webcrypto);});
afterEach(()=>vi.unstubAllGlobals());
it('accepts genuine reopened File-owner camera inspection and exact exported glTF bytes',async()=>{
  const asset=wire.asset as StudioAsset,review=checkedModelCameras(wire.inspection,asset),choice=modelCameraSelection(review,asset,wire.request.node_index);
  expect(createHash('sha256').update(Buffer.from(wire.source_glb_base64,'base64')).digest('hex')).toBe(asset.sha256);
  expect(await checkedModelCameraExport(wire.result,asset,choice)).toEqual(wire.result);
  const fetch=vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/cameras')?wire.inspection:wire.result),{status:200}));vi.stubGlobal('fetch',fetch);
  const client=studioClient(asset.novel_id,{sessionToken:'fixture-session'});
  expect(await client.inspectModelCameras(asset)).toEqual(wire.inspection);
  expect(await client.exportModelCamera(asset,choice)).toEqual(wire.result);
  const calls=fetch.mock.calls as unknown as [string,RequestInit][];expect(JSON.parse(String(calls[1][1].body))).toEqual(wire.request);
});
it('validates camera definitions, shared instances, perspective omission and orthographic zero near without recentering',async()=>{
  expect(checkedModelCameras(cameraReview(),cameraAsset)).toEqual(cameraReview());
  for(const node of [0,1,2]) {
    const choice=modelCameraSelection(cameraReview(),cameraAsset,node),result=cameraExport(choice);
    expect(await checkedModelCameraExport(result,cameraAsset,choice)).toEqual(result);
  }
  expect(modelCameraSelection(cameraReview(),cameraAsset,0).camera.world_matrix[12]).toBe(120);
  const review=cameraReview();review.camera_inspection.instances=[];review.camera_inspection.camera_definition_count=0;
  expect(checkedModelCameras(review,cameraAsset).camera_inspection.instances).toEqual([]);
  expect(()=>modelCameraSelection(review,cameraAsset,0)).toThrow();
});
it('accepts finite far/aspect and keeps caller objects detached',async()=>{
  const choice=cameraChoice();if(choice.camera.projection.type!=='perspective')throw new Error();
  choice.camera.projection.aspectRatio=16/9;choice.camera.projection.zfar=500;
  const original=cameraExport(choice),pending=checkedModelCameraExport(original,cameraAsset,choice);
  original.camera_export.camera.world_matrix[12]=999;choice.camera.world_matrix[12]=888;
  expect((await pending).camera_export.camera.world_matrix[12]).toBe(120);
  const review=cameraReview(),checked=checkedModelCameras(review,cameraAsset);review.camera_inspection.instances[0].world_matrix[12]=777;
  expect(checked.camera_inspection.instances[0].world_matrix[12]).toBe(120);
});
const invalidInspections:Record<string,(review:ModelCameras)=>void>={
  stale:r=>{r.asset_snapshot.version++;},
  'wrong coordinate system':r=>{r.camera_inspection.coordinate_system='OTHER' as never;},
  'unknown field':r=>{Object.assign(r.camera_inspection,{extra:true});},
  'not static':r=>{r.camera_inspection.animation_applied=true as false;},
  'invalid scene':r=>{r.camera_inspection.scene_index=64;},
  'sole scene mismatch':r=>{r.camera_inspection.scene_selection='SOLE_SCENE';r.camera_inspection.scene_index=1;},
  'camera count overflow':r=>{r.camera_inspection.camera_definition_count=65;},
  'camera index mismatch':r=>{r.camera_inspection.instances[0].camera_index=2;},
  'node outside inspection':r=>{r.camera_inspection.instances[0].node_index=3;},
  'duplicate node':r=>{r.camera_inspection.instances[1].node_index=0;},
  'control in name':r=>{r.camera_inspection.instances[0].node_name='bad\u007f';},
  'name too long':r=>{r.camera_inspection.instances[0].camera_name='a'.repeat(241);},
  'nonfinite position':r=>{r.camera_inspection.instances[0].world_matrix[12]=Infinity;},
  'out of bounds position':r=>{r.camera_inspection.instances[0].world_matrix[12]=1e9+1;},
  'non-affine matrix':r=>{r.camera_inspection.instances[0].world_matrix[3]=1e-12;},
  'scaled matrix':r=>{r.camera_inspection.instances[0].world_matrix[0]=2;},
  'reflected matrix':r=>{r.camera_inspection.instances[0].world_matrix[0]=-1;},
  'skewed matrix':r=>{r.camera_inspection.instances[0].world_matrix[4]=0.1;},
  'sparse matrix':r=>{delete r.camera_inspection.instances[0].world_matrix[0];},
  'invalid yfov':r=>{Object.assign(r.camera_inspection.instances[0].projection,{yfov:Math.PI});},
  'zero perspective near':r=>{r.camera_inspection.instances[0].projection.znear=0;},
  'bad aspect ratio':r=>{Object.assign(r.camera_inspection.instances[0].projection,{aspectRatio:0});},
  'far behind near':r=>{r.camera_inspection.instances[0].projection.zfar=0.01;},
  'missing omission marker':r=>{delete (r.camera_inspection.instances[0].projection as Partial<{zfar:number}>).zfar;},
  'negative orthographic near':r=>{r.camera_inspection.instances[1].projection.znear=-1;},
  'zero orthographic extent':r=>{Object.assign(r.camera_inspection.instances[1].projection,{xmag:0});},
  'extra projection field':r=>{Object.assign(r.camera_inspection.instances[0].projection,{orthographic:{}});},
};
it.each(Object.keys(invalidInspections))('rejects invalid camera inspection: %s',name=>{
  const review=cameraReview();invalidInspections[name](review);expect(()=>checkedModelCameras(review,cameraAsset)).toThrow();
});
const invalidExports:Record<string,(result:ModelCameraExport)=>void>={
  source:r=>{r.asset_snapshot.digest='f'.repeat(64);},
  scene:r=>{r.camera_export.scene_index=1;},
  selection:r=>{r.camera_export.camera.node_index=2;},
  pose:r=>{r.camera_export.camera.world_matrix[12]++;},
  projection:r=>{r.camera_export.camera.projection.znear=0.2;},
  profile:r=>{r.camera_export.profile='BLENDER' as never;},
  'target acceptance claim':r=>{r.camera_export.blender_import_acceptance='PASSED' as never;},
  'created asset':r=>{r.camera_export.asset_created=true as false;},
  bytes:r=>{r.content_base64='AAAA';},
  hash:r=>{r.camera_export.sha256='0'.repeat(64);},
  count:r=>{r.camera_export.byte_count++;},
  'noncanonical base64':r=>{r.content_base64+='\n';},
  'extra receipt field':r=>{Object.assign(r.camera_export,{extra:true});},
  'artifact pose despite correct hash':r=>{rewriteCameraDocument(r,d=>{d.nodes[0].matrix[12]++;});},
  'artifact projection despite correct hash':r=>{rewriteCameraDocument(r,d=>{Object.assign(d.cameras[0].perspective,{aspectRatio:1});});},
  'artifact source despite correct hash':r=>{rewriteCameraDocument(r,d=>{d.extras.studio_camera_source.version++;});},
  'artifact foreign resource despite correct hash':r=>{rewriteCameraDocument(r,d=>{Object.assign(d,{buffers:[{uri:'https://example.invalid/resource.bin'}]});});},
  'artifact extra node despite correct hash':r=>{rewriteCameraDocument(r,d=>{d.nodes.push(d.nodes[0]);});},
  'artifact geometry despite correct hash':r=>{rewriteCameraDocument(r,d=>{Object.assign(d.nodes[0],{mesh:0});});},
};
it.each(Object.keys(invalidExports))('rejects invalid camera export: %s',async name=>{
  const result=cameraExport();invalidExports[name](result);await expect(checkedModelCameraExport(result,cameraAsset,cameraChoice())).rejects.toThrow();
});
it.each([
  ['root key',(text:string)=>text.replace('{','{"nodes":[{"mesh":0}],')],
  ['escaped root key',(text:string)=>text.replace('{','{"no\\u0064es":[{"mesh":0}],')],
  ['nested node key',(text:string)=>text.replace('"camera":0','"camera":9,"camera":0')],
  ['nested provenance key',(text:string)=>text.replace('"asset_id":','"asset_id":"foreign-source","asset_id":')],
] as const)('rejects duplicate %s in raw glTF even with recomputed size and hash',async(_name,forge)=>{
  const result=cameraExport(),bytes=Buffer.from(forge(Buffer.from(result.content_base64,'base64').toString('utf8')));
  result.content_base64=bytes.toString('base64');result.camera_export.byte_count=bytes.length;result.camera_export.sha256=createHash('sha256').update(bytes).digest('hex');
  await expect(checkedModelCameraExport(result,cameraAsset,cameraChoice())).rejects.toThrow();
});
it('does not mistake delimiters inside escaped camera names for artifact structure',async()=>{
  const choice=cameraChoice();choice.camera.node_name='Camera "nested": { [ ] } \\';choice.camera.camera_name='カメラ {}';
  expect(await checkedModelCameraExport(cameraExport(choice),cameraAsset,choice)).toEqual(cameraExport(choice));
});
it('uses original source endpoints with captured source and exact explicit selection',async()=>{
  const fetch=vi.fn(async(url:string)=>new Response(JSON.stringify(url.endsWith('/cameras')?cameraReview():cameraExport()),{status:200}));vi.stubGlobal('fetch',fetch);
  const client=studioClient(cameraAsset.novel_id,{sessionToken:'fixture-session'});
  expect(await client.inspectModelCameras(cameraAsset)).toEqual(cameraReview());
  expect(await client.exportModelCamera(cameraAsset,cameraChoice())).toEqual(cameraExport());
  const calls=fetch.mock.calls as unknown as [string,RequestInit][];
  expect(calls.map(([url])=>url)).toEqual([`/api/projects/${cameraAsset.novel_id}/studio/assets/${cameraAsset.id}/model-reference/cameras`,`/api/projects/${cameraAsset.novel_id}/studio/assets/${cameraAsset.id}/model-reference/camera-export`]);
  expect(calls[0][1].method).toBe('GET');expect(calls[1][1].method).toBe('POST');
  expect(JSON.parse(String(calls[1][1].body))).toEqual({contract:'studio-static-glb-camera-export/1',source_version:cameraAsset.version,source_sha256:cameraAsset.sha256,scene_index:0,node_index:0,camera_index:0,profile:'GLTF_2_CAMERA_ONLY'});
  const invalid=cameraChoice();invalid.camera.projection.znear=NaN;
  await expect(client.exportModelCamera(cameraAsset,invalid)).rejects.toThrow();expect(fetch).toHaveBeenCalledTimes(2);
  const abort=new AbortController();abort.abort();await expect(client.inspectModelCameras(cameraAsset,abort.signal)).rejects.toThrow();await expect(client.exportModelCamera(cameraAsset,cameraChoice(),abort.signal)).rejects.toThrow();expect(fetch).toHaveBeenCalledTimes(2);
  expect(()=>checkedModelCameraSelection({...cameraChoice(),node_index:0})).toThrow();
});
