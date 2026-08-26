import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError, URLError
from io import BytesIO

from app.providers import OpenAICompatibleProvider, ProviderError


class _Response:
    status = 200
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return json.dumps({"choices": [{"message": {"content": "ok"}}]}).encode()

class _StreamResponse(_Response):
    def __iter__(self):
        yield b'data: {"choices":[{"delta":{"content":"a"}}]}\n'
        yield b'data: {"choices":[{"delta":{"content":"b"}}]}\n'
        yield b'data: [DONE]\n'


class ProviderRetryTests(unittest.TestCase):
    def provider(self):
        return OpenAICompatibleProvider("test", "https://example.invalid", "TEST_PROVIDER_KEY")

    @patch.dict("os.environ", {"TEST_PROVIDER_KEY": "temporary"})
    @patch("app.providers.urlopen", side_effect=[HTTPError("u", 503, "busy", {}, BytesIO()), _Response()])
    def test_retries_server_error(self, urlopen):
        result = self.provider().generate("hello", "model", retries=1, backoff=0)
        self.assertEqual(result.text, "ok")
        self.assertEqual(urlopen.call_count, 2)

    @patch.dict("os.environ", {"TEST_PROVIDER_KEY": "temporary"})
    @patch("app.providers.urlopen", side_effect=URLError("offline"))
    def test_exhausted_network_error_is_safe(self, urlopen):
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            self.provider().generate("hello", "model", retries=1, backoff=0)
        self.assertEqual(urlopen.call_count, 2)

    @patch.dict("os.environ", {"TEST_PROVIDER_KEY": "temporary"})
    @patch("app.providers.urlopen", return_value=_StreamResponse())
    def test_stream_parses_sse_deltas(self, urlopen):
        self.assertEqual("".join(self.provider().stream("hello", "model", retries=0)), "ab")


if __name__ == "__main__":
    unittest.main()
