import contextvars
from collections.abc import Callable

from mcp.server.fastmcp import FastMCP
from mcp.server.transport_security import TransportSecuritySettings
from starlette.requests import Request
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Receive, Scope, Send

from .api_client import ContactScienceClient
from .config import Settings

# Per-request credential isolation via contextvars.
# GatewayTokenMiddleware sets this before the MCP handler runs.
# Python asyncio copies context per task, so concurrent SSE connections are isolated.
_gateway_creds_var: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "contactscience_gateway_creds", default=None
)


def get_client_from_context(settings: Settings) -> ContactScienceClient | None:
    """Resolve the active ContactScienceClient for the current request context."""
    authorization = _gateway_creds_var.get()
    if not authorization:
        return None
    return ContactScienceClient(authorization, settings.contactscience_base_url)


class GatewayTokenMiddleware:
    """ASGI middleware.

    Reads X-ContactScience-Authorization (required) from request headers and
    stores it in the contextvar. Returns 401 if the header is missing on
    /mcp requests.
    """

    def __init__(self, app: ASGIApp, settings: Settings):
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        path = scope.get("path", "")
        if not path.startswith("/mcp"):
            await self.app(scope, receive, send)
            return

        request = Request(scope)
        authorization = request.headers.get("x-contactscience-authorization")
        if not authorization:
            response = JSONResponse(
                {
                    "error": "Missing credentials",
                    "message": "This server requires the X-ContactScience-Authorization header",
                    "required_headers": ["X-ContactScience-Authorization"],
                    "optional_headers": [],
                },
                status_code=401,
            )
            await response(scope, receive, send)
            return

        ctx_token = _gateway_creds_var.set(authorization)
        try:
            await self.app(scope, receive, send)
        finally:
            _gateway_creds_var.reset(ctx_token)


def create_mcp_server(settings: Settings) -> FastMCP:
    """Build the FastMCP server instance and register all Contact Science tools."""
    # DNS-rebinding protection is a browser-oriented safeguard that rejects
    # non-localhost Host headers with 421. Disable it so the server works
    # correctly behind a reverse proxy or docker network.
    mcp = FastMCP(
        name="contactscience-mcp",
        instructions=(
            "Contact Science is an appointment-setting / sales engagement CRM "
            "platform MSPs use to track outbound call campaigns. This server "
            "exposes its reporting API for two record types: scheduled/completed "
            "appointments (contactscience_get_appointments) and blocked/rejected "
            "call attempts (contactscience_get_call_block). Both tools are "
            "read-only date-range reports — start_date (YYYY-MM-DD) is required "
            "by the live API, end_date narrows the range further. Use "
            "appointments to answer 'how many appointments were booked/kept in "
            "period X'; use call_block to answer 'which calls were blocked/failed "
            "to connect in period X'. There is no cross-tool relationship beyond "
            "sharing the same date-range shape — pick whichever record type the "
            "question is actually about."
        ),
        transport_security=TransportSecuritySettings(enable_dns_rebinding_protection=False),
    )

    client_factory: Callable[[], ContactScienceClient | None] = lambda: get_client_from_context(
        settings
    )

    from .tools import reports

    reports.register(mcp, client_factory)

    return mcp
