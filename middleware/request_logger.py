"""
Custom Django middleware — logs every request with method, path, status, and duration.

Django middleware lifecycle (MIDDLEWARE list in settings, top → bottom):
  1. Request travels DOWN the stack: each middleware's __call__ runs before
     passing to the next via self.get_response(request).
  2. Response travels UP the stack: code after get_response() runs in reverse
     order. This is where we log because we now have the response status.

To add middleware: append it to the MIDDLEWARE list in settings.
To remove it: simply remove the entry — no other wiring needed.
"""

import logging
import time

from django.http import HttpRequest, HttpResponse

logger = logging.getLogger(__name__)


class RequestLoggingMiddleware:
    def __init__(self, get_response: object) -> None:
        # Called once when Django starts — use for one-time setup.
        self.get_response = get_response

    def __call__(self, request: HttpRequest) -> HttpResponse:
        start = time.monotonic()

        response: HttpResponse = self.get_response(request)  # type: ignore[call-arg]

        duration_ms = (time.monotonic() - start) * 1000
        logger.info(
            "%s %s → %d (%.1f ms) [%s]",
            request.method,
            request.path,
            response.status_code,
            duration_ms,
            request.META.get("REMOTE_ADDR", "-"),
        )
        return response
