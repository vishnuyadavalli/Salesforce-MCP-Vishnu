import logging
import os
import click
import sys
from typing import Optional

from starlette.responses import PlainTextResponse
import uvicorn
from fastmcp import FastMCP
from oauth2_middleware import OAuth2Middleware
from fastmcp_instantiator import mcp_application
from properties import (
    CIRCUIT_LLM_API_APP_KEY, 
    CIRCUIT_LLM_API_CLIENT_ID, 
    CIRCUIT_LLM_API_CLIENT_SECRET,
    CIRCUIT_LLM_API_ENDPOINT, 
    CIRCUIT_LLM_API_MODEL_NAME, 
    CIRCUIT_LLM_API_VERSION, 
    JWKS_URI, 
    AUDIENCE, 
    ISSUER, 
    CIRCUIT_CLIENT_ID,
    SALESFORCE_USERNAME,
    SALESFORCE_PASSWORD
)

# Inject env vars for deep modules if needed
os.environ["CIRCUIT_LLM_API_APP_KEY"] = CIRCUIT_LLM_API_APP_KEY
# ... (others can remain if needed by libraries relying on os.environ)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class MissingAPPKeyError(Exception):
    """Exception for missing APP key."""

class MissingCredentialsError(Exception):
    """Exception for missing Credentials key."""

def build_mcp_app(host: Optional[str] = None, port: Optional[int] = None):
    """Build and return the A2A Starlette application."""
    if not CIRCUIT_LLM_API_APP_KEY:
        raise MissingAPPKeyError('CIRCUIT_LLM_API_APP_KEY environment variable not set.')
    
    # Basic sanity check for Salesforce creds (optional, but good for debugging)
    if not SALESFORCE_USERNAME or not SALESFORCE_PASSWORD:
        logger.warning("WARNING: SALESFORCE_USERNAME or SALESFORCE_PASSWORD not set in properties.py")

    public_host = host or os.getenv('PUBLIC_HOST') or 'localhost'
    public_port = port or int(os.getenv('PUBLIC_PORT', '8006'))
    public_scheme = os.getenv('PUBLIC_SCHEME', 'http')

    app = mcp_application.streamable_http_app()

    app.add_middleware(OAuth2Middleware)

    async def _ok(_request):
        return PlainTextResponse('ok')
    app.add_route('/healthz', _ok, methods=['GET'])
    app.add_route('/readyz', _ok, methods=['GET'])

    return app

app = build_mcp_app()

@click.command()
@click.option('--host', 'host', default='0.0.0.0')
@click.option('--port', 'port', default=8006)
def main(host, port):
    """Local runner for the MCP server."""
    try:
        local_app = build_mcp_app(host=host, port=port)
        uvicorn.run(local_app, host=host, port=port)
    except Exception as e:
        logger.error(f'An error occurred during server startup: {e}')
        sys.exit(1)

if __name__ == '__main__':
    main()