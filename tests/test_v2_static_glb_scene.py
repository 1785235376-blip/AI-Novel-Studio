"""Actual GLB numeric transforms, not materials, animation or DCC acceptance."""
from copy import deepcopy
import math
import pytest
from app.creative.model_reference_glb import inspect_static_glb
from test_v2_static_glb_inspection import glb,triangle_document


def read(doc): return inspect_static_glb(glb(doc),include_geometry=True,include_scene=True)


def test_keeps_mesh_metadata_and_applies_declared_translation_only_in_scene():
    result=read(triangle_document())
    assert result['inspection']['bounds']['min']==[-1,0,0]
    scene=result['scene_preview']
    assert scene['bounds']=={'min':[99,0,0],'max':[101,2,0]}
    assert scene['scene_transforms_applied'] is True and scene['materials_rendered'] is False
    assert scene['selection']=='DECLARED_DEFAULT' and scene['mesh_instances']==1
    assert scene['primitives'][0]['triangles']==[[0,1,2]]


def test_parent_times_local_trs_and_column_major_matrix_agree():
    doc=triangle_document();doc['nodes']=[{'translation':[10,0,0],'scale':[2,2,2],'children':[1]},
        {'mesh':0,'translation':[0,3,0],'rotation':[0,0,math.sqrt(.5),math.sqrt(.5)]}]
    scene=read(doc)['scene_preview']
    for got,want in zip(scene['primitives'][0]['positions'],[[10,4,0],[10,8,0],[6,6,0]]):assert got==pytest.approx(want,abs=1e-8)
    doc['nodes'][1]={'mesh':0,'matrix':[0,1,0,0,-1,0,0,0,0,0,1,0,0,3,0,1]}
    other=read(doc)['scene_preview']
    for got,want in zip(other['primitives'][0]['positions'],scene['primitives'][0]['positions']):assert got==pytest.approx(want,abs=1e-8)


def test_instances_have_separate_world_geometry_and_selected_scene_is_explicit():
    doc=triangle_document();doc['nodes']=[{'mesh':0},{'mesh':0,'translation':[100,0,0]}];doc['scenes']=[{'nodes':[0,1]}];del doc['scene']
    scene=read(doc)['scene_preview'];assert scene['selection']=='SOLE_SCENE'
    assert scene['position_count']==6 and scene['triangle_count']==2 and scene['mesh_instances']==2
    assert [p['node_index'] for p in scene['primitives']]==[0,1]
    assert scene['bounds']=={'min':[-1,0,0],'max':[101,2,0]}
    doc['scenes'].append({'nodes':[1]})
    with pytest.raises(ValueError,match='SCENE_SELECTION_REQUIRED'):read(doc)
    doc['scene']=1;assert read(doc)['scene_preview']['mesh_instances']==1


@pytest.mark.parametrize('fault',['cycle','two_parents','duplicate_child','child_root','matrix_trs','nonunit_rotation','nonaffine','huge','extension','overflow','empty','instance_limit'])
def test_rejects_invalid_or_unbounded_scene_without_breaking_mesh_only_read(fault):
    doc=triangle_document()
    if fault=='cycle':doc['nodes'][0]['children']=[0]
    if fault=='two_parents':doc['nodes']=[{'children':[2]},{'children':[2]},{'mesh':0}]
    if fault=='duplicate_child':doc['nodes']=[{'children':[1,1]},{'mesh':0}]
    if fault=='child_root':doc['nodes']=[{'children':[1]},{'mesh':0}];doc['scenes'][0]['nodes']=[1]
    if fault=='matrix_trs':doc['nodes'][0]['matrix']=[1,0,0,0,0,1,0,0,0,0,1,0,0,0,0,1]
    if fault=='nonunit_rotation':doc['nodes'][0]['rotation']=[0,0,0,0]
    if fault=='nonaffine':doc['nodes']=[{'mesh':0,'matrix':[1,0,0,1,0,1,0,0,0,0,1,0,0,0,0,1]}]
    if fault=='huge':doc['nodes'][0]['translation']=[10**500,0,0]
    if fault=='extension':doc['nodes'][0]['extensions']={'unsupported':{}}
    if fault=='overflow':doc['nodes']=[{'scale':[1e9,1,1],'children':[1]},{'mesh':0,'scale':[1e9,1,1]}]
    if fault=='empty':doc['nodes']=[{}]
    if fault=='instance_limit':doc['nodes']=[{'mesh':0} for _ in range(129)];doc['scenes'][0]['nodes']=list(range(129))
    with pytest.raises(ValueError,match='MODEL_REFERENCE_GLB_'):read(doc)
    assert inspect_static_glb(glb(doc),include_geometry=True)['mesh_preview']['scene_transforms_applied'] is False
