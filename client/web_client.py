import asyncio
import uvicorn
import os
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage
from llm import get_llm

# --- CONFIGURATION ---
MCP_SERVER_URL = "http://localhost:8012/sse"
PORT = 8000

# Global state for the agent
agent = None
mcp_client = None

# --- HTML TEMPLATE ---
HTML_TEMPLATE = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salesforce AI Agent</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
        .typing-dot {
            animation: typing 1.4s infinite ease-in-out both;
        }
        .typing-dot:nth-child(1) { animation-delay: -0.32s; }
        .typing-dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes typing {
            0%, 80%, 100% { transform: scale(0); }
            40% { transform: scale(1); }
        }
    </style>
</head>
<body class="bg-gray-100 h-screen flex flex-col font-sans">

    <!-- Header -->
    <header class="bg-blue-600 text-white p-4 shadow-md flex justify-between items-center">
        <h1 class="text-xl font-bold flex items-center gap-2">
            ☁️ Salesforce MCP Agent
        </h1>
        <span id="status" class="text-xs bg-blue-800 px-2 py-1 rounded-full animate-pulse">Connecting...</span>
    </header>

    <!-- Chat Container -->
    <main id="chat-container" class="flex-1 overflow-y-auto p-4 space-y-4 scroll-smooth">
        <!-- Welcome Message -->
        <div class="flex justify-start">
            <div class="bg-white text-gray-800 p-3 rounded-lg rounded-tl-none shadow-sm max-w-[80%] border border-gray-200">
                <p>Hello! I am your Salesforce Assistant. I can query records, describe objects, and help you manage your data. What would you like to know?</p>
            </div>
        </div>
    </main>

    <!-- Input Area -->
    <footer class="bg-white p-4 border-t border-gray-200">
        <div class="max-w-4xl mx-auto relative">
            <form id="chat-form" class="flex gap-2">
                <input type="text" id="user-input" 
                    class="flex-1 border border-gray-300 rounded-full px-4 py-3 focus:outline-none focus:border-blue-500 focus:ring-1 focus:ring-blue-500 shadow-sm"
                    placeholder="Ask about accounts, leads, or schemas..." required autocomplete="off">
                <button type="submit" 
                    class="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-full font-semibold shadow-sm transition-colors disabled:bg-gray-400">
                    Send
                </button>
            </form>
        </div>
    </footer>

    <script>
        const chatContainer = document.getElementById('chat-container');
        const chatForm = document.getElementById('chat-form');
        const userInput = document.getElementById('user-input');
        const statusBadge = document.getElementById('status');
        let isProcessing = false;

        // Auto-scroll to bottom
        function scrollToBottom() {
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        // Add Message to UI
        function addMessage(text, isUser, isTool = false) {
            const div = document.createElement('div');
            div.className = `flex ${isUser ? 'justify-end' : 'justify-start'}`;
            
            const bubble = document.createElement('div');
            const baseStyle = "p-3 rounded-lg shadow-sm max-w-[80%] border text-sm ";
            
            if (isUser) {
                bubble.className = baseStyle + "bg-blue-600 text-white rounded-tr-none border-blue-700";
            } else if (isTool) {
                bubble.className = baseStyle + "bg-gray-50 text-gray-600 font-mono text-xs border-gray-200 whitespace-pre-wrap border-l-4 border-l-orange-400";
            } else {
                bubble.className = baseStyle + "bg-white text-gray-800 rounded-tl-none border-gray-200";
            }
            
            bubble.innerText = text;
            div.appendChild(bubble);
            chatContainer.appendChild(div);
            scrollToBottom();
        }

        // Show Typing Indicator
        function showTyping() {
            const div = document.createElement('div');
            div.id = 'typing-indicator';
            div.className = 'flex justify-start';
            div.innerHTML = `
                <div class="bg-white p-4 rounded-lg rounded-tl-none shadow-sm border border-gray-200 flex gap-1">
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                    <div class="typing-dot w-2 h-2 bg-gray-400 rounded-full"></div>
                </div>
            `;
            chatContainer.appendChild(div);
            scrollToBottom();
        }

        function removeTyping() {
            const el = document.getElementById('typing-indicator');
            if (el) el.remove();
        }

        // Handle Form Submit
        chatForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const message = userInput.value.trim();
            if (!message || isProcessing) return;

            addMessage(message, true);
            userInput.value = '';
            isProcessing = true;
            showTyping();

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message })
                });

                if (!response.ok) throw new Error("Server Error");

                const reader = response.body.getReader();
                const decoder = new TextDecoder();

                removeTyping();

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
                                    addMessage(`🛠️ Tool Used: ${data.name}\nOutput: ${data.content.substring(0, 150)}...`, false, true);
                                } else if (data.type === 'answer') {
                                    addMessage(data.content, false);
                                }
                            } catch (e) { console.error("Parse error", e); }
                        }
                    }
                }
            } catch (error) {
                removeTyping();
                addMessage("❌ Error: " + error.message, false);
            } finally {
                isProcessing = false;
            }
        });

        // Initial Health Check
        fetch('/health').then(r => {
            if(r.ok) {
                statusBadge.innerText = "Connected";
                statusBadge.classList.remove("bg-blue-800", "animate-pulse");
                statusBadge.classList.add("bg-green-500");
            } else {
                statusBadge.innerText = "Offline";
                statusBadge.classList.add("bg-red-500");
            }
        }).catch(() => {
             statusBadge.innerText = "Offline";
             statusBadge.classList.add("bg-red-500");
        });

    </script>
</body>
</html>
"""

# --- BACKEND LOGIC ---

async def startup():
    """Initialize the Agent connection on startup."""
    global mcp_client, agent
    print("--- WEB CLIENT STARTING ---")
    
    try:
        # 1. Initialize LLM
        llm = get_llm()
        print("✅ LLM Initialized")

        # 2. Connect to MCP Server
        mcp_client = MultiServerMCPClient({
            "salesforce": {
                "transport": "sse",
                "url": MCP_SERVER_URL
            }
        })
        print(f"🔌 Connecting to MCP at {MCP_SERVER_URL}...")
        
        mcp_tools = await mcp_client.get_tools()
        print(f"✅ MCP Connected. Found {len(mcp_tools)} tools.")

        # 3. Create Agent
        agent = create_react_agent(llm, mcp_tools)
        print("🚀 Agent Ready!")

    except Exception as e:
        print(f"❌ CRITICAL STARTUP ERROR: {e}")
        # We don't exit, so the UI can still show the error state

async def homepage(request):
    return HTMLResponse(HTML_TEMPLATE)

async def health(request):
    if agent:
        return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error"}, status_code=503)

async def chat_endpoint(request):
    if not agent:
        return JSONResponse({"error": "Agent not initialized. Check console logs."}, status_code=500)

    data = await request.json()
    user_message = data.get("message")

    async def event_stream():
        try:
            # Stream the agent's thinking process
            async for chunk in agent.astream(
                {"messages": [HumanMessage(content=user_message)]},
                stream_mode="updates"
            ):
                for node, values in chunk.items():
                    # Handle Tool Outputs (intermediate steps)
                    for msg in values["messages"]:
                        if hasattr(msg, 'tool_call_id'):
                            # Send tool output to UI
                            payload = {
                                "type": "tool",
                                "name": msg.name,
                                "content": str(msg.content)
                            }
                            yield f"data: {json.dumps(payload)}\n\n"
                        
                        # Handle Final Answer
                        elif hasattr(msg, 'content') and msg.content and node == "agent":
                             # Some nodes are intermediate thoughts, we want the final response
                             # In LangGraph, typically the last agent message is the answer,
                             # but we can stream partials if we want. 
                             # For simplicity, we send agent messages as answers.
                             payload = {
                                 "type": "answer",
                                 "content": msg.content
                             }
                             yield f"data: {json.dumps(payload)}\n\n"

        except Exception as e:
            yield f"data: {json.dumps({'type': 'answer', 'content': f'Error: {str(e)}'})}\n\n"

    return HTMLResponse(event_stream(), media_type='text/event-stream')

# --- APP DEFINITION ---
app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/chat", chat_endpoint, methods=["POST"]),
        Route("/health", health),
    ],
    middleware=[
        Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])
    ],
    on_startup=[startup]
)

if __name__ == "__main__":
    # Run on a different port than the MCP server
    uvicorn.run(app, host="0.0.0.0", port=PORT)