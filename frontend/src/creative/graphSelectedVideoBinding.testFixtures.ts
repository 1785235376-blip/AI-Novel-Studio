import catalog from './fixtures/phase4.video-catalog.json';
import type { StudioGraphCatalog, StudioGraphDefinition, StudioGraphNode } from './studioGraphTypes';
import type { ProductionProvider } from './studioProductionClient';
export const videoBindingCatalog = () => structuredClone(catalog) as unknown as StudioGraphCatalog;
export const videoBindingProvider = (id = 'local-one'): ProductionProvider => ({ operation_id: 'm7.video.t2v', provider_id: id,
  model_id: `model-${id}`, local: true, route_digest: 'a'.repeat(64), capability: 'MEDIA',
  supported_parameters: ['width', 'height', 'seed', 'negative_prompt', 'duration_seconds', 'frame_rate'], readiness: 'CONFIGURED_NOT_VERIFIED' });
export const videoBindingNode = (id: string, index = 0): StudioGraphNode => ({ id, definition_id: 'video_generate', definition_version: 1,
  enabled: index !== 1, position: { x: index * 160, y: index * -100 }, parameters: { operation_id: 'm7.video.t2v',
    provider_id: `old-${id}`, model_id: `model-${id}`, allow_cloud: true, bind_shot: true,
    prompt: `镜头 ${id} 的独立提示词`, license_note: `授权 ${id}`, parameters: { seed: index + 1, duration_seconds: index + 2, frame_rate: 24, negative_prompt: `独立排除 ${id}` } } });
export function videoBindingGraph(count = 4): StudioGraphDefinition {
  return { schema_version: 5, title: '已有视频草稿', nodes: Array.from({ length: count }, (_, i) => videoBindingNode(`video-${i + 1}`, i)),
    edges: [], viewport: { x: 30, y: -20, zoom: 0.8 }, presentation: { comment: '原作者备注',
      notes: [{ id: 'note', text: '保留中文注释', position: { x: 12, y: 24 } }] } };
}
