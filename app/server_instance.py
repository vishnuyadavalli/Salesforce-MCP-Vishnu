from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# We use a new file to bypass any caching issues.
# stateless_http defaults to False (SSE Enabled)
mcp_application = FastMCP("SalesforceServer")