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
from langchain_core.messages import HumanMessage
from llm import get_llm

# --- NEW IMPORT FOR MEMORY ---
from langgraph.checkpoint.memory import MemorySaver

# --- CONFIGURATION ---
MCP_SERVER_URL = "http://localhost:8000/sse"
WEB_PORT = 8080

# Global state
agent = None
mcp_client = None

# --- HTML TEMPLATE (Unchanged) ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salesforce Agent</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .dot { animation: jump 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes jump { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
    </style>
</head>
<body class="bg-gray-50 h-screen flex flex-col font-sans">

    <!-- Header -->
    <header class="bg-white border-b border-gray-200 p-4 flex justify-between items-center shadow-sm z-10">
        <div class="flex items-center gap-2">
            <span class="text-2xl">☁️</span>
            <h1 class="text-lg font-semibold text-gray-800">Salesforce Agent</h1>
        </div>
        <div id="status" class="flex items-center gap-2 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium animate-pulse">
            <span class="w-2 h-2 rounded-full bg-yellow-500"></span> Connecting...
        </div>
    </header>

    <!-- Chat Area -->
    <main id="chat-box" class="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth pb-24">
        <div class="flex justify-start">
            <div class="bg-white border border-gray-200 text-gray-800 p-3 rounded-2xl rounded-tl-none shadow-sm max-w-[85%]">
                <p>Hi! I'm connected to your Salesforce instance. Ask me to find records, describe objects, or run queries.</p>
            </div>
        </div>
    </main>

    <!-- Input Area -->
    <footer class="bg-white border-t border-gray-200 p-4 fixed bottom-0 w-full z-10">
        <form id="chat-form" class="max-w-4xl mx-auto flex gap-3">
            <input type="text" id="user-input" 
                class="flex-1 bg-gray-100 border-0 rounded-xl px-4 py-3 focus:ring-2 focus:ring-blue-500 focus:bg-white transition-all outline-none"
                placeholder="Type a message..." autocomplete="off">
            <button type="submit" 
                class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-xl font-medium transition-colors disabled:opacity-50 disabled:cursor-not-allowed">
                Send
            </button>
        </form>
    </footer>

    <script>
        const chatBox = document.getElementById('chat-box');
        const form = document.getElementById('chat-form');
        const input = document.getElementById('user-input');
        const status = document.getElementById('status');
        let isProcessing = false;

        function scrollToBottom() {
            chatBox.scrollTop = chatBox.scrollHeight;
        }

        function addBubble(text, type) {
            const div = document.createElement('div');
            div.className = `flex ${type === 'user' ? 'justify-end' : 'justify-start'}`;
            
            const bubble = document.createElement('div');
            const base = "p-3 rounded-2xl shadow-sm max-w-[85%] text-sm whitespace-pre-wrap ";
            
            if (type === 'user') {
                bubble.className = base + "bg-blue-600 text-white rounded-tr-none";
            } else if (type === 'tool') {
                bubble.className = base + "bg-gray-100 text-gray-600 font-mono text-xs border border-gray-200";
            } else { // ai
                bubble.className = base + "bg-white border border-gray-200 text-gray-800 rounded-tl-none";
            }
            
            bubble.innerText = text;
            div.appendChild(bubble);
            chatBox.appendChild(div);
            scrollToBottom();
        }

        function setStatus(state) {
            if (state === 'connected') {
                status.className = "flex items-center gap-2 px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium";
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500"></span> Connected';
            } else {
                status.className = "flex items-center gap-2 px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium";
                status.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> Disconnected';
            }
        }

        // Polling for health status
        setInterval(() => {
            fetch('/health').then(r => r.ok ? setStatus('connected') : setStatus('error'))
                            .catch(() => setStatus('error'));
        }, 5000);

        // Send Message
        form.addEventListener('submit', async (e) => {
            e.preventDefault();
            const msg = input.value.trim();
            if (!msg || isProcessing) return;

            addBubble(msg, 'user');
            input.value = '';
            isProcessing = true;

            const typingId = 'typing-' + Date.now();
            const typingDiv = document.createElement('div');
            typingDiv.id = typingId;
            typingDiv.className = 'flex justify-start';
            typingDiv.innerHTML = `
                <div class="bg-white border border-gray-200 p-4 rounded-2xl rounded-tl-none shadow-sm flex gap-1">
                    <div class="dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="dot w-2 h-2 bg-gray-400 rounded-full"></div>
                </div>`;
            chatBox.appendChild(typingDiv);
            scrollToBottom();

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: msg })
                });

                if (!response.ok) {
                    const errData = await response.json();
                    throw new Error(errData.error || "Server Error");
                }

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
                                if (data.type === 'tool') {
                                    addBubble(`🔧 Tool: ${data.name}\n${data.content.substring(0, 200)}...`, 'tool');
                                } else if (data.type === 'answer') {
                                    addBubble(data.content, 'ai');
                                } else if (data.type === 'error') {
                                    addBubble("❌ Error: " + data.content, 'tool');
                                }
                            } catch (e) { console.error(e); }
                        }
                    }
                }
            } catch (err) {
                document.getElementById(typingId)?.remove();
                addBubble("Network Error: " + err.message, 'tool');
            } finally {
                isProcessing = false;
            }
        });
    </script>
</body>
</html>
"""

# --- BACKEND ---

async def check_connection():
    print(f"🔎 Checking connection to {MCP_SERVER_URL}...")
    async with httpx.AsyncClient() as client:
        try:
            resp = await client.get(MCP_SERVER_URL, timeout=2.0)
            print("   ✅ Server is reachable.")
            return True
        except httpx.ConnectError:
            print("   ❌ Connection Refused: Server is NOT running on port 8012.")
            return False
        except Exception as e:
             print(f"   ⚠️ Warning: Connection check failed ({e}), but trying anyway.")
             return True

async def startup():
    global mcp_client, agent
    print("\n--- WEB CLIENT STARTING ---")
    
    if not await check_connection():
        print("❌ CRITICAL: Cannot connect to MCP Server.")
        return

    try:
        llm = get_llm()
        await llm.ainvoke([HumanMessage(content="Hi")])
        print("   ✅ LLM Ready")

        mcp_client = MultiServerMCPClient({
            "salesforce": {
                "transport": "sse",
                "url": MCP_SERVER_URL
            }
        })
        
        try:
            mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=5.0)
        except asyncio.TimeoutError:
            raise Exception(f"Connection timed out.")
            
        print(f"   ✅ Connected! Found {len(mcp_tools)} tools.")

        # --- ENABLE MEMORY ---
        memory = MemorySaver()
        agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
        # ---------------------
        
        print("🚀 AGENT READY! Go to http://localhost:8080")

    except Exception as e:
        print(f"\n❌ CRITICAL STARTUP ERROR: {e}")

async def homepage(request):
    return HTMLResponse(HTML_TEMPLATE)

async def health(request):
    if agent:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error"}, status_code=503)

async def chat_endpoint(request):
    if not agent:
        return JSONResponse({"error": "Agent offline"}, status_code=503)

    data = await request.json()
    user_msg = data.get("message", "")

    # Use a config to track the conversation thread
    config = {"configurable": {"thread_id": "web_user_1"}}

    async def generator():
        try:
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=user_msg)]},
                config=config,  # Pass the thread config here
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