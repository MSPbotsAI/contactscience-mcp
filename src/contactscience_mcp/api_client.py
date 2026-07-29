from typing import Any

import httpx


class ContactScienceError(Exception):
    def __init__(self, status_code: int, message: str):
        self.status_code = status_code
        super().__init__(f"Contact Science API error {status_code}: {message}")


class ContactScienceClient:
    """Async httpx client wrapping the Contact Science reporting API.

    Quirk: this API returns HTTP 200 even on auth failure — the error is
    embedded in the JSON body instead (e.g. {"error": "Unauthorized",
    "message": "Invalid API Key"}). _raise_for_status treats that shape as
    an error regardless of the HTTP status code.
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
        async with httpx.AsyncClient(timeout=30.0) as client:
            try:
                resp = await client.get(
                    f"{self._base_url}{path}",
                    headers=self._headers(),
                    params=self._clean_params(params),
                )
            except httpx.RequestError as e:
                raise ContactScienceError(
                    0, f"{e or type(e).__name__} (url={self._base_url}{path})"
                ) from e
            body = self._parse_body(resp)
            self._raise_for_status(resp, body)
            return body

    def _parse_body(self, resp: httpx.Response) -> Any:
        if not resp.content:
            return None
        try:
            return resp.json()
        except ValueError:
            return {"raw_response": resp.text}

    def _raise_for_status(self, resp: httpx.Response, body: Any) -> None:
        if isinstance(body, dict) and "error" in body:
            raise ContactScienceError(resp.status_code, body.get("message") or body["error"])
        if resp.status_code >= 400:
            msg = body if isinstance(body, str) else str(body)
            raise ContactScienceError(resp.status_code, msg)
