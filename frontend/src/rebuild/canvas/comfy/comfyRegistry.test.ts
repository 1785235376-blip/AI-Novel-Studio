// [HERMIA-FE-20261031 DUALCANVAS-COMFY] registry / object_info parser / typed connect.
import {describe, it, expect} from 'vitest';
import {BUILTIN_OBJECT_INFO, NODE_GROUPS, connect, defaultRegistry, groupOf, makeRegistry, mergeImported, parseObjectInfo, portColor, sanitizeGraph, searchDefs, typesCompatible, type CfGraph} from './comfyRegistry';

const reg = defaultRegistry('image');
const g = (...ts: string[]): CfGraph => ({nodes: ts.map((t, i) => ({id: `n${i}`, t, x: 0, y: 0, title: t})), edges: []});

describe('parseObjectInfo', () => {
  it('splits ports from widgets exactly like ComfyUI (INT/FLOAT/STRING/BOOLEAN/combo are widgets)', () => {
    const {defs, errors} = parseObjectInfo({KSampler: BUILTIN_OBJECT_INFO.KSampler});
    expect(errors).toEqual([]);
    const k = defs[0];
    expect(k.inputs.map(p => `${p.name}:${p.type}`)).toEqual(['model:MODEL', 'positive:CONDITIONING', 'negative:CONDITIONING', 'latent_image:LATENT']);
    expect(k.widgets.map(w => w.name)).toEqual(['seed', 'steps', 'cfg', 'sampler_name', 'scheduler', 'denoise']);
    expect(k.outputs).toEqual([{name: 'LATENT', type: 'LATENT'}]);
    expect(k.group).toBe('sampling');
  });
  it('reads a real-shaped object_info entry incl. optional inputs, output_name, output_node and custom types', () => {
    const {defs} = parseObjectInfo({
      MyNode: {input: {required: {img: ['IMAGE'], n: ['INT', {default: 1}], mode: [['a', 'b']]}, optional: {mask: ['MASK'], ip: ['IPADAPTER']}},
        output: ['IMAGE', 'MASK'], output_name: ['out', 'mask'], display_name: 'My Node', category: 'custom/foo', output_node: true},
    });
    expect(defs[0]).toMatchObject({name: 'MyNode', display_name: 'My Node', group: 'other', output_node: true, source: 'imported'});
    expect(defs[0].inputs).toEqual([{name: 'img', type: 'IMAGE'}, {name: 'mask', type: 'MASK', optional: true}, {name: 'ip', type: 'IPADAPTER', optional: true}]);
    expect(defs[0].outputs.map(o => o.name)).toEqual(['out', 'mask']);
  });
  it('rejects malformed entries without throwing', () => {
    expect(parseObjectInfo(null).errors[0].reason).toBe('not_an_object');
    const r = parseObjectInfo({A: 3, B: {output: [1]}, C: {input: {required: {x: [42]}}}, D: {output: ['IMAGE']}});
    expect(r.errors.map(e => e.name)).toEqual(['A', 'B', 'C']); expect(r.defs.map(d => d.name)).toEqual(['D']);
  });
  it('groups ComfyUI category paths', () => {
    expect(groupOf('conditioning/controlnet')).toBe('controlnet'); expect(groupOf('image/upscaling')).toBe('upscale');
    expect(groupOf('image/video')).toBe('video'); expect(groupOf('advanced/loaders')).toBe('loaders'); expect(groupOf('latent/inpaint')).toBe('latent');
    expect(groupOf('whatever')).toBe('other');
  });
});

describe('registry', () => {
  it('covers every requested category with real ComfyUI node names and no generation call of its own', () => {
    for (const k of ['image', 'video'] as const) {
      const groups = new Set(defaultRegistry(k).defs.map(d => d.group));
      for (const want of NODE_GROUPS.filter(x => x !== 'other')) expect(groups.has(want)).toBe(true);
    }
    expect(reg.defs.length).toBeGreaterThanOrEqual(40);
    for (const n of ['CheckpointLoaderSimple', 'CLIPTextEncode', 'KSampler', 'EmptyLatentImage', 'VAEDecode', 'LoadImage', 'ControlNetApplyAdvanced', 'ImageUpscaleWithModel']) expect(reg.byName.has(n)).toBe(true);
  });
  it('PoemSeed enrichment nodes (reference / director / variants) are present and feedable; ComfyUI nodes are not', () => {
    expect(defaultRegistry('video').byName.get('director_note')?.feedAs).toBe('director_note');
    expect(reg.byName.get('image_reference')?.feedAs).toBe('image_reference');
    expect(reg.byName.get('KSampler')?.feedAs).toBeUndefined();
  });
  it('imported object_info replaces builtins by name but never PoemSeed nodes', () => {
    const imp = parseObjectInfo({KSampler: {input: {required: {model: ['MODEL']}}, output: ['LATENT'], category: 'sampling'}, image_reference: {output: ['MASK']}}).defs;
    const m = mergeImported(reg, imp);
    expect(m.byName.get('KSampler')!.inputs).toHaveLength(1);
    expect(m.byName.get('image_reference')!.source).toBe('poemseed');
  });
  it('search matches zh, English, class name and port type', () => {
    expect(searchDefs(reg, '采样', 'zh-CN').map(d => d.name)).toContain('KSampler');
    expect(searchDefs(reg, 'vae dec', 'en').map(d => d.name)).toEqual(['VAEDecode']);
    expect(searchDefs(reg, 'CONTROL_NET', 'en').length).toBeGreaterThanOrEqual(2);
  });
  it('port colours: known types fixed, unknown stable', () => {
    expect(portColor('IMAGE')).toBe('#64B5F6'); expect(portColor('FOO')).toBe(portColor('FOO')); expect(portColor('LATENT')).not.toBe(portColor('IMAGE'));
  });
});

describe('typed connect', () => {
  it('compatibility: equal, wildcard, union', () => {
    expect(typesCompatible('IMAGE', 'IMAGE')).toBe(true); expect(typesCompatible('LATENT', 'IMAGE')).toBe(false);
    expect(typesCompatible('*', 'MODEL')).toBe(true); expect(typesCompatible('IMAGE', 'IMAGE,MASK')).toBe(true);
  });
  it('LATENT → VAEDecode.samples ok; IMAGE → VAEDecode.samples refused; MODEL → KSampler.positive refused', () => {
    const base = g('EmptyLatentImage', 'VAEDecode', 'LoadImage', 'CheckpointLoaderSimple', 'KSampler');
    const ok = connect(base, reg, 'n0', 0, 'n1', 0);
    expect(ok.ok).toBe(true);
    expect(connect(base, reg, 'n2', 0, 'n1', 0)).toEqual({ok: false, reason: 'type', from: 'IMAGE', to: 'LATENT'});
    expect(connect(base, reg, 'n3', 0, 'n4', 1)).toMatchObject({ok: false, reason: 'type'});
    expect(connect(base, reg, 'n3', 0, 'n4', 0).ok).toBe(true);
    expect(connect(base, reg, 'n0', 5, 'n1', 0)).toMatchObject({ok: false, reason: 'slot'});
    expect(connect(base, reg, 'n1', 0, 'n1', 0)).toMatchObject({ok: false, reason: 'self'});
  });
  it('one link per input (replaces) and no cycles; input graph is not mutated', () => {
    const base = g('EmptyLatentImage', 'LatentUpscale', 'LatentUpscale');
    const r1 = connect(base, reg, 'n0', 0, 'n1', 0); if (!r1.ok) throw new Error();
    expect(base.edges).toHaveLength(0);
    const r2 = connect(r1.graph, reg, 'n2', 0, 'n1', 0); if (!r2.ok) throw new Error();
    expect(r2.graph.edges).toHaveLength(1); expect(r2.replaced).toBe(r1.graph.edges[0].id);
    const r3 = connect(r2.graph, reg, 'n1', 0, 'n2', 0);
    expect(r3).toMatchObject({ok: false, reason: 'cycle'});
  });
  it('sanitizeGraph keeps v1 nodes and drops edges that do not type-check', () => {
    const s = sanitizeGraph({nodes: [{id: 'a', t: 'image_reference', x: 1, y: 2, title: 'R'}, {id: 'b', t: 'VAEDecode', x: 0, y: 0, title: 'D'}, {bad: 1}],
      edges: [{id: 'old', a: 'a', b: 'b'}]}, reg);
    expect(s.nodes.map(n => n.id)).toEqual(['a', 'b']); expect(s.edges).toEqual([]);
    expect(makeRegistry([]).defs).toEqual([]);
  });
});
