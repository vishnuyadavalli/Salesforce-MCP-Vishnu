import asyncio
from client.llm import get_llm
from langchain_core.messages import HumanMessage

async def test_llm_direct():
    print("\n--- TESTING AZURE OPENAI CONNECTION ---")
    try:
        print("1. Getting LLM Object...")
        llm = get_llm()
        print(f"   Endpoint: {llm.azure_endpoint}")
        print(f"   Deployment/Model: {llm.deployment_name}")
        print(f"   API Version: {llm.openai_api_version}")

        print("\n2. Sending simple 'Hello' to Azure...")
        response = await llm.ainvoke([HumanMessage(content="Hello, are you working?")])
        
        print("\n✅ SUCCESS! Azure Response:")
        print(response.content)
        
    except Exception as e:
        print(f"\n❌ FAILED: {e}")
        print("\nTROUBLESHOOTING GUIDE:")
        print("1. Check CIRCUIT_LLM_API_ENDPOINT in properties.py")
        print("   - INCORRECT: https://my-resource.openai.azure.com/openai/deployments/...")
        print("   - CORRECT:   https://my-resource.openai.azure.com/")
        print("2. Check CIRCUIT_LLM_API_MODEL_NAME in properties.py")
        print("   - This must match the 'Deployment Name' in Azure AI Studio, NOT just the model name (e.g. 'gpt-4').")

if __name__ == "__main__":
    asyncio.run(test_llm_direct())