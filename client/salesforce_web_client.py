import asyncio
import uvicorn
import json
import traceback
import httpx
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage
from llm import get_llm
from langgraph.checkpoint.memory import MemorySaver

# --- CONFIGURATION ---
MCP_SERVER_URL = "http://localhost:8000/sse"
WEB_PORT = 8081  # Running on a new port to avoid conflict

# Global state
agent = None
mcp_client = None

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salesforce Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        .dot { animation: jump 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes jump { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    </style>
</head>
<body class="bg-slate-50 h-screen flex flex-col font-sans text-slate-800">

    <!-- Header -->
    <header class="bg-white border-b border-slate-200 p-4 flex justify-between items-center shadow-sm z-10">
        <div class="flex items-center gap-3">
            <!-- Home Button -->
            <button onclick="showStartScreen()" class="p-2 text-slate-500 hover:bg-slate-100 hover:text-blue-600 rounded-lg transition-colors" title="Go Home">
                <i data-lucide="home" class="w-5 h-5"></i>
            </button>
            
            <div class="flex items-center gap-2 border-l border-slate-200 pl-3">
                <div class="bg-blue-600 p-1.5 rounded-lg">
                    <i data-lucide="cloud" class="text-white w-5 h-5"></i>
                </div>
                <h1 class="text-lg font-bold text-slate-800">Salesforce Assistant</h1>
            </div>
        </div>
        <div id="status" class="flex items-center gap-2 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium animate-pulse">
            <span class="w-2 h-2 rounded-full bg-yellow-500"></span> Connecting...
        </div>
    </header>

    <!-- Main Area -->
    <main class="flex-1 overflow-y-auto p-4 relative">
        
        <!-- Start Screen (Cards) -->
        <div id="start-screen" class="max-w-2xl mx-auto mt-10 space-y-6 fade-in">
            <div class="text-center space-y-2">
                <h2 class="text-2xl font-bold text-slate-900">What would you like to do?</h2>
                <p class="text-slate-500">Select an option to get started.</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-4">
                <!-- Option 1: Find Records -->
                <button onclick="selectOption('find_records')" class="group bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-500 transition-all text-left">
                    <div class="bg-blue-100 w-10 h-10 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-600 transition-colors">
                        <i data-lucide="search" class="text-blue-600 w-5 h-5 group-hover:text-white"></i>
                    </div>
                    <h3 class="font-semibold text-lg mb-1">Find Records</h3>
                    <p class="text-sm text-slate-500">Search for Accounts, Contacts, or run custom queries.</p>
                </button>

                <!-- Option 2: Retrieve Metadata -->
                <button onclick="selectOption('retrieve_metadata')" class="group bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-purple-500 transition-all text-left">
                    <div class="bg-purple-100 w-10 h-10 rounded-full flex items-center justify-center mb-4 group-hover:bg-purple-600 transition-colors">
                        <i data-lucide="code" class="text-purple-600 w-5 h-5 group-hover:text-white"></i>
                    </div>
                    <h3 class="font-semibold text-lg mb-1">Retrieve Metadata</h3>
                    <p class="text-sm text-slate-500">View Apex classes, LWC bundles, Flows, and more.</p>
                </button>
            </div>
        </div>

        <!-- Metadata Sub-Options (Hidden by default) -->
        <div id="metadata-options" class="hidden max-w-2xl mx-auto mt-10 space-y-6 fade-in">
            <div class="flex items-center gap-2 mb-4">
                <button onclick="showStartScreen()" class="text-slate-400 hover:text-slate-600"><i data-lucide="arrow-left"></i> Back</button>
                <h2 class="text-xl font-bold">Select Metadata Type</h2>
            </div>
            
            <div class="grid grid-cols-2 md:grid-cols-3 gap-3">
                <button onclick="sendMetadataPrompt('ApexClass')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">Apex Class</button>
                <button onclick="sendMetadataPrompt('Flow')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">Flow</button>
                <button onclick="sendMetadataPrompt('ValidationRule')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">Validation Rule</button>
                <button onclick="sendMetadataPrompt('LightningComponentBundle')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">LWC</button>
                <button onclick="sendMetadataPrompt('Layout')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">Layout</button>
                <button onclick="sendMetadataPrompt('FlexiPage')" class="bg-white p-4 rounded-xl border hover:border-purple-500 hover:shadow-sm text-left text-sm font-medium">Lightning Page</button>
            </div>
        </div>

        <!-- Chat View (Hidden by default) -->
        <div id="chat-container" class="hidden max-w-3xl mx-auto space-y-4 pb-24">
            <!-- Messages will appear here -->
        </div>

    </main>

    <!-- Input Area (Hidden on start screen) -->
    <footer id="input-area" class="hidden bg-white border-t border-slate-200 p-4 fixed bottom-0 w-full z-10">
        <form id="chat-form" class="max-w-3xl mx-auto flex gap-3">
            <button type="button" onclick="resetFlow()" class="p-3 text-slate-400 hover:text-slate-600" title="Clear Chat">
                <i data-lucide="eraser" class="w-5 h-5"></i>
            </button>
            <input type="text" id="user-input" 
                class="flex-1 bg-slate-100 border-0 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all outline-none"
                placeholder="Type a message..." autocomplete="off">
            <button type="submit" 
                class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-medium transition-colors shadow-sm disabled:opacity-50">
                <i data-lucide="send" class="w-5 h-5"></i>
            </button>
        </form>
    </footer>

    <script>
        lucide.createIcons();
        
        const startScreen = document.getElementById('start-screen');
        const metadataOptions = document.getElementById('metadata-options');
        const chatContainer = document.getElementById('chat-container');
        const inputArea = document.getElementById('input-area');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');
        const statusBadge = document.getElementById('status');
        let isProcessing = false;

        // --- UI LOGIC ---

        function selectOption(option) {
            startScreen.classList.add('hidden');
            
            if (option === 'find_records') {
                showChat("I want to find records. Please ask me what I am looking for.");
            } else if (option === 'retrieve_metadata') {
                metadataOptions.classList.remove('hidden');
            }
        }

        function showStartScreen() {
            metadataOptions.classList.add('hidden');
            chatContainer.classList.add('hidden');
            inputArea.classList.add('hidden');
            startScreen.classList.remove('hidden');
            chatContainer.innerHTML = ''; // Clear chat
        }

        function resetFlow() {
            // This clears the chat visual only. 
            // In a real app, you might send a signal to the backend to clear memory.
            chatContainer.innerHTML = '';
            showChat("Chat cleared. How can I help?");
        }

        function sendMetadataPrompt(type) {
            metadataOptions.classList.add('hidden');
            showChat(`I want to retrieve metadata of type '${type}'. Please ask me for the name or specific details.`);
        }

        function showChat(initialSystemPrompt) {
            chatContainer.classList.remove('hidden');
            inputArea.classList.remove('hidden');
            
            // Send invisible prompt to jumpstart the agent
            sendMessage(initialSystemPrompt, true); 
        }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `flex ${type === 'user' ? 'justify-end' : 'justify-start'} fade-in`;
            
            const bubble = document.createElement('div');
            const base = "p-4 rounded-2xl shadow-sm max-w-[85%] text-sm leading-relaxed whitespace-pre-wrap ";
            
            if (type === 'user') {
                bubble.className = base + "bg-blue-600 text-white rounded-tr-sm";
            } else if (type === 'tool') {
                bubble.className = base + "bg-slate-100 text-slate-600 font-mono text-xs border border-slate-200 overflow-x-auto";
            } else if (type === 'error') {
                bubble.className = base + "bg-red-50 text-red-600 border border-red-100";
            } else { 
                bubble.className = base + "bg-white border border-slate-200 text-slate-800 rounded-tl-sm";
            }
            
            bubble.innerText = text;
            div.appendChild(bubble);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        async function sendMessage(text, isHidden = false) {
            if (!text || isProcessing) return;
            isProcessing = true;

            if (!isHidden) {
                addMessage(text, 'user');
                userInput.value = '';
            }

            // Typing Indicator
            const typingId = 'typing-' + Date.now();
            const typingDiv = document.createElement('div');
            typingDiv.id = typingId;
            typingDiv.className = 'flex justify-start fade-in';
            typingDiv.innerHTML = `
                <div class="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-sm shadow-sm flex gap-1">
                    <div class="dot w-2 h-2 bg-slate-400 rounded-full"></div>
                    <div class="dot w-2 h-2 bg-slate-400 rounded-full"></div>
                    <div class="dot w-2 h-2 bg-slate-400 rounded-full"></div>
                </div>`;
            chatContainer.appendChild(typingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });

                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                document.getElementById(typingId).remove();

                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    const chunk = decoder.decode(value);
                    const lines = chunk.split('\\n\\n');
                    
                    for (const line of lines) {
                        if (line.startsWith('data: ')) {
                            try {
                                const data = JSON.parse(line.replace('data: ', ''));
                                if (data.type === 'tool') addMessage(`🔧 Used Tool: ${data.name}`, 'tool');
                                else if (data.type === 'answer') addMessage(data.content, 'ai');
                                else if (data.type === 'error') addMessage(data.content, 'error');
                            } catch (e) {}
                        }
                    }
                }
            } catch (e) {
                document.getElementById(typingId)?.remove();
                addMessage("Connection Error: " + e.message, 'error');
            } finally {
                isProcessing = false;
            }
        }

        chatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendMessage(userInput.value.trim());
        });

        // --- INITIALIZATION ---
        async function checkHealth() {
            try {
                const r = await fetch('/health');
                if (r.ok) {
                    statusBadge.className = "flex items-center gap-2 px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium";
                    statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500"></span> Connected';
                } else {
                    throw new Error();
                }
            } catch {
                statusBadge.className = "flex items-center gap-2 px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium";
                statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> Offline';
            }
        }
        setInterval(checkHealth, 5000);
        checkHealth();

    </script>
</body>
</html>
"""

# --- BACKEND LOGIC ---

async def check_connection():
    print(f"🔎 Checking connection to {MCP_SERVER_URL}...")
    async with httpx.AsyncClient() as client:
        try:
            await client.get(MCP_SERVER_URL, timeout=2.0)
            print("   ✅ Server is reachable.")
            return True
        except httpx.ConnectError:
            print("   ❌ Connection Refused: Server is NOT running on port 8012.")
            return False
        except Exception: return True

async def startup():
    global mcp_client, agent
    print("\n--- SALESFORCE WEB CLIENT STARTING ---")
    
    if not await check_connection():
        print("❌ CRITICAL: Cannot connect to MCP Server on Port 8012.")
        return

    try:
        llm = get_llm()
        # System prompt to enforce behavior
        system_prompt = SystemMessage(content="""
        You are a helpful Salesforce Assistant.
        
        If the user says "I want to find records", ask them specifically what they are looking for (e.g., Account Name, Contact Email).
        
        If the user says "I want to retrieve metadata of type X", ask them for the specific name of the component (e.g., "What is the name of the Apex Class?"). 
        If they want to see ALL components of that type, tell them you can list them.
        
        Always be concise and professional.
        """)
        
        mcp_client = MultiServerMCPClient({
            "salesforce": {
                "transport": "sse",
                "url": MCP_SERVER_URL
            }
        })
        
        mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=5.0)
        print(f"   ✅ Connected! Found {len(mcp_tools)} tools.")

        memory = MemorySaver()
        # Pass system prompt as the first message in state if possible, or handle via logic
        agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
        print(f"🚀 WEB CLIENT READY! http://localhost:{WEB_PORT}")

    except Exception as e:
        print(f"\n❌ CRITICAL STARTUP ERROR: {e}")

async def homepage(request):
    return HTMLResponse(HTML_TEMPLATE)

async def health(request):
    if agent: return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error"}, status_code=503)

async def chat_endpoint(request):
    if not agent:
        return JSONResponse({"error": "Agent offline"}, status_code=503)

    data = await request.json()
    user_msg = data.get("message", "")
    
    # Use a static thread_id for simplicity in this demo
    # In a real app, you'd generate this per user session
    config = {"configurable": {"thread_id": "web_session_v1"}}

    async def generator():
        try:
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=user_msg)]},
                config=config,
                stream_mode="updates"
            ):
                for node, values in chunk.items():
                    for msg in values["messages"]:
                        if hasattr(msg, 'tool_call_id'):
                            yield f"data: {json.dumps({'type': 'tool', 'name': msg.name, 'content': str(msg.content)})}\n\n"
                        elif hasattr(msg, 'content') and msg.content:
                             yield f"data: {json.dumps({'type': 'answer', 'content': msg.content})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type='text/event-stream')

app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/chat", chat_endpoint, methods=["POST"]),
        Route("/health", health),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])],
    on_startup=[startup]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)