"""Host-selected Alibaba Model Studio text preset; no discovery or automatic IO.

Official regional endpoint reference (checked 2026-10-17):
https://www.alibabacloud.com/help/en/model-studio/base-url
Only standard pay-as-you-go shared API endpoints are preset. Coding/Token Plan
endpoints are deliberately absent; no purchase, credentials or cloud permission
is provisioned here. Original transport/vault/route and budget owners still apply.
"""
from types import MappingProxyType

from .openai_compatible import CompatibleProviderConfig, OpenAICompatibleTextProvider

BAILIAN_REGION_URLS = MappingProxyType({
    'cn-beijing': 'https://dashscope.aliyuncs.com/compatible-mode/v1',
    'ap-southeast-1': 'https://dashscope-intl.aliyuncs.com/compatible-mode/v1',
    'us-east-1': 'https://dashscope-us.aliyuncs.com/compatible-mode/v1',
    'cn-hongkong': 'https://cn-hongkong.dashscope.aliyuncs.com/compatible-mode/v1',
})


def bailian_configuration(region='cn-beijing'):
    if not isinstance(region, str) or region not in BAILIAN_REGION_URLS:
        raise ValueError('BAILIAN_PRESET_REGION_UNSUPPORTED')
    return CompatibleProviderConfig('aliyun-bailian', BAILIAN_REGION_URLS[region], 'DASHSCOPE_API_KEY')


class BailianTextProvider(OpenAICompatibleTextProvider):
    """Standard text completion using the original transport; no tool/vision grant.

    This preset explicitly requests non-thinking mode. Dedicated thinking-only
    or model-specific protocols are not advertised as supported by this preset.
    https://www.alibabacloud.com/help/en/model-studio/deep-thinking
    """
    def __init__(self, region='cn-beijing', *, transport=None):
        super().__init__(bailian_configuration(region), transport=transport)

    def _payload(self, request, stream):
        return {**super()._payload(request, stream), 'enable_thinking': False}
