from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# CRITICAL: Do NOT use stateless_http=True here.
# We need standard mode so we can access .sse_handler in main.py
mcp_application = FastMCP("SalesforceServer")

