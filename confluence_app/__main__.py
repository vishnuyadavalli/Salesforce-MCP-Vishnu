import sys
import os

# Ensure we can import modules from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from server_instance import mcp_application
# Import tools to register them with the server
import confluence_tools

def main():
    print("\n--- STARTING CONFLUENCE MCP SERVER ---")
    
    # FIX: FastMCP reads settings from command line arguments, not Python arguments.
    # We manually inject the port into sys.argv so it picks it up automatically.
    if "--port" not in sys.argv:
        print("✅ Auto-configuring Port 8013...")
        sys.argv.extend(["--port", "8013"])
    
    # Now run normally; it will see the --port 8013 we just added
    mcp_application.run(transport="sse")

if __name__ == "__main__":
    main()