from app.credential_vault import CredentialVault
import sys
import uuid
import pytest

def test_vault_round_trip_and_redacted_status():
    vault = CredentialVault(backend="memory")
    vault.set("deepseek", "TEST_ONLY_SECRET")
    assert vault.resolve("deepseek") == "TEST_ONLY_SECRET"
    assert vault.status("deepseek") == {"provider": "deepseek", "configured": True, "backend": "memory", "secret": None}
    vault.clear("deepseek")
    assert vault.resolve("deepseek") is None

def test_vault_rejects_invalid_or_unknown_credentials():
    vault = CredentialVault(backend="memory")
    for value in ("", "bad\nsecret"):
        try: vault.set("deepseek", value)
        except ValueError: pass
        else: raise AssertionError("invalid credential accepted")
    try: vault.set("unknown", "x")
    except ValueError: pass
    else: raise AssertionError("unknown provider accepted")

@pytest.mark.skipif(sys.platform != "win32", reason="Windows Credential Manager only")
def test_windows_credential_manager_round_trip():
    vault = CredentialVault(backend="windows")
    secret = "TEST_ONLY_" + uuid.uuid4().hex
    vault.clear("deepseek")
    try:
        vault.set("deepseek", secret)
        assert vault.resolve("deepseek") == secret
        assert vault.status("deepseek")["secret"] is None
    finally:
        vault.clear("deepseek")
    assert vault.resolve("deepseek") is None
