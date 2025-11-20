import logging
import os
import sys
import click
import uvicorn
from starlette.applications import Starlette
from starlette.routing import Route
from starlette.responses import PlainTextResponse

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# ----------------

from fastmcp_instantiator import mcp_application
from properties import CIRCUIT_LLM_API_APP_KEY

# 1. Dependency Check
try:
    import simple_salesforce
except ImportError:
    print("\n❌ CRITICAL ERROR: 'simple-salesforce' is not installed.")
    print("   Please run: pip install simple-salesforce")
    sys.exit(1)

# 2. Register Tools
try:
    import salesforce
    print("✅ Salesforce tools registered.")
except Exception as e:
    print(f"❌ FAILED to import Salesforce tools: {e}")
    sys.exit(1)

def create_app():
    """
    Manually construct the Starlette app to expose FastMCP handlers.
    """
    # Now that stateless_http=True is removed from instantiator, 
    # these handlers MUST exist.
    try:
        sse_handler = mcp_application.sse_handler
        messages_handler = mcp_application.messages_handler
    except AttributeError:
        print("\n❌ ERROR: FastMCP is missing SSE handlers.")
        print("   Please ensure app/fastmcp_instantiator.py does NOT have 'stateless_http=True'")
        sys.exit(1)

    async def health_check(request):
        return PlainTextResponse("ok")

    # Define the routes explicitly
    routes = [
        Route("/sse", endpoint=sse_handler, methods=["GET"]),
        Route("/messages", endpoint=messages_handler, methods=["POST"]),
        Route("/healthz", endpoint=health_check, methods=["GET"]),
        Route("/readyz", endpoint=health_check, methods=["GET"]),
    ]

    return Starlette(debug=True, routes=routes)

@click.command()
@click.option('--host', 'host', default='0.0.0.0')
@click.option('--port', 'port', default=8012)
def main(host, port):
    """Local runner for the MCP server."""
    print(f"\n--- STARTING SERVER ON PORT {port} (Manual SSE Mode) ---")
    print(f"Server URL: http://{host}:{port}/sse")
    
    # Create the app and run it with Uvicorn directly
    try:
        app = create_app()
        uvicorn.run(app, host=host, port=port)
    except Exception as e:
        print(f"Server failed to start: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()