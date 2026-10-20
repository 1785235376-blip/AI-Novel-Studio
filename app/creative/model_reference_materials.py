"""Bounded glTF material-factor metadata; never decodes textures or renders PBR."""
import math


def inspect_materials(document):
    def fail(): raise ValueError('MODEL_REFERENCE_GLB_MATERIAL_INVALID')
    def obj(value):
        if not isinstance(value, dict) or value.get('extensions'): fail()
        return value
    def number(value, maximum=1):
        if type(value) not in (int, float) or not 0 <= value <= maximum or not math.isfinite(value): fail()
        return float(value)
    def vector(value, length):
        if not isinstance(value, list) or len(value) != length: fail()
        return [number(v) for v in value]
    rows = document.get('materials', [])
    textures = document.get('textures', [])
    if not isinstance(rows, list) or len(rows) > 128 or not isinstance(textures, list) or len(textures) > 128: fail()
    result=[]
    for index, raw in enumerate(rows):
        material=obj(raw); pbr=obj(material.get('pbrMetallicRoughness', {}))
        name=material.get('name', '')
        if not isinstance(name,str) or len(name)>200 or any(ord(c)<32 for c in name): fail()
        mode=material.get('alphaMode','OPAQUE'); sided=material.get('doubleSided',False)
        if mode not in ('OPAQUE','MASK','BLEND') or type(sided) is not bool: fail()
        slots=[]
        for owner, key in ((pbr,'baseColorTexture'),(pbr,'metallicRoughnessTexture'),(material,'normalTexture'),(material,'occlusionTexture'),(material,'emissiveTexture')):
            if key not in owner: continue
            info=obj(owner[key]); tex=info.get('index'); coord=info.get('texCoord',0)
            if type(tex) is not int or not 0 <= tex < len(textures) or type(coord) is not int or not 0 <= coord <= 7: fail()
            obj(textures[tex]); slots.append(key)
        result.append({'index':index,'name':name,'base_color_factor':vector(pbr.get('baseColorFactor',[1,1,1,1]),4),
            'metallic_factor':number(pbr.get('metallicFactor',1)),'roughness_factor':number(pbr.get('roughnessFactor',1)),
            'emissive_factor':vector(material.get('emissiveFactor',[0,0,0]),3),'alpha_mode':mode,
            'alpha_cutoff':number(material.get('alphaCutoff',.5),1_000_000),'double_sided':sided,'declared_texture_slots':slots})
    bindings=[]
    for mesh_index, mesh in enumerate(document['meshes']):
        for primitive_index, primitive in enumerate(mesh['primitives']):
            index=primitive.get('material')
            if 'material' in primitive and (type(index) is not int or not 0 <= index < len(rows)): fail()
            bindings.append({'mesh_index':mesh_index,'primitive_index':primitive_index,'material_index':index})
    return {'contract':'studio-static-glb-material-inspection/1','materials':result,'primitive_bindings':bindings,
        'default_factors_applied':True,'color_space':'LINEAR_FACTORS','textures_decoded':False,
        'texture_resources_validated':False,'materials_rendered':False,'external_resources_loaded':False,'model_called':False}
