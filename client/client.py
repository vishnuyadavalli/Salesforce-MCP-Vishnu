import asyncio
import traceback
from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from llm import get_llm

# Configure the client to connect to your local MCP server
mcp_client = MultiServerMCPClient(
    {
        "salesforce_mcp_server": {
            "transport": "sse",             # Use standard SSE transport
            "url": "http://localhost:8012/sse" # Point to the SSE endpoint
        }
    }
)

async def main():
    print("--- CLIENT STARTED ---")
    try:
        # 1. Test LLM Credentials first
        print("1. Testing LLM Credentials...")
        try:
            llm = get_llm()
            print("   ✅ LLM Token obtained successfully.")
        except Exception as e:
            print(f"   ❌ LLM Error: {e}")
            print("   ⚠️ CHECK YOUR properties.py: Are CIRCUIT_LLM_... keys set?")
            return

        # 2. Connect to MCP Server
        print("2. Connecting to MCP Server (http://localhost:8012/sse)...")
        try:
            mcp_tools = await mcp_client.get_tools()
        except Exception as e:
             print("\n❌ MCP CONNECTION ERROR:")
             traceback.print_exc() 
             return

        if mcp_tools:
            print(f"\n   ✅ Successfully discovered {len(mcp_tools)} tool(s):")
            for tool in mcp_tools:
                print(f"   - {tool.name}")
        else:
            print("\n   ⚠️ No tools discovered.")
            return

        # 3. Run Agent
        print("\n3. Initializing Agent...")
        agent = create_react_agent(llm, mcp_tools)

        # Example 1: Describe Account Object
        print("\n4. Running Query...")
        response = await agent.ainvoke(
            {"messages": [HumanMessage(content="What fields are available on the Salesforce Account object?")]}
        )
        print("\n✅ Final Answer:")
        print(response["messages"][-1].content)

    except Exception as e:
        print(f"\n❌ UNHANDLED ERROR: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())