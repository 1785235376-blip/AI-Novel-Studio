import copy
import pytest
from app.creative.model_reference_glb import inspect_static_glb
from test_v2_static_glb_inspection import glb, triangle_document


def document():
    value=triangle_document();value['materials']=[{'name':'Paint','pbrMetallicRoughness':{'baseColorFactor':[.1,.2,.3,.4],'metallicFactor':.2,'roughnessFactor':.8},'alphaMode':'MASK','doubleSided':True}];value['meshes'][0]['primitives'][0]['material']=0;return value


def test_actual_glb_factors_defaults_and_primitive_binding():
    result=inspect_static_glb(glb(document()),include_materials=True)['material_inspection'];row=result['materials'][0]
    assert row['base_color_factor']==[.1,.2,.3,.4] and row['alpha_cutoff']==.5 and row['emissive_factor']==[0,0,0]
    assert row['metallic_factor']==.2 and row['roughness_factor']==.8
    assert result['primitive_bindings']==[{'mesh_index':0,'primitive_index':0,'material_index':0}]
    plain=inspect_static_glb(glb(),include_materials=True)['material_inspection'];assert plain['materials']==[] and plain['primitive_bindings'][0]['material_index'] is None
    defaults=document();defaults['materials']=[{}];row=inspect_static_glb(glb(defaults),include_materials=True)['material_inspection']['materials'][0];assert row['base_color_factor']==[1,1,1,1] and row['roughness_factor']==row['metallic_factor']==1


@pytest.mark.parametrize('change',[
 lambda v:v['materials'][0]['pbrMetallicRoughness'].update(baseColorFactor=[1,1,True,1]),
 lambda v:v['materials'][0]['pbrMetallicRoughness'].update(roughnessFactor=2),
 lambda v:v['materials'][0].update(doubleSided=1),
 lambda v:v['materials'][0].update(alphaCutoff=-1),
 lambda v:v['materials'][0].update(extensions={'unknown':{}}),
 lambda v:v['meshes'][0]['primitives'][0].update(material=None),
 lambda v:v['meshes'][0]['primitives'][0].update(material=1),
 lambda v:v.update(materials=[{}]*129),
 lambda v:v['materials'][0].update(normalTexture={'index':0}),
])
def test_malformed_material_metadata_is_not_a_partial_success(change):
    value=document();change(value)
    with pytest.raises(ValueError,match='MODEL_REFERENCE_GLB_MATERIAL_INVALID'):inspect_static_glb(glb(value),include_materials=True)


def test_declared_texture_is_not_loaded_or_claimed_validated():
    value=document();value['textures']=[{'source':0}];value['materials'][0]['normalTexture']={'index':0}
    result=inspect_static_glb(glb(value),include_materials=True)['material_inspection'];assert result['materials'][0]['declared_texture_slots']==['normalTexture'];assert result['texture_resources_validated'] is result['textures_decoded'] is result['materials_rendered'] is False
    with pytest.raises(ValueError):inspect_static_glb(glb(value),include_materials=True,include_geometry=True)
