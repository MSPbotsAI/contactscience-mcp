import json
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP

from ..api_client import ContactScienceClient, ContactScienceError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], ContactScienceClient | None]) -> None:

    @mcp.tool()
    async def contactscience_get_appointments(extra_params: dict[str, str] | None = None) -> str:
        """List Contact Science appointment report records.

        API: GET /reports/appointments

        No required parameters. Contact Science's full filter reference is
        not publicly documented; pass any additional query-string filters
        via extra_params if known.

        Args:
            extra_params: Optional raw query-string parameters to forward,
                for filters not covered above.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get("/reports/appointments", params=extra_params)
            return json.dumps(result, indent=2)
        except ContactScienceError as e:
            return f"Error: {e}"

    @mcp.tool()
    async def contactscience_get_call_block(extra_params: dict[str, str] | None = None) -> str:
        """List Contact Science call block report records.

        API: GET /reports/callBlock

        No required parameters. Contact Science's full filter reference is
        not publicly documented; pass any additional query-string filters
        via extra_params if known.

        Args:
            extra_params: Optional raw query-string parameters to forward,
                for filters not covered above.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        try:
            result = await client.get("/reports/callBlock", params=extra_params)
            return json.dumps(result, indent=2)
        except ContactScienceError as e:
            return f"Error: {e}"
