from app.audio_providers import AudioGenerationRequest, HttpAudioProvider, provider_catalog, resolve_provider
from app.authorization import ModalityDomain


class Response:
    status_code = 200
    def __init__(self, data=None): self.data = data or {}
    def json(self): return self.data
    def raise_for_status(self): return None


class Transport:
    def __init__(self): self.posts = []
    def get(self, *args, **kwargs): return Response()
    def post(self, url, **kwargs): self.posts.append((url, kwargs)); return Response({'audio_url':'audio://result'})


class Vault:
    def resolve(self, provider_id): return None


def test_audio_is_a_first_class_domain_and_catalog_is_local_first():
    assert ModalityDomain.AUDIO.value == 'AUDIO'
    rows = provider_catalog()
    assert [row['provider_id'] for row in rows[:3]] == ['dasheng-local','stable-audio-local','mmaudio-local']
    assert {'TTS','TEXT_TO_AUDIO'} <= set(rows[0]['capabilities'])


def test_auto_route_prefers_dasheng_for_tts():
    provider_id, model_id, provider = resolve_provider('auto','TTS',Vault(),Transport())
    assert provider_id == 'dasheng-local'
    assert model_id == 'dasheng-audiogen'
    assert isinstance(provider,HttpAudioProvider)


def test_generic_audio_contract_supports_video_to_audio():
    transport=Transport();provider=HttpAudioProvider(transport,'http://localhost:8003/v1')
    result=provider.generate(AudioGenerationRequest('mmaudio-local','mmaudio','VIDEO_TO_AUDIO','同步环境音','task-1',source_video_uri='file:///shot.mp4'))
    assert result.audio_uri == 'audio://result'
    assert transport.posts[0][0].endswith('/audio/generations')
    assert transport.posts[0][1]['json']['source_video_uri'] == 'file:///shot.mp4'
