import sys
import os

# Ensure we can import modules
sys.path.insert(0, os.path.abspath("app"))

from server_instance import mcp_application

print("\n--- INSPECTING FastMCP OBJECT ---")
print(f"Type: {type(mcp_application)}")
print("\nAttributes:")

# List all attributes that look like they might be the ASGI app
candidates = []
for attr in dir(mcp_application):
    if not attr.startswith("__"):
        candidates.append(attr)

print(candidates)

print("\nChecking for common ASGI candidates:")
for attr in ["app", "asgi_app", "starlette_app", "fastapi_app", "_http_app", "server"]:
    if hasattr(mcp_application, attr):
        print(f"✅ FOUND: mcp_application.{attr}")
    else:
        print(f"   - mcp_application.{attr} (not found)")