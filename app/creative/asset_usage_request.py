"""One budget around saved-usage HTTP admission, including outer middleware."""
import re
from urllib.parse import parse_qsl

from starlette.responses import JSONResponse

from .asset_usage_budget import UsageBudgetError, usage_read_budget
from ..repositories.file.mutation_coordinator import (
    ReadOnlyCoordinationUnavailable, existing_coordination_only,
)

_route = re.compile(r'/api/(?:v1/)?novels/[^/]+/experimental/production/assets/[^/]+/studio-(graph|timeline|asset)-usages')


class AssetUsageRequestBudgetMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        match = _route.fullmatch(scope.get('path', '')) if scope.get('type') == 'http' else None
        query = scope.get('query_string', b'')
        if (match is None or scope.get('method') != 'GET'
                or (not query and match.group(1) != 'asset')):
            return await self.app(scope, receive, send)
        # Only bounded mode detection precedes original authentication. Original
        # query validation remains after auth. Oversized requests cannot initialize
        # coordination while waiting to reach that validation.
        strict = len(query) > 2048 or any(key == 'strict_read_only' for key, _ in
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
                code = ('STUDIO_USAGE_STRICT_READ_ONLY_UNAVAILABLE' if isinstance(exc, ReadOnlyCoordinationUnavailable)
                        else 'STUDIO_' + match.group(1).upper() + '_USAGE_UNAVAILABLE')
                detail = {'code': code}
                response = JSONResponse(status_code=409, content={
                    'detail': detail, 'code': code, 'message': code, 'details': detail,
                    'request_id': scope.get('state', {}).get('request_id', '')})
                await response(scope, receive, private_send)
