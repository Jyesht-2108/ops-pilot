from mcp.server import MCPServer
from sandbox import run_reproduction
from linear import get_linear_issue

mcp = MCPServer("OpsPilot Support MCP")


@mcp.tool()
def ping() -> str:
    """Check whether the Support MCP server is running."""
    return "Support MCP is running"


@mcp.tool()
async def get_ticket(ticket_id: str) -> dict:
    """
    Retrieve a support ticket from Linear.

    Args:
        ticket_id: Linear issue identifier, for example TES-5.
    """
    return await get_linear_issue(ticket_id)

@mcp.tool()
def run_sandbox_reproduction(ticket_id: str) -> dict:
    """
    Reproduce a Linear support ticket in an isolated Daytona sandbox.

    Args:
        ticket_id: Linear issue identifier, for example TES-5.
    """
    if ticket_id != "TES-5":
        return {
            "status": "not_implemented",
            "message": "Sandbox reproduction is currently configured for the Payments API test ticket TES-5."
        }

    return run_reproduction()


if __name__ == "__main__":
    mcp.run(
        transport="streamable-http",
        host="0.0.0.0",
        port=8001,
    )