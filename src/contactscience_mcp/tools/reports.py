from collections.abc import Callable
from typing import Annotated

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations
from pydantic import Field

from .._json import dump_json_capped
from ..api_client import ContactScienceClient, ContactScienceError
from ._common import NO_TOKEN


def register(mcp: FastMCP, client_factory: Callable[[], ContactScienceClient | None]) -> None:

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def contactscience_get_appointments(
        start_date: Annotated[
            str,
            Field(
                description="Report start date (YYYY-MM-DD). Required — the API rejects calls without it."
            ),
        ],
        end_date: Annotated[
            str | None, Field(description="Report end date (YYYY-MM-DD), optional.")
        ] = None,
        extra_params: Annotated[
            dict[str, str] | None,
            Field(description="Extra query-string filters to forward, for filters not covered above."),
        ] = None,
    ) -> str:
        """List Contact Science appointment report records.

        Use for questions about scheduled/completed appointments in a date
        range. start_date is required.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"startDate": start_date, "endDate": end_date}
        if extra_params:
            params.update(extra_params)
        try:
            result = await client.get("/reports/appointments", params=params)
            return dump_json_capped(result)
        except ContactScienceError as e:
            return e.to_envelope()

    @mcp.tool(annotations=ToolAnnotations(readOnlyHint=True))
    async def contactscience_get_call_block(
        start_date: Annotated[
            str,
            Field(
                description="Report start date (YYYY-MM-DD). Required — the API rejects calls without it."
            ),
        ],
        end_date: Annotated[
            str | None, Field(description="Report end date (YYYY-MM-DD), optional.")
        ] = None,
        extra_params: Annotated[
            dict[str, str] | None,
            Field(description="Extra query-string filters to forward, for filters not covered above."),
        ] = None,
    ) -> str:
        """List Contact Science call block report records.

        Use for questions about blocked/rejected call attempts in a date
        range. start_date is required.
        """
        client = client_factory()
        if client is None:
            return NO_TOKEN
        params = {"startDate": start_date, "endDate": end_date}
        if extra_params:
            params.update(extra_params)
        try:
            result = await client.get("/reports/callBlock", params=params)
            return dump_json_capped(result)
        except ContactScienceError as e:
            return e.to_envelope()
