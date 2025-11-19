from mcp.server.fastmcp import FastMCP

# Initialize FastMCP server for tools (SSE)
mcp_application = FastMCP("server", stateless_http=True)

# Import tool modules so their @mcp_application.tool() decorators execute
# and register tools with the FastMCP instance.
try:
    import salesforce  # noqa: F401  (imported for side effects)
except Exception as _e: 
    # If this import fails, the server will start but no tools will be registered.
    # You can log or raise here if strict behavior is desired.
    print(f"Failed to import salesforce tools: {_e}")
    pass