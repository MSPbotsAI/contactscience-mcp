import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import ContactScienceClient, ContactScienceError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], ContactScienceClient | None]) -> None:

    @mcp.tool()
    async def contactscience_get_appointments(
        start_date: str,
        end_date: str | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """List Contact Science appointment report records.

        API: GET /reports/appointments

        Confirmed live against the real API: start_date is required (the
        vendor returns {"error": "Invalid parameters", "message": "startDate
        parameter is missing"} without it); end_date is an accepted optional
        filter. Beyond these two, Contact Science's full filter reference is
        not publicly documented; pass any additional query-string filters
        via extra_params if known.

        Args:
            start_date: Required. Report start date (YYYY-MM-DD).
            end_date: Optional. Report end date (YYYY-MM-DD).
            extra_params: Optional raw query-string parameters to forward,
                for filters not covered above.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"startDate": start_date, "endDate": end_date}
        if extra_params:
            params.update(extra_params)
        try:
            result = await client.get("/reports/appointments", params=params)
            return json.dumps(result, indent=2)
        except ContactScienceError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def contactscience_get_call_block(
        start_date: str,
        end_date: str | None = None,
        extra_params: dict[str, str] | None = None,
    ) -> str:
        """List Contact Science call block report records.

        API: GET /reports/callBlock

        Confirmed live against the real API: start_date is required (the
        vendor returns {"error": "Invalid parameters", "message": "startDate
        parameter is missing"} without it); end_date is an accepted optional
        filter. Beyond these two, Contact Science's full filter reference is
        not publicly documented; pass any additional query-string filters
        via extra_params if known.

        Args:
            start_date: Required. Report start date (YYYY-MM-DD).
            end_date: Optional. Report end date (YYYY-MM-DD).
            extra_params: Optional raw query-string parameters to forward,
                for filters not covered above.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"startDate": start_date, "endDate": end_date}
        if extra_params:
            params.update(extra_params)
        try:
            result = await client.get("/reports/callBlock", params=params)
            return json.dumps(result, indent=2)
        except ContactScienceError as e:
            return f"Error: {e}"
