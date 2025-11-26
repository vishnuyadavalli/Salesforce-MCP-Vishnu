import sys
import os
import uvicorn

# Ensure we can import modules from the current directory
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

from server_instance import mcp_application
# Import tools to register them with the server
import confluence_tools

def main():
    print("\n--- STARTING CONFLUENCE MCP SERVER ---")
    print("✅ Force-starting Uvicorn on Port 8013...")
    
    # CRITICAL FIX: Use 'mcp_application.sse_app'
    uvicorn.run(mcp_application.sse_app, host="0.0.0.0", port=8013)

if __name__ == "__main__":
    main()