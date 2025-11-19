import asyncio
from langchain_mcp_adapters.client import MultiServerMCPClient
from llm import get_llm
from langgraph.prebuilt import create_react_agent

# Configure the client to connect to your local MCP server
mcp_client = MultiServerMCPClient(
    {
        "salesforce_mcp_server": {
            "transport": "streamable_http",
            "url": "http://localhost:8006/mcp"
        }
    }
)

async def main():
    try:
        print("Attempting to load tools from http://localhost:8006...")
        mcp_tools = await mcp_client.get_tools()

        if mcp_tools:
            print(f"\nSuccessfully discovered {len(mcp_tools)} tool(s):")
            for tool in mcp_tools:
                print(f"- Name: {tool.name}")
                print(f"  Description: {tool.description}")
                print("-" * 20)
        else:
            print("\nNo tools discovered. Check if Salesforce credentials are set and server is running.")
            return

        llm = get_llm()
        agent = create_react_agent(
            llm,
            mcp_tools
        )

        # Example 1: Describe Account Object
        print("\n--- Test 1: Describing Account Object ---")
        response_1 = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "What fields are available on the Salesforce Account object?"}]}
        )
        print(response_1['messages'][-1].content)

        # Example 2: Query Data
        print("\n--- Test 2: Querying Accounts ---")
        response_2 = await agent.ainvoke(
            {"messages": [{"role": "user", "content": "Find the names and industries of the first 3 Accounts in Salesforce."}]}
        )
        print(response_2['messages'][-1].content)

    except Exception as e:
        print(f"\nError connecting to or loading tools from MCP server: {e}")
        print("Please ensure your MCP server is running on http://localhost:8006")

if __name__ == "__main__":
    asyncio.run(main())