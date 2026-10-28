"""One budget around saved-usage HTTP admission, including outer middleware."""
import re
from urllib.parse import parse_qsl

from starlette.responses import JSONResponse

from .asset_usage_budget import UsageBudgetError, usage_read_budget, isolate_usage_request_context
from ..repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_coordination_only,
    isolate_coordination_request_context,
)

_route = re.compile(r'/api/(?:v1/)?novels/[^/]+/experimental/production/assets/[^/]+/studio-(graph|timeline|asset)-usages')
_audio_history_status = re.compile(r'/api/(?:v1/)?projects/[^/]+/studio/assets/[^/]+/history')


class AssetUsageRequestBudgetMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # A keepalive server may create the next task while sending the previous
        # response. Isolate every scope, including unmatched routes/websockets;
        # nested same-request helpers keep their original reuse semantics.
        with isolate_usage_request_context(), isolate_coordination_request_context():
            return await self._request(scope, receive, send)

    async def _request(self, scope, receive, send):
        history = (scope.get('type') == 'http' and scope.get('method') == 'GET'
                   and _audio_history_status.fullmatch(scope.get('path', '')) is not None)
        match = _route.fullmatch(scope.get('path', '')) if scope.get('type') == 'http' else None
        query = scope.get('query_string', b'')
        if not history and (match is None or scope.get('method') != 'GET'
                or (not query and match.group(1) != 'asset')):
            return await self.app(scope, receive, send)
        # Only bounded mode detection precedes original authentication. Original
        # query validation remains after auth. Oversized requests cannot initialize
        # coordination while waiting to reach that validation.
        strict = history or len(query) > 2048 or any(key == 'strict_read_only' for key, _ in
            parse_qsl(query.decode('ascii', errors='replace'), keep_blank_values=True))
        started = False
        async def private_send(message):
            nonlocal started
            if message['type'] == 'http.response.start':
                started = True
                message = {**message, 'headers': [(key, value) for key, value in message.get('headers', [])
                    if key.lower() not in {b'cache-control', b'x-content-type-options'}]
                    + [(b'cache-control', b'no-store'), (b'x-content-type-options', b'nosniff')]}
            await send(message)
        with usage_read_budget(fresh=True), existing_coordination_only(strict):
            try:
                return await self.app(scope, receive, private_send)
            except (UsageBudgetError, ReadOnlyCoordinationUnavailable) as exc:
                if started:
                    raise
                code = ('AUDIO_HISTORY_READ_ONLY_UNAVAILABLE' if history else
                        'STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE' if isinstance(exc, ReadOnlyCoordinationUnavailable)
                        else 'STUDIO_' + match.group(1).upper() + '_USAGE_UNAVAILABLE')
                detail = {'code': code}
                response = JSONResponse(status_code=409, content={
                    'detail': detail, 'code': code, 'message': code, 'details': detail,
                    'request_id': scope.get('state', {}).get('request_id', '')})
                await response(scope, receive, private_send)
