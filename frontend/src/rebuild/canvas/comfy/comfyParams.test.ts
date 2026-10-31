// [HERMIA-FE-20261031 DUALCANVAS-COMFY PARAMS] Widget metadata + bounded param restoration.
import {describe, expect, it} from 'vitest';
import {defaultWidgetParams, parseObjectInfo, sanitizeWidgetParams} from './comfyRegistry';

const info = {
  ParamsNode: {
    input: {
      required: {
        model: ['MODEL'],
        seed: ['INT', {default: 42, min: 0, max: 100, step: 1}],
        cfg: ['FLOAT', {default: 7.5, min: 0, max: 30}],
        sampler_name: [['euler', 'dpmpp_2m']],
        text: ['STRING', {default: 'hello', multiline: true}],
        enabled: ['BOOLEAN', {default: true}],
      },
      optional: {strength: ['FLOAT', {default: 0.5}]},
    },
    output: ['LATENT'],
  },
};

const def = () => parseObjectInfo(info, 'imported').defs[0];

describe('comfyWidgetParams', () => {
  it('parses widgets separately from typed ports with choices/defaults/ranges', () => {
    const d = def();
    expect(d.inputs).toEqual([{name: 'model', type: 'MODEL', optional: undefined}]);
    const widgets = Object.fromEntries(d.widgets.map(w => [w.name, w]));
    expect(widgets.seed).toMatchObject({kind: 'INT', default: 42, min: 0, max: 100, step: 1});
    expect(widgets.cfg).toMatchObject({kind: 'FLOAT', default: 7.5, min: 0, max: 30});
    expect(widgets.sampler_name).toMatchObject({kind: 'COMBO', choices: ['euler', 'dpmpp_2m']});
    expect(widgets.text).toMatchObject({kind: 'STRING', default: 'hello', multiline: true});
    expect(widgets.enabled).toMatchObject({kind: 'BOOLEAN', default: true});
    expect(widgets.strength).toMatchObject({kind: 'FLOAT', default: 0.5, optional: true});
  });

  it('creates initial values for every widget only', () => {
    expect(defaultWidgetParams(def())).toEqual({
      seed: 42, cfg: 7.5, sampler_name: 'euler', text: 'hello', enabled: true, strength: 0.5,
    });
    expect(defaultWidgetParams(undefined)).toBeUndefined();
  });

  it('keeps only known widgets with their primitive type and drops invalid/unknown values', () => {
    expect(sanitizeWidgetParams(def(), {
      seed: 7, cfg: 2.5, sampler_name: 'dpmpp_2m', text: 'ok', enabled: false, strength: 0.25,
      model: 'should-not-be-a-param', unknown: 'drop', seedBad: true,
    })).toEqual({seed: 7, cfg: 2.5, sampler_name: 'dpmpp_2m', text: 'ok', enabled: false, strength: 0.25});
    expect(sanitizeWidgetParams(def(), {seed: '7', cfg: Number.NaN, enabled: 'true', sampler_name: 3})).toBeUndefined();
    expect(sanitizeWidgetParams(def(), {text: 'x'.repeat(5000)})).toEqual({text: 'x'.repeat(4096)});
    expect(sanitizeWidgetParams(def(), null)).toBeUndefined();
  });

  it('keeps a bounded primitive map for unknown nodes so older/removed definitions do not crash', () => {
    expect(sanitizeWidgetParams(undefined, {seed: 1, enabled: true, text: 'x', nested: {bad: true}, long: 'x'.repeat(600)}))
      .toEqual({seed: 1, enabled: true, text: 'x'});
  });
});
