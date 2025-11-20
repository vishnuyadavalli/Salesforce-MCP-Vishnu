from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server
# CRITICAL: Do NOT use stateless_http=True here.
# We need standard mode so we can access .sse_handler in main.py
mcp_application = FastMCP("SalesforceServer")

# Import tool modules so their @mcp_application.tool() decorators execute
try:
    import salesforce  # noqa: F401
except Exception as _e: 
    print(f"Failed to import salesforce tools: {_e}")
    pass