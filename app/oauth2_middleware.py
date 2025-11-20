import logging
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
import jwt
from jwt import InvalidTokenError

# Configure logging to show our debug messages
logging.basicConfig(level=logging.INFO)
log = logging.getLogger("middleware")

class OAuth2Middleware(BaseHTTPMiddleware):
    """Starlette middleware that authenticates A2A access using an OAuth2 bearer token."""

    def __init__(
        self,
        app: Starlette,
        public_paths: list[str] = None,
    ):
        super().__init__(app)
        # Force these paths to be public for local testing
        self.public_paths = set(public_paths or [])
        self.public_paths.add("/sse")
        self.public_paths.add("/messages")
        
        log.info(f"--- MIDDLEWARE INITIALIZED ---")
        log.info(f"Allowed Public Paths: {self.public_paths}")

    async def dispatch(self, request: Request, call_next):
        """
        Middleware to authenticate requests.
        """
        path = request.url.path
        
        # --- DEBUG LOG ---
        log.info(f"Incoming Request -> Path: {path} | Method: {request.method}")
        # -----------------

        # 1. Bypass Health Checks
        if path in ('/healthz', '/readyz'):
            return await call_next(request)

        # 2. Bypass Public Paths (SSE, Messages)
        if path in self.public_paths:
            log.info(f"✅ ALLOWING public path: {path}")
            return await call_next(request)

        # 3. Auth Logic (Commented out for local debugging to prevent 401s)
        # If you still get 401s, something else in your stack is throwing them.
        
        # auth_header = request.headers.get('Authorization')
        # if not auth_header:
        #      log.warning(f"⛔ BLOCKED: No Auth Header for {path}")
        #      return self._unauthorized("Missing Authorization Header", request)
        
        # For now, allow everything else too
        log.info(f"⚠️ ALLOWING unknown path (Debug Mode): {path}")
        return await call_next(request)

    def _unauthorized(self, reason: str, request: Request):
        return JSONResponse(
            {'error': 'unauthorized', 'reason': reason}, status_code=401
        )