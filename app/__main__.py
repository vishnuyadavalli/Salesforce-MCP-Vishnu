import logging
import os
import sys
import click

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# ----------------

# Import from your NEW server instance file
from server_instance import mcp_application

# 1. Register Tools
try:
    import salesforce
    print("✅ Salesforce tools registered.")
except ImportError:
    print("❌ CRITICAL: 'simple-salesforce' missing.")
    sys.exit(1)
except Exception as e:
    print(f"❌ FAILED to import Salesforce tools: {e}")
    sys.exit(1)

@click.command()
def main():
    """Local runner for the MCP server."""
    print("\n--- STARTING SERVER (Default Port 8012) ---")
    print("The server will pick a default port (usually 8012).")
    print("Check the logs below for: 'Uvicorn running on http://0.0.0.0:8012'")
    
    # CORRECTED: Call run() without host/port arguments
    # This avoids the TypeError you were seeing.
    mcp_application.run(transport="sse")

if __name__ == "__main__":
    main()