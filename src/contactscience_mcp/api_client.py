import asyncio
from typing import Any

import httpx

from ._json import error_envelope

_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)
_RETRYABLE_STATUS = {429, 500, 502, 503, 504}
_MAX_RETRIES = 3
_MAX_BACKOFF_SECONDS = 20.0

# One shared connection pool for the process lifetime. No credentials are
# ever stored on it — the authorization value is passed per-request via
# headers, so this is safe to share across tenants/requests (see server.py's
# contextvar-based credential isolation, which is what actually keeps
# tenants apart).
_http_client: httpx.AsyncClient | None = None


def _get_http_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None:
        _http_client = httpx.AsyncClient(timeout=_TIMEOUT, follow_redirects=True)
    return _http_client


# status_code -> (error code, retryable). status_code 0 means a network/
# connection-level failure (no response at all).
_STATUS_TO_CODE: dict[int, tuple[str, bool]] = {
    0: ("upstream_error", True),
    400: ("invalid_argument", False),
    401: ("unauthorized", False),
    403: ("unauthorized", False),
    404: ("not_found", False),
    422: ("invalid_argument", False),
    429: ("rate_limited", True),
}


def _classify(status_code: int) -> tuple[str, bool]:
    if status_code in _STATUS_TO_CODE:
        return _STATUS_TO_CODE[status_code]
    if status_code >= 500:
        return "upstream_error", True
    return "invalid_argument", False


# Contact Science's own quirk: some in-band error shapes ({"error": "...",
# "message": "..."}) come back with a real HTTP status of 200. We classify
# those by the "error" label text since the transport-level status code
# doesn't carry the real signal in that case.
_QUIRK_ERROR_LABEL_TO_STATUS = {
    "unauthorized": 401,
    "forbidden": 403,
    "invalid parameters": 400,
    "not found": 404,
}


def _classify_quirk(resp_status_code: int, error_label: str) -> int:
    if resp_status_code >= 400:
        return resp_status_code
    return _QUIRK_ERROR_LABEL_TO_STATUS.get(error_label.strip().lower(), 400)


class ContactScienceError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        self.message = message
        super().__init__(f"Contact Science API error {status_code}: {message}")

    def to_envelope(self) -> str:
        code, retryable = _classify(self.status_code)
        return error_envelope(code, self.message, retryable)


class ContactScienceClient:
    """Async httpx client wrapping the Contact Science reporting API.

    Reuses the module-level connection pool (see _get_http_client) across
    every call made through this instance, rather than opening a new
    connection per request.

    Quirk: this API returns HTTP 200 even on auth/parameter failures — the
    error is embedded in the JSON body instead (e.g. {"error": "Unauthorized",
    "message": "Invalid API Key"}). _raise_for_status treats that shape as an
    error regardless of the transport-level status code (see
    _classify_quirk above).
    """

    def __init__(self, authorization: str, base_url: str):
        self._authorization = authorization
        self._base_url = base_url.rstrip("/")

    def _headers(self) -> dict[str, str]:
        return {
            "authorization": self._authorization,
            "Accept": "application/json",
        }

    def _clean_params(self, params: dict | None) -> dict:
        if not params:
            return {}
        return {k: v for k, v in params.items() if v is not None}

    async def get(self, path: str, params: dict | None = None) -> Any:
        return await self._request("GET", path, params=params)

    async def post(self, path: str, json_body: Any = None, params: dict | None = None) -> Any:
        return await self._request("POST", path, params=params, json_body=json_body)

    async def _request(
        self, method: str, path: str, params: dict | None = None, json_body: Any = None
    ) -> Any:
        client = _get_http_client()
        url = f"{self._base_url}{path}"
        headers = self._headers()
        params = self._clean_params(params)

        last_exc: Exception | None = None
        for attempt in range(_MAX_RETRIES + 1):
            try:
                resp = await client.request(
                    method, url, headers=headers, params=params, json=json_body
                )
            except httpx.RequestError as e:
                last_exc = e
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(min(2**attempt, _MAX_BACKOFF_SECONDS))
                    continue
                raise ContactScienceError(0, f"{e or type(e).__name__} (url={url})") from e

            if resp.status_code in _RETRYABLE_STATUS and attempt < _MAX_RETRIES:
                delay = self._retry_delay(resp, attempt)
                await asyncio.sleep(delay)
                continue

            body = self._parse_body(resp)
            self._raise_for_status(resp, body)
            return body

        # Unreachable in practice (loop always returns or raises above), but
        # keeps type checkers happy and guards against future edits.
        if last_exc:
            raise ContactScienceError(0, f"{last_exc}") from last_exc
        raise ContactScienceError(0, "request failed with no response")

    def _retry_delay(self, resp: httpx.Response, attempt: int) -> float:
        retry_after = resp.headers.get("Retry-After")
        if retry_after:
            try:
                return min(float(retry_after), _MAX_BACKOFF_SECONDS)
            except ValueError:
                pass
        return min(2**attempt, _MAX_BACKOFF_SECONDS)

    def _parse_body(self, resp: httpx.Response) -> Any:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return {"raw_response": resp.text}

    def _raise_for_status(self, resp: httpx.Response, body: Any) -> None:
        if isinstance(body, dict) and "error" in body:
            label = body["error"] if isinstance(body["error"], str) else str(body["error"])
            status = _classify_quirk(resp.status_code, label)
            raise ContactScienceError(status, body.get("message") or label)
        if resp.status_code >= 400:
            msg = body if isinstance(body, str) else str(body)
            raise ContactScienceError(resp.status_code, msg)
