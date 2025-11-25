import asyncio
import httpx

async def check_server():
    url = "http://localhost:8000/sse"
    print(f"--- TESTING CONFLUENCE SERVER CONNECTION ---")
    print(f"Target: {url}")
    
    async with httpx.AsyncClient() as client:
        try:
            # Attempt to connect to the SSE endpoint
            async with client.stream("GET", url, timeout=5.0) as response:
                print(f"✅ Connection Successful! Status Code: {response.status_code}")
                print("Server is UP and reachable.")
        except httpx.ConnectError:
            print("❌ Connection Failed: Connection Refused.")
            print("   - Is the server running?")
            print("   - Did it start on Port 8013? (Check the server terminal logs)")
            print("   - Try running: 'python3 confluence_app --port 8013'")
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_server())