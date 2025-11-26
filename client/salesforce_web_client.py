import asyncio
import uvicorn
import json
import traceback
import httpx
import os
import sys
import uuid
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add project root to path to find 'app' module
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

# Import directly from llm (since we are in the same dir)
try:
    from llm import get_llm
except ImportError:
    # Fallback if running as a module from root
    from client.llm import get_llm

from langgraph.checkpoint.memory import MemorySaver

# Import OrgManager to expose list to UI via API
from app.org_manager import org_manager

# --- CONFIGURATION ---
MCP_SERVER_URL = "http://localhost:8012/sse"
WEB_PORT = 8081

# Global state
agent = None
mcp_client = None

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = SystemMessage(content="""
You are a helpful Salesforce Assistant.

1. **Managing Orgs**: You can add orgs and switch default orgs. If a user provides credentials, use `add_salesforce_org`.

2. **Comparing Metadata**: 
   - If asked to compare metadata, you MUST use `fetch_metadata_source` for BOTH orgs mentioned.
   - Do not stop after fetching. You must compare the code returned by the tools.
   - **FORMATTING**: Use Markdown Code Blocks for the diffs.
   - Provide a summary of changes (e.g., "Line 10 changed from X to Y").

3. **General**: If the user says "Find records", ask specific questions.

Always be concise and professional.
""")

# --- HTML TEMPLATE ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Salesforce Assistant</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/themes/prism-tomorrow.min.css" rel="stylesheet" />
    <script src="https://cdnjs.cloudflare.com/ajax/libs/prism/1.29.0/prism.min.js"></script>
    <style>
        .dot { animation: jump 1.4s infinite ease-in-out both; }
        .dot:nth-child(1) { animation-delay: -0.32s; }
        .dot:nth-child(2) { animation-delay: -0.16s; }
        @keyframes jump { 0%, 80%, 100% { transform: scale(0); } 40% { transform: scale(1); } }
        .fade-in { animation: fadeIn 0.5s ease-in; }
        
        /* Markdown/Diff Styles */
        pre { background: #1e1e1e; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; color: #d4d4d4; }
        code { font-family: 'Consolas', 'Monaco', monospace; font-size: 0.85rem; }
        .markdown-body ul { list-style-type: disc; margin-left: 1.5rem; margin-top: 0.5rem; }
        .markdown-body ol { list-style-type: decimal; margin-left: 1.5rem; margin-top: 0.5rem; }
        .markdown-body p { margin-bottom: 0.5rem; }
    </style>
</head>
<body class="bg-slate-50 h-screen flex flex-col font-sans text-slate-800">

    <header class="bg-white border-b border-slate-200 p-4 flex justify-between items-center shadow-sm z-10">
        <div class="flex items-center gap-3">
            <button onclick="window.location.reload()" class="p-2 text-slate-500 hover:bg-slate-100 hover:text-blue-600 rounded-lg transition-colors" title="Reset Session">
                <i data-lucide="refresh-cw" class="w-5 h-5"></i>
            </button>
            <div class="flex items-center gap-2 border-l border-slate-200 pl-3">
                <div class="bg-blue-600 p-1.5 rounded-lg">
                    <i data-lucide="cloud" class="text-white w-5 h-5"></i>
                </div>
                <h1 class="text-lg font-bold text-slate-800">Salesforce Assistant</h1>
            </div>
        </div>

        <div class="flex items-center gap-4">
             <div class="flex items-center gap-2">
                <label class="text-xs font-semibold text-slate-500 uppercase">Default Org:</label>
                <select id="header-org-select" onchange="changeDefaultOrg(this.value)" class="bg-slate-100 border-none text-sm rounded-lg p-1.5 focus:ring-2 focus:ring-blue-500">
                    </select>
                <button onclick="toggleAddOrgModal()" class="text-blue-600 hover:text-blue-800 text-sm font-medium underline pl-1">
                    + Add
                </button>
            </div>
            
            <div id="status" class="flex items-center gap-2 px-3 py-1 bg-yellow-100 text-yellow-700 rounded-full text-xs font-medium animate-pulse">
                <span class="w-2 h-2 rounded-full bg-yellow-500"></span> Connecting...
            </div>
        </div>
    </header>

    <main class="flex-1 overflow-y-auto p-4 relative">
        
        <div id="start-screen" class="max-w-4xl mx-auto mt-10 space-y-6 fade-in">
            <div class="text-center space-y-2">
                <h2 class="text-2xl font-bold text-slate-900">What would you like to do?</h2>
                <p class="text-slate-500">Manage data or compare metadata across environments.</p>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-3 gap-4">
                <button onclick="selectOption('find_records')" class="group bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-blue-500 transition-all text-left">
                    <div class="bg-blue-100 w-10 h-10 rounded-full flex items-center justify-center mb-4 group-hover:bg-blue-600 transition-colors">
                        <i data-lucide="search" class="text-blue-600 w-5 h-5 group-hover:text-white"></i>
                    </div>
                    <h3 class="font-semibold text-lg mb-1">Find Records</h3>
                    <p class="text-sm text-slate-500">Query Accounts, Contacts using natural language.</p>
                </button>

                <button onclick="selectOption('retrieve_metadata')" class="group bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-purple-500 transition-all text-left">
                    <div class="bg-purple-100 w-10 h-10 rounded-full flex items-center justify-center mb-4 group-hover:bg-purple-600 transition-colors">
                        <i data-lucide="code" class="text-purple-600 w-5 h-5 group-hover:text-white"></i>
                    </div>
                    <h3 class="font-semibold text-lg mb-1">Retrieve Metadata</h3>
                    <p class="text-sm text-slate-500">View details of Apex classes, Triggers, Flows.</p>
                </button>

                <button onclick="selectOption('compare_metadata')" class="group bg-white p-6 rounded-2xl border border-slate-200 shadow-sm hover:shadow-md hover:border-orange-500 transition-all text-left">
                    <div class="bg-orange-100 w-10 h-10 rounded-full flex items-center justify-center mb-4 group-hover:bg-orange-600 transition-colors">
                        <i data-lucide="git-compare" class="text-orange-600 w-5 h-5 group-hover:text-white"></i>
                    </div>
                    <h3 class="font-semibold text-lg mb-1">Compare Metadata</h3>
                    <p class="text-sm text-slate-500">Diff Code/Config between two Salesforce Orgs.</p>
                </button>
            </div>
        </div>

        <div id="compare-form" class="hidden max-w-xl mx-auto mt-10 bg-white p-8 rounded-2xl border border-slate-200 shadow-lg fade-in">
            <div class="flex items-center gap-2 mb-6">
                <button onclick="showStartScreen()" class="text-slate-400 hover:text-slate-600"><i data-lucide="arrow-left"></i></button>
                <h2 class="text-xl font-bold">Compare Metadata</h2>
            </div>

            <div class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Metadata Type</label>
                    <select id="comp-type" class="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg">
                        <option value="ApexClass">Apex Class</option>
                        <option value="ApexTrigger">Apex Trigger</option>
                        <option value="ApexPage">Visualforce Page</option>
                        <option value="ApexComponent">Apex Component</option>
                    </select>
                </div>

                <div class="grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Source Org (Left)</label>
                        <select id="comp-org-a" class="org-dropdown w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg"></select>
                    </div>
                    <div>
                        <label class="block text-sm font-medium text-slate-700 mb-1">Target Org (Right)</label>
                        <select id="comp-org-b" class="org-dropdown w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg"></select>
                    </div>
                </div>

                <div>
                    <label class="block text-sm font-medium text-slate-700 mb-1">Component Name (Exact API Name)</label>
                    <input type="text" id="comp-name" placeholder="e.g. AccountController" class="w-full p-2.5 bg-slate-50 border border-slate-300 rounded-lg focus:ring-2 focus:ring-orange-500 outline-none">
                </div>

                <button onclick="submitComparison()" class="w-full bg-orange-600 hover:bg-orange-700 text-white font-medium py-3 rounded-xl transition-colors">
                    Run Comparison
                </button>
            </div>
        </div>
        
        <div id="add-org-modal" class="hidden fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
            <div class="bg-white p-6 rounded-2xl w-96 shadow-2xl">
                <h3 class="text-lg font-bold mb-4">Add New Org Connection</h3>
                <div class="space-y-3">
                    <input id="new-alias" type="text" placeholder="Alias (e.g. UAT)" class="w-full p-2 border rounded">
                    <input id="new-user" type="text" placeholder="Username" class="w-full p-2 border rounded">
                    <input id="new-pass" type="password" placeholder="Password" class="w-full p-2 border rounded">
                    <input id="new-token" type="password" placeholder="Security Token" class="w-full p-2 border rounded">
                    <div class="flex items-center gap-2">
                        <input id="new-sandbox" type="checkbox" class="w-4 h-4">
                        <label class="text-sm">Is Sandbox?</label>
                    </div>
                    <div class="flex gap-2 mt-4">
                        <button onclick="toggleAddOrgModal()" class="flex-1 py-2 bg-slate-200 rounded hover:bg-slate-300">Cancel</button>
                        <button onclick="saveNewOrg()" class="flex-1 py-2 bg-blue-600 text-white rounded hover:bg-blue-700">Save</button>
                    </div>
                </div>
            </div>
        </div>

        <div id="chat-container" class="hidden max-w-5xl mx-auto space-y-4 pb-24"></div>

    </main>

    <footer id="input-area" class="hidden bg-white border-t border-slate-200 p-4 fixed bottom-0 w-full z-10">
        <form id="chat-form" class="max-w-5xl mx-auto flex gap-3">
            <button type="button" onclick="window.location.reload()" class="p-3 text-slate-400 hover:text-slate-600" title="Reset Session">
                <i data-lucide="refresh-cw" class="w-5 h-5"></i>
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
        
        // --- Session Management ---
        const sessionId = "session_" + Math.random().toString(36).substring(7);
        console.log("Current Session ID:", sessionId);

        const startScreen = document.getElementById('start-screen');
        const compareForm = document.getElementById('compare-form');
        const chatContainer = document.getElementById('chat-container');
        const inputArea = document.getElementById('input-area');
        const userInput = document.getElementById('user-input');
        const statusBadge = document.getElementById('status');
        const addOrgModal = document.getElementById('add-org-modal');
        let isProcessing = false;

        function selectOption(option) {
            startScreen.classList.add('hidden');
            if (option === 'find_records') showChat("I want to find records.");
            else if (option === 'retrieve_metadata') showChat("I want to retrieve metadata.");
            else if (option === 'compare_metadata') {
                compareForm.classList.remove('hidden');
                populateOrgDropdowns();
            }
        }

        function showStartScreen() {
            compareForm.classList.add('hidden');
            chatContainer.classList.add('hidden');
            inputArea.classList.add('hidden');
            startScreen.classList.remove('hidden');
            chatContainer.innerHTML = ''; 
        }

        function showChat(initialPrompt) {
            chatContainer.classList.remove('hidden');
            inputArea.classList.remove('hidden');
            compareForm.classList.add('hidden');
            if(initialPrompt) sendMessage(initialPrompt, true);
        }
        
        function toggleAddOrgModal() { addOrgModal.classList.toggle('hidden'); }

        async function fetchOrgs() {
            try {
                const r = await fetch('/api/orgs');
                return await r.json();
            } catch(e) { console.error(e); return {orgs:[], default:""}; }
        }

        async function populateOrgDropdowns() {
            const data = await fetchOrgs();
            const options = data.orgs.map(o => `<option value="${o}">${o}</option>`).join('');
            document.getElementById('header-org-select').innerHTML = options;
            document.getElementById('header-org-select').value = data.default;
            document.querySelectorAll('.org-dropdown').forEach(s => s.innerHTML = options);
            if(data.orgs.length > 1) document.getElementById('comp-org-b').selectedIndex = 1;
        }
        
        async function changeDefaultOrg(newAlias) {
             sendMessage(`Switch the default org to ${newAlias}`, true);
        }

        async function saveNewOrg() {
            const alias = document.getElementById('new-alias').value;
            const user = document.getElementById('new-user').value;
            const pass = document.getElementById('new-pass').value;
            const token = document.getElementById('new-token').value;
            const isSand = document.getElementById('new-sandbox').checked;
            if(!alias || !user || !pass) return alert("Fill all fields");
            toggleAddOrgModal();
            const prompt = `Add a new salesforce org with alias '${alias}', username '${user}', password '${pass}', token '${token}' and domain '${isSand ? 'test' : ''}'.`;
            await sendMessage(prompt, true); 
            await populateOrgDropdowns();
        }

        function submitComparison() {
            const type = document.getElementById('comp-type').value;
            const orgA = document.getElementById('comp-org-a').value;
            const orgB = document.getElementById('comp-org-b').value;
            const name = document.getElementById('comp-name').value;
            if (!name) return alert("Please enter a component name.");
            
            const prompt = `Compare the metadata for ${type} named '${name}' between org '${orgA}' and org '${orgB}'. Fetch the source code from both and provide a side-by-side comparison summary.`;
            showChat();
            sendMessage(prompt, false);
        }

        function addMessage(text, type) {
            const div = document.createElement('div');
            div.className = `flex ${type === 'user' ? 'justify-end' : 'justify-start'} fade-in`;
            const bubble = document.createElement('div');
            const base = "p-4 rounded-2xl shadow-sm max-w-[90%] text-sm leading-relaxed whitespace-pre-wrap ";
            
            if (type === 'user') bubble.className = base + "bg-blue-600 text-white rounded-tr-sm";
            else if (type === 'tool') bubble.className = base + "bg-slate-100 text-slate-600 font-mono text-xs border border-slate-200 overflow-x-auto max-h-60";
            else if (type === 'error') bubble.className = base + "bg-red-50 text-red-600 border border-red-100";
            else bubble.className = base + "bg-white border border-slate-200 text-slate-800 rounded-tl-sm markdown-body";
            
            bubble.innerText = text; 
            if (type === 'ai') {
                 let formatted = text
                    .replace(/```([\s\S]*?)```/g, '<pre><code>$1</code></pre>')
                    .replace(/`([^`]+)`/g, '<code class="bg-gray-100 px-1 rounded">$1</code>')
                    .replace(/\*\*([^*]+)\*\*/g, '<b>$1</b>')
                    .replace(/- ([^\n]+)/g, '<li>$1</li>'); 
                 bubble.innerHTML = formatted;
            }
            div.appendChild(bubble);
            chatContainer.appendChild(div);
            chatContainer.scrollTop = chatContainer.scrollHeight;
        }

        async function sendMessage(text, isHidden = false) {
            if (!text || isProcessing) return;
            isProcessing = true;
            if (!isHidden) { addMessage(text, 'user'); userInput.value = ''; }

            const typingId = 'typing-' + Date.now();
            const typingDiv = document.createElement('div');
            typingDiv.id = typingId;
            typingDiv.className = 'flex justify-start fade-in';
            typingDiv.innerHTML = `<div class="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-sm shadow-sm flex gap-1"><div class="dot w-2 h-2 bg-slate-400 rounded-full"></div><div class="dot w-2 h-2 bg-slate-400 rounded-full"></div><div class="dot w-2 h-2 bg-slate-400 rounded-full"></div></div>`;
            chatContainer.appendChild(typingDiv);
            chatContainer.scrollTop = chatContainer.scrollHeight;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: sessionId })
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                document.getElementById(typingId).remove();

                // FIX: Added Buffer for SSE Splitting
                let buffer = '';
                
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) break;
                    
                    // Decode and add to buffer
                    buffer += decoder.decode(value, {stream: true});
                    
                    // Split by double newline (SSE standard)
                    let parts = buffer.split('\n\n');
                    
                    // Keep the last part in buffer (it might be incomplete)
                    buffer = parts.pop();
                    
                    for (const part of parts) {
                        if (part.trim().startsWith('data: ')) {
                            try {
                                const jsonStr = part.trim().replace('data: ', '');
                                const data = JSON.parse(jsonStr);
                                if (data.type === 'tool') addMessage(`🔧 Tool Output (${data.name}):\n${data.content.substring(0, 200)}...`, 'tool');
                                else if (data.type === 'answer') addMessage(data.content, 'ai');
                                else if (data.type === 'error') addMessage(data.content, 'error');
                            } catch (e) { console.error("Parse error", e); }
                        }
                    }
                }
            } catch (e) {
                document.getElementById(typingId)?.remove();
                addMessage("Connection Error: " + e.message, 'error');
            } finally { isProcessing = false; }
        }

        document.getElementById('chat-form').addEventListener('submit', (e) => { e.preventDefault(); sendMessage(userInput.value.trim()); });
        populateOrgDropdowns();
        setInterval(async () => {
            try {
                const r = await fetch('/health');
                if (r.ok) { statusBadge.className = "flex items-center gap-2 px-3 py-1 bg-green-100 text-green-700 rounded-full text-xs font-medium"; statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-green-500"></span> Connected'; } 
                else throw new Error();
            } catch { statusBadge.className = "flex items-center gap-2 px-3 py-1 bg-red-100 text-red-700 rounded-full text-xs font-medium"; statusBadge.innerHTML = '<span class="w-2 h-2 rounded-full bg-red-500"></span> Offline'; }
        }, 5000);
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
        mcp_client = MultiServerMCPClient({
            "salesforce": {
                "transport": "sse",
                "url": MCP_SERVER_URL
            }
        })
        
        mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=5.0)
        print(f"   ✅ Connected! Found {len(mcp_tools)} tools.")

        memory = MemorySaver()
        
        # Create agent without deprecated modifiers
        agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
        print(f"🚀 WEB CLIENT READY! http://localhost:{WEB_PORT}")

    except Exception as e:
        print(f"\n❌ CRITICAL STARTUP ERROR: {e}")

async def homepage(request):
    return HTMLResponse(HTML_TEMPLATE)

async def get_orgs(request):
    return JSONResponse({
        "orgs": org_manager.list_orgs(),
        "default": org_manager.default_org
    })

async def health(request):
    if agent: return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error"}, status_code=503)

async def chat_endpoint(request):
    if not agent: return JSONResponse({"error": "Agent offline"}, status_code=503)

    data = await request.json()
    user_msg = data.get("message", "")
    # Use session_id from client to maintain separate conversations
    session_id = data.get("session_id", "default")
    config = {"configurable": {"thread_id": session_id}}

    async def generator():
        try:
            # Inject System Prompt if this is a new session
            state = await agent.aget_state(config)
            current_messages = state.values.get("messages", []) if state.values else []
            
            input_messages = [HumanMessage(content=user_msg)]
            if not current_messages:
                print(f"📝 Injecting System Prompt for new session: {session_id}")
                input_messages.insert(0, SYSTEM_PROMPT)

            async for chunk in agent.astream(
                {"messages": input_messages},
                config=config,
                stream_mode="updates"
            ):
                for node, values in chunk.items():
                    # Explicitly handle list of messages
                    msgs = values.get("messages", [])
                    # If it's a single message, wrap it
                    if not isinstance(msgs, list): msgs = [msgs]
                    
                    for msg in msgs:
                        # Debug Print
                        print(f"📨 Received Message Type: {type(msg).__name__}")
                        
                        if isinstance(msg, ToolMessage):
                            # This is the OUTPUT from the tool
                            print(f"   🔧 Tool Output: {str(msg.content)[:50]}...")
                            yield f"data: {json.dumps({'type': 'tool', 'name': msg.name or 'Tool', 'content': str(msg.content)})}\n\n"
                        
                        elif isinstance(msg, AIMessage):
                            # This is the ANSWER from the AI (or a tool call request)
                            if msg.tool_calls:
                                print(f"   🛠️  AI is calling tools: {len(msg.tool_calls)}")
                                # We don't necessarily need to show this to the user, 
                                # but we could show a 'Thinking...' state
                            elif msg.content:
                                print(f"   🤖 AI Answer: {str(msg.content)[:50]}...")
                                yield f"data: {json.dumps({'type': 'answer', 'content': str(msg.content)})}\n\n"
                                
        except Exception as e:
            print(f"❌ ERROR in Chat Stream: {e}")
            traceback.print_exc()
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type='text/event-stream')

app = Starlette(
    debug=True,
    routes=[
        Route("/", homepage),
        Route("/api/orgs", get_orgs),
        Route("/chat", chat_endpoint, methods=["POST"]),
        Route("/health", health),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])],
    on_startup=[startup]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)