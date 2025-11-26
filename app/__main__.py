import sys
import os
import uvicorn

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# ----------------

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

def main():
    print("\n--- STARTING SALESFORCE MCP SERVER (Port 8012) ---")
    
    # CRITICAL FIX: 
    # 1. Run 'sse_app' (the actual web app) instead of the wrapper.
    # 2. Use uvicorn directly to enforce the port.
    uvicorn.run(mcp_application.sse_app, host="0.0.0.0", port=8014)

if __name__ == "__main__":
    main()