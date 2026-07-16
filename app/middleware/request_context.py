"""
Request correlation-ID middleware.

Attaches a unique `request_id` to every inbound request (reusing an
inbound `X-Request-ID` header if the caller/load-balancer already set one),
stores it on `request.state`, binds it into the Loguru context so every log
line for this request is traceable, and echoes it back in the response
header.
"""

import uuid

from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.constants.api import REQUEST_ID_HEADER


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request_id = request.headers.get(REQUEST_ID_HEADER) or str(uuid.uuid4())
        request.state.request_id = request_id

        with logger.contextualize(request_id=request_id):
            response = await call_next(request)

        response.headers[REQUEST_ID_HEADER] = request_id
        return response
