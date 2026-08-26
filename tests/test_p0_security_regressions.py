import unittest
from unittest.mock import patch
from types import SimpleNamespace

from app.net_safety import OutboundURLRejected, validate_outbound_url
from fastapi.testclient import TestClient
from app.main import app


class P0SecurityRegressionTests(unittest.TestCase):
    def test_outbound_url_rejects_local_and_non_http(self):
        for url in ("file:///tmp/a", "http://127.0.0.1/a", "http://169.254.169.254/latest", "http://10.0.0.1/a", "http://localhost/a"):
            with self.subTest(url=url):
                with self.assertRaises(OutboundURLRejected):
                    validate_outbound_url(url)

    def test_outbound_url_accepts_public_https_shape(self):
        with patch('app.net_safety.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('93.184.216.34', 443))]):
            self.assertEqual(validate_outbound_url("https://example.com/image.png"), "https://example.com/image.png")

    def test_outbound_url_rejects_hostname_resolving_to_private_address(self):
        with patch('app.net_safety.socket.getaddrinfo', return_value=[(2, 1, 6, '', ('169.254.169.254', 80))]):
            with self.assertRaises(OutboundURLRejected):
                validate_outbound_url("http://metadata.example.test/latest")

    def test_explicit_loopback_allowlist_is_host_specific(self):
        config=SimpleNamespace(outbound_loopback_allowlist='comfyui.local')
        with patch('app.config.settings',config), patch('app.net_safety.socket.getaddrinfo', return_value=[(2,1,6,'',('127.0.0.1',8188))]):
            self.assertEqual(validate_outbound_url('http://comfyui.local:8188/output.png'),'http://comfyui.local:8188/output.png')

    def test_vision_rejects_private_image_url_before_provider_call(self):
        with patch('app.credential_vault.credential_vault.resolve',return_value='secret'):
            response=TestClient(app).post('/api/vision/analyze',json={'provider_id':'openai','model_id':'vision','prompt':'inspect','image_url':'http://169.254.169.254/latest'})
        self.assertEqual(response.status_code,400)
        self.assertEqual(response.json()['detail']['code'],'OUTBOUND_URL_REJECTED')

    def test_default_runtime_rejects_non_loopback_clients(self):
        client=TestClient(app,client=('192.168.1.44',50000))
        response=client.get('/novels')
        self.assertEqual(response.status_code,403)
        self.assertEqual(response.json()['detail']['code'],'LOCAL_RUNTIME_LOOPBACK_REQUIRED')

    def test_packaged_provider_does_not_use_environment_key(self):
        from app.providers import OpenAICompatibleProvider
        with patch.dict('os.environ', {'PACKAGED_WINDOWS_MODE':'true','DEEPSEEK_API_KEY':'env-only'}, clear=False):
            with patch('app.credential_vault.credential_vault.resolve', return_value=''):
                self.assertEqual(OpenAICompatibleProvider('deepseek','https://example.invalid','DEEPSEEK_API_KEY')._key(), '')

if __name__ == "__main__":
    unittest.main()
