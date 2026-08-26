import unittest
from unittest.mock import patch

from app.net_safety import OutboundURLRejected, validate_outbound_url


class P0SecurityRegressionTests(unittest.TestCase):
    def test_outbound_url_rejects_local_and_non_http(self):
        for url in ("file:///tmp/a", "http://127.0.0.1/a", "http://169.254.169.254/latest", "http://10.0.0.1/a", "http://localhost/a"):
            with self.subTest(url=url):
                with self.assertRaises(OutboundURLRejected):
                    validate_outbound_url(url)

    def test_outbound_url_accepts_public_https_shape(self):
        self.assertEqual(validate_outbound_url("https://example.com/image.png"), "https://example.com/image.png")

    def test_packaged_provider_does_not_use_environment_key(self):
        from app.providers import OpenAICompatibleProvider
        with patch.dict('os.environ', {'PACKAGED_WINDOWS_MODE':'true','DEEPSEEK_API_KEY':'env-only'}, clear=False):
            with patch('app.credential_vault.credential_vault.resolve', return_value=''):
                self.assertEqual(OpenAICompatibleProvider('deepseek','https://example.invalid','DEEPSEEK_API_KEY')._key(), '')

if __name__ == "__main__":
    unittest.main()
