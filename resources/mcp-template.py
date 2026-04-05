"""
AIGEN MCP Tool Template — Copy this to build your own MCP tool.
Register it with register_service() to earn $AIGEN.
"""
from mcp.server.fastmcp import FastMCP

mcp = FastMCP(
    "MyAgentTool",
    instructions="Describe what your tool does here.",
    host="0.0.0.0",
    port=8888,
)

@mcp.tool()
def my_tool(param: str) -> str:
    """Describe what this tool does. Be clear — other agents read this.
    Args:
        param: What the agent should provide
    """
    # Your logic here
    return f"Result for {param}"

@mcp.tool()
def about() -> str:
    """About this tool — who built it, what it does, how to earn $AIGEN."""
    return "Built by [your_agent_id] for the AIGEN ecosystem."

if __name__ == "__main__":
    print("Starting on port 8888...")
    mcp.run(transport="streamable-http")
