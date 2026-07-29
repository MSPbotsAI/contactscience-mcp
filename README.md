# contactscience-mcp

MCP server for **Contact Science** — an appointment-setting / sales
engagement CRM platform. Exposes its appointment and call-block reporting
endpoints as MCP tools.

> Naming note: MSPbots' own integration is registered as "Contact Science"
> (`subjectCode=SCIENCE`); the underlying API host is Contact Science's own
> backend, `www.klpzmedia.com`. This MCP covers exactly the 2 GET endpoints
> MSPbots itself has configured — see **Known Gaps** below for why the scope
> stops there.

## Overview

- Stateless HTTP service. No credentials are ever persisted — each request
  supplies its own token via a header, used only for the lifetime of that
  single request.
- Supports concurrent requests; per-request credential isolation is done via
  Python `contextvars`, not a global/shared client instance.
- Entry points: `POST /mcp` (MCP protocol) and `GET /health` (health check).
- Default port: `8080` (configurable via `MCP_HTTP_PORT`).

## Authentication

Contact Science authenticates with a single static **API token**, generated
in the Contact Science admin portal. MSPbots' own integration convention
sends this token as the raw value of the `authorization` header — **no
`Bearer ` prefix** — and this server forwards it exactly that way.

### HEADER 授权参数说明

| Header | 类型 | 是否必填 | 默认值 | 枚举值 | 字段描述 | Example |
|---|---|---|---|---|---|---|
| `X-ContactScience-Authorization` | string | 是 | 无 | 无 | Contact Science 静态 API Token，原样转发为上游 `authorization` 请求头（不加 `Bearer ` 前缀） | `a1b2c3d4e5f6...` |

Missing the header returns `401`:
```json
{
  "error": "Missing credentials",
  "message": "This server requires the X-ContactScience-Authorization header",
  "required_headers": ["X-ContactScience-Authorization"],
  "optional_headers": []
}
```

**Important quirk**: unlike most REST APIs, Contact Science's own endpoints
return **HTTP 200 even when the token is invalid** — the error is embedded
in the JSON body instead (`{"error": "Unauthorized", "message": "Invalid API
Key"}`). This server's client (`api_client.py`) detects that body shape and
raises a tool-level error regardless of the HTTP status code, so callers
still see a clear `Error: Contact Science API error ...` message rather than
silently getting an error payload back as if it were real data.

## Environment Variables

| Variable | 类型 | 是否必填 | 默认值 | 说明 |
|---|---|---|---|---|
| `MCP_HTTP_PORT` | int | 否 | `8080` | HTTP 监听端口 |
| `MCP_HTTP_HOST` | string | 否 | `0.0.0.0` | HTTP 监听地址 |
| `CONTACTSCIENCE_BASE_URL` | string | 否 | `https://www.klpzmedia.com/apis/1.0` | Contact Science API 基础 URL |

## MCP Endpoint

- `POST /mcp` — MCP protocol (streamable HTTP transport)
- `GET /health` — health check, returns `{"status": "ok", "service": "contactscience-mcp", "transport": "http"}`

## Tool List

Both tools are plain `GET` calls with **no required parameters** — this
matches exactly how MSPbots itself calls this integration today. Each tool
accepts an optional `extra_params` pass-through dict for any additional
query-string filters (e.g. a date range), since Contact Science does not
publish a public API reference (see **Known Gaps**).

| Tool | 功能 | 参数 |
|---|---|---|
| `contactscience_get_appointments` | 列出预约（appointment）报表记录 | `extra_params: dict[str,str] \| None` |
| `contactscience_get_call_block` | 列出通话拦截（call block）报表记录 | `extra_params: dict[str,str] \| None` |

## 测试示例

```bash
# Health check
curl -s http://localhost:8080/health

# Call a tool via the MCP protocol (streamable HTTP) — requires an
# initialize handshake first per the MCP spec; abbreviated example below
# shows the tool-call request body only:
curl -s -X POST http://localhost:8080/mcp \
  -H "X-ContactScience-Authorization: <your-contact-science-token>" \
  -H "Content-Type: application/json" \
  -H "Accept: application/json, text/event-stream" \
  -H "mcp-session-id: <session-id-from-initialize>" \
  -d '{
    "jsonrpc": "2.0",
    "id": 1,
    "method": "tools/call",
    "params": {
      "name": "contactscience_get_appointments",
      "arguments": {}
    }
  }'
```

Expected: `200` with the appointments list on a valid token; `200` with
`{"error": "Unauthorized", "message": "Invalid API Key"}` in the body on an
invalid token — surfaced by this server as a tool-level `Error: ...` message
(see the auth quirk note above), not treated as real data.

## API Reference

- No public API documentation exists for Contact Science's reporting API.
  The vendor's marketing site (contactscience.com) and backend
  (klpzmedia.com) do not publish a developer reference, and no
  Swagger/OpenAPI spec or third-party reference was found. The two endpoints
  implemented here were confirmed directly from MSPbots' own stored
  integration configuration and by probing the live API.

## Known Gaps

- **Scope is exactly MSPbots' 2 configured endpoints, not a larger vendor
  API surface** — Contact Science does not publish any public API
  reference, so (like `bvoip-mcp` earlier in this program) there was no
  broader public spec to weigh a wider scope against.
- Response field shapes are not independently documented — whatever the
  live API returns is passed through as-is; no schema/field reference
  exists to validate against.
- Request-side filter parameters (e.g. a date range) are undocumented;
  `extra_params` is provided so a caller who discovers additional supported
  filters can still pass them through.
