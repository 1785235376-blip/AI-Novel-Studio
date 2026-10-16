from uuid import uuid4
import pytest
from pydantic import ValidationError
from app.experimental.provider_profiles import ProviderProfile, ProviderProfileSelection, VaultReference


def profile(**changes):
    payload = dict(profile_id=uuid4(), display_name='Writing profile', provider_id='local-provider',
                   vault_reference=VaultReference(backend='keyring', entry_id=uuid4()), capabilities=['TEXT'])
    return ProviderProfile(**(payload | changes))


def test_profile_contract_excludes_credentials_and_internal_references():
    p = profile()
    public = p.public()
    assert public['secret'] is None and 'vault_reference' not in public
    assert str(p.vault_reference.entry_id) not in str(public)
    assert public['configuration_status'] == 'HOST_INTEGRATION_REQUIRED'
    with pytest.raises(ValidationError): profile(secret='not-accepted')
    with pytest.raises(ValidationError): VaultReference(backend='memory', entry_id=uuid4())
    with pytest.raises(ValidationError): VaultReference(backend='keyring', entry_id='plaintext-key')


def test_project_profile_selection_disable_revoke_and_capability_contract():
    first, other = profile(), profile()
    selected = ProviderProfileSelection(default_profile_id=first.profile_id, project_profile_ids={'novel':other.profile_id})
    assert selected.select('novel', [first,other], 'TEXT') == other
    assert selected.select('other', [first,other], 'TEXT') == first
    with pytest.raises(ValueError): selected.select('novel', [first,other], 'IMAGE')
    with pytest.raises(ValueError): selected.select('novel', [first,other.model_copy(update={'enabled':False})], 'TEXT')
    with pytest.raises(ValidationError): profile(revoked=True, enabled=True)
    with pytest.raises(ValueError): ProviderProfileSelection().select('novel', [first], 'TEXT')
