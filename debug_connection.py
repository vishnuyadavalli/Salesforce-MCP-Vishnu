import asyncio
import httpx

async def check_server():
    url = "http://localhost:8000/sse"
    print(f"Testing connection to: {url}")
    
    async with httpx.AsyncClient() as client:
        try:
            print("Testing Connection");
            # Attempt to connect to the SSE endpoint
            async with client.stream("GET", url, timeout=5.0) as response:
                print(f"✅ Connection Successful! Status Code: {response.status_code}")
                print("Server is running and accessible.")
        except httpx.ConnectError:
            print("❌ Connection Failed: Could not connect to the server.")
            print("   - Is the server running in a separate terminal?")
            print("   - Is it running on port 8000?")
        except Exception as e:
            print(f"❌ Unexpected Error: {e}")

if __name__ == "__main__":
    asyncio.run(check_server())