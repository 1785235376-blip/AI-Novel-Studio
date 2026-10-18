"""Author declarations remain versioned untrusted metadata, never permissions."""
import copy
import pytest
from pydantic import ValidationError
from app.experimental.research_library import ResearchLibraryService,MetadataIn
from app.experimental.common import StaleSourceError
from test_v2_creative_project_lifecycle import rig
from test_r4_research_library import payload,citation


def test_declarations_survive_reopen_old_client_edit_replace_and_history(rig):
    e=rig;service=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    claims={'license_statement':'Synthetic author declaration. Attribution required.','verification_note':'Compared with the original, manually; not machine verified.'}
    row=service.import_file(e.nid,e.scope,e.actor,{**payload(),**claims},guard=lambda:None)
    fresh=ResearchLibraryService(e.store,e.novels,e.chapters,historical_inspection=True)
    assert all(fresh.source(e.nid,e.scope,e.actor,row['id'])[k]==v for k,v in claims.items())
    evidence=fresh.resolve(e.nid,e.scope,e.actor,citation(row))
    assert all(evidence[k]==v for k,v in claims.items())
    assert fresh.context(e.nid,e.scope,e.actor,[citation(row)])['untrusted_data'] is True
    old_body={k:v for k,v in payload().items() if k not in {'filename','content_base64'}}
    edited=fresh.edit_source(e.nid,e.scope,e.actor,row['id'],{**old_body,'expected_version':1},guard=lambda:None)
    assert all(edited[k]==v for k,v in claims.items())
    replaced=fresh.replace_file(e.nid,e.scope,e.actor,row['id'],{**payload('Replacement'),'expected_version':2},guard=lambda:None)
    assert all(replaced[k]==v for k,v in claims.items())
    cleared=fresh.edit_source(e.nid,e.scope,e.actor,row['id'],{**old_body,'license_statement':'','verification_note':'','expected_version':3},guard=lambda:None)
    assert cleared['license_statement']==cleared['verification_note']==''
    with pytest.raises(StaleSourceError):fresh.resolve(e.nid,e.scope,e.actor,citation(row))
    history=fresh.source_history(e.nid,e.scope,e.actor,row['id'])['items']
    assert history[0]['license_statement']==claims['license_statement']
    restored=fresh.restore_source(e.nid,e.scope,e.actor,row['id'],{'expected_version':4,'restore_version':1},guard=lambda:None)
    assert restored['license_statement']==claims['license_statement'] and restored['access']=='PRIVATE'
    saved=e.store.read(e.nid,e.scope)
    assert saved['collections']['research_sources'][row['id']]['version']==5


@pytest.mark.parametrize('field',['license_statement','verification_note'])
def test_declarations_bounded_and_do_not_accept_authority_fields(field):
    with pytest.raises(ValidationError):MetadataIn.model_validate({'title':'Reference',field:'x'*4001})
    with pytest.raises(ValidationError):MetadataIn.model_validate({'title':'Reference','commercial_use_verified':True})
