import asyncio
import uvicorn
import json
import traceback
import httpx
import os
import sys
from starlette.applications import Starlette
from starlette.responses import HTMLResponse, JSONResponse, StreamingResponse
from starlette.routing import Route
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

# Add project root to path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if project_root not in sys.path:
    sys.path.insert(0, project_root)

from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage

try:
    from client.llm import get_llm
except ImportError:
    from llm import get_llm

from langgraph.checkpoint.memory import MemorySaver

# --- CONFIGURATION ---
SALESFORCE_SERVER_URL = "http://localhost:8014/sse"
CONFLUENCE_SERVER_URL = "http://localhost:8013/sse"
WEB_PORT = 8085

agent = None
mcp_client = None

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = SystemMessage(content="""
You are an Intelligent Support Engineer. Your goal is to resolve Salesforce Cases using Confluence Documentation.

### 🧠 RESOLUTION WORKFLOW:

1. **FETCH CASE**: Use `execute_soql_query` to get Case details.
2. **SEARCH**: Use `search_documentation` based on the Case Subject/Description.
3. **RESOLVE**: Use `read_page_content` to get the solution.

### 📝 OUTPUT FORMAT (Strictly follow this order):

**1. CASE DETAILS**
Start your response immediately with a Markdown summary of the case:
> **Case #**: [Number]
> **Subject**: [Subject]
> **Priority**: [Priority]
> **Description**: [Short Description]

**2. RESOLUTION (Documentation)**
Present the solution found in Confluence.
- **CRITICAL**: You MUST wrap the Confluence HTML content in `<article>` tags.
- Example: `<article><h1>Page Title</h1><p>Steps...</p></article>`
- Do not wrap this in markdown code blocks.

**3. SOURCE**
End your response with the source link provided by the tool:
**Source:** [Page Title](URL)

### 🛡️ RULES:
- If no case is found, state that clearly.
- If no documentation is found, provide the Case Details but state no resolution was found.
""")

# --- HTML TEMPLATE ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Support Omni-Agent</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>
    <style>
        .fade-in { animation: fadeIn 0.3s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Markdown Styles */
        .prose p { margin-bottom: 0.5rem; }
        .prose ul { list-style-type: disc; margin-left: 1.5rem; }
        .prose blockquote { border-left: 4px solid #6366f1; background-color: #f8fafc; padding: 1rem; border-radius: 0 0.5rem 0.5rem 0; margin-bottom: 1rem; }
        .prose strong { color: #1e293b; }
        .prose a { color: #2563eb; text-decoration: underline; font-weight: 600; }

        /* Confluence Styles */
        .wiki-content { font-family: -apple-system, sans-serif; color: #172b4d; font-size: 0.95rem; }
        .wiki-content h1 { font-size: 1.5em; font-weight: 700; margin-top: 0; margin-bottom: 0.5em; color: #1e293b; }
        .wiki-content h2 { font-size: 1.25em; font-weight: 600; margin-top: 1em; border-bottom: 1px solid #e2e8f0; }
        .wiki-content ul { list-style-type: disc; padding-left: 1.5em; margin-bottom: 1em; }
        .wiki-content img { max-width: 100%; border-radius: 4px; border: 1px solid #e2e8f0; }
    </style>
</head>
<body class="bg-slate-50 h-screen flex flex-col font-sans text-slate-800">
    <header class="bg-white border-b border-slate-200 p-4 flex justify-between items-center shadow-sm z-10">
        <div class="flex items-center gap-3">
            <div class="flex items-center gap-2 border-r border-slate-200 pr-4">
                <div class="bg-indigo-600 p-1.5 rounded-lg"><i data-lucide="bot" class="text-white w-5 h-5"></i></div>
                <h1 class="text-lg font-bold text-slate-800">Support Omni-Agent</h1>
            </div>
            <div class="flex gap-2 text-xs font-medium text-slate-500">
                <span class="flex items-center gap-1"><i data-lucide="cloud" class="w-3 h-3"></i> Salesforce</span>
                <span class="text-slate-300">|</span>
                <span class="flex items-center gap-1"><i data-lucide="book" class="w-3 h-3"></i> Confluence</span>
            </div>
        </div>
        <button onclick="window.location.reload()" class="p-2 text-slate-400 hover:bg-slate-100 rounded-lg"><i data-lucide="refresh-cw" class="w-5 h-5"></i></button>
    </header>

    <main class="flex-1 overflow-y-auto p-4 relative" id="chat-container">
        <div id="welcome-screen" class="max-w-2xl mx-auto mt-20 text-center space-y-6 fade-in">
            <h2 class="text-3xl font-bold text-slate-900">Automated Case Resolution</h2>
            <p class="text-slate-500 text-lg">Enter a Salesforce Case Number. I will fetch details and find a resolution.</p>
            <div class="bg-white p-6 rounded-2xl border border-slate-200 shadow-sm max-w-md mx-auto">
                <label class="block text-left text-xs font-bold text-slate-500 uppercase mb-2">Quick Resolve</label>
                <div class="flex gap-2">
                    <input type="text" id="case-input" class="flex-1 border border-slate-300 rounded-lg px-3 py-2 focus:ring-2 focus:ring-indigo-500 outline-none" placeholder="Case # (e.g. 00001002)">
                    <button onclick="triggerCaseResolve()" class="bg-indigo-600 hover:bg-indigo-700 text-white px-4 py-2 rounded-lg font-medium transition-colors">Resolve</button>
                </div>
            </div>
        </div>
        <div id="messages" class="max-w-4xl mx-auto space-y-6 pb-24 hidden"></div>
    </main>

    <footer class="bg-white border-t border-slate-200 p-4 fixed bottom-0 w-full z-10">
        <form id="chat-form" class="max-w-4xl mx-auto flex gap-3">
            <input type="text" id="user-input" class="flex-1 bg-slate-100 border-0 rounded-xl px-4 py-3 focus:bg-white transition-all outline-none focus:ring-2 focus:ring-indigo-500" placeholder="Or ask a question..." autocomplete="off">
            <button type="submit" class="bg-slate-900 hover:bg-slate-800 text-white px-6 py-3 rounded-xl font-medium shadow-sm"><i data-lucide="send" class="w-5 h-5"></i></button>
        </form>
    </footer>

    <script>
        lucide.createIcons();
        const sessionId = "unified_" + Math.random().toString(36).substring(7);
        const welcomeScreen = document.getElementById('welcome-screen');
        const messagesDiv = document.getElementById('messages');
        const userInput = document.getElementById('user-input');
        let typingIndicatorElement = null;

        function triggerCaseResolve() {
            const caseNum = document.getElementById('case-input').value.trim();
            if(!caseNum) return;
            handleMessage(`I have a Salesforce Case with number '${caseNum}'. Fetch its details and find a resolution in Confluence. Additionally, use Case_Category__c, Component__c fields on the case as well to look for solution.`);
        }

        function showTyping(text="Thinking...") {
            if (typingIndicatorElement) {
                typingIndicatorElement.querySelector('span').innerText = text;
                return;
            }
            const div = document.createElement('div');
            div.id = "typing-indicator";
            div.className = 'flex justify-start fade-in';
            div.innerHTML = `<div class="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-3"><div class="flex gap-1"><div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"></div><div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div><div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div></div><span class="text-xs font-medium text-slate-500 uppercase tracking-wide">${text}</span></div>`;
            messagesDiv.appendChild(div);
            messagesDiv.scrollIntoView({ behavior: "smooth", block: "end" });
            typingIndicatorElement = div;
        }

        function hideTyping() {
            if (typingIndicatorElement) { typingIndicatorElement.remove(); typingIndicatorElement = null; }
        }

        function addMessage(role, text, type='text') {
            if (role !== 'system') hideTyping();
            welcomeScreen.classList.add('hidden');
            messagesDiv.classList.remove('hidden');
            
            const div = document.createElement('div');
            div.className = `flex ${role === 'user' ? 'justify-end' : 'justify-start'} fade-in`;
            const bubble = document.createElement('div');
            const base = "p-4 rounded-2xl shadow-sm max-w-[90%] text-sm leading-relaxed ";
            
            if (role === 'user') {
                bubble.className = base + "bg-indigo-600 text-white rounded-tr-sm";
                bubble.innerText = text;
            } else if (type === 'tool') {
                bubble.className = base + "bg-slate-50 text-slate-500 font-mono text-xs border border-slate-200 w-full overflow-hidden";
                bubble.innerHTML = `<div class="flex items-center gap-2 mb-1"><i data-lucide="wrench" class="w-3 h-3"></i> <span class="font-bold">Tool Used</span></div><div class="truncate">${text}</div>`;
            } else {
                // HTML / MARKDOWN RENDERING
                if (text.includes('<article>')) {
                    bubble.className = base + "bg-white border border-slate-200 text-slate-800 rounded-tl-sm w-full";
                    const parts = text.split(/<article>|<\/article>/);
                    let html = "";
                    // Case Details
                    if(parts[0]) html += `<div class="prose mb-4">${marked.parse(parts[0])}</div>`;
                    // Documentation
                    if(parts[1]) {
                        let cleanHtml = parts[1].replace(/\\\\n/g, '').replace(/\\\\"/g, '"');
                        if(cleanHtml.includes('&lt;')) {
                             const txt = document.createElement("textarea");
                             txt.innerHTML = cleanHtml;
                             cleanHtml = txt.value;
                        }
                        html += `<div class="wiki-content p-5 border border-slate-200 rounded-lg bg-slate-50 my-2">${cleanHtml}</div>`;
                    }
                    // Source
                    if(parts[2]) html += `<div class="prose mt-4 pt-4 border-t border-slate-100">${marked.parse(parts[2])}</div>`;
                    bubble.innerHTML = html;
                } else {
                    bubble.className = base + "bg-white border border-slate-200 text-slate-800 rounded-tl-sm prose";
                    bubble.innerHTML = marked.parse(text);
                }
            }
            div.appendChild(bubble);
            messagesDiv.appendChild(div);
            messagesDiv.scrollIntoView({ behavior: "smooth", block: "end" });
            lucide.createIcons();
        }

        async function handleMessage(text) {
            addMessage('user', text);
            userInput.value = '';
            showTyping("Initializing Agent...");
            let hasResponse = false;

            try {
                const response = await fetch('/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, session_id: sessionId })
                });
                const reader = response.body.getReader();
                const decoder = new TextDecoder();
                let buffer = '';
                while (true) {
                    const { done, value } = await reader.read();
                    if (done) { if(buffer.trim()) if(processBuffer(buffer)) hasResponse=true; break; }
                    buffer += decoder.decode(value, {stream: true});
                    // CORRECT SPLITTER: \n\n (real newlines)
                    let parts = buffer.split('\n\n');
                    buffer = parts.pop();
                    parts.forEach(p => { if(processBuffer(p)) hasResponse=true; });
                }
                if(!hasResponse) { hideTyping(); addMessage('system', "Error: No response from server.", 'error'); }
            } catch(e) {
                hideTyping();
                addMessage('system', "Error: " + e.message);
            } finally { hideTyping(); }
        }
        
        function processBuffer(chunk) {
            const trimmed = chunk.trim();
            if (!trimmed.startsWith('data: ')) return false;
            const jsonStr = trimmed.substring(6);
            try {
                const data = JSON.parse(jsonStr);
                if (data.type === 'tool') showTyping(`Running: ${data.name}...`);
                else if (data.type === 'answer') { hideTyping(); addMessage('ai', data.content); }
                else if (data.type === 'error') addMessage('system', `Error: ${data.content}`, 'tool');
                return true;
            } catch(e) { return false; }
        }
        document.getElementById('chat-form').addEventListener('submit', (e) => { e.preventDefault(); const t = userInput.value.trim(); if(t) handleMessage(t); });
    </script>
</body>
</html>
"""

async def startup():
    global mcp_client, agent
    print("\n--- UNIFIED CLIENT STARTING ---")
    for name, url in [("Salesforce", SALESFORCE_SERVER_URL), ("Confluence", CONFLUENCE_SERVER_URL)]:
        print(f"🔎 Connecting to {name} ({url})...")
        try:
            async with httpx.AsyncClient() as client:
                await client.get(url, timeout=2.0)
                print(f"   ✅ {name} Online")
        except Exception:
            print(f"   ⚠️  {name} might be offline (or streaming). Continuing...")

    try:
        llm = get_llm()
        mcp_client = MultiServerMCPClient({
            "salesforce": {"transport": "sse", "url": SALESFORCE_SERVER_URL},
            "confluence": {"transport": "sse", "url": CONFLUENCE_SERVER_URL}
        })
        mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=10.0)
        memory = MemorySaver()
        agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
        print(f"🚀 UNIFIED AGENT READY! http://localhost:{WEB_PORT}")
    except Exception as e:
        print(f"❌ Startup Error: {traceback.format_exc()}")

async def chat_endpoint(request):
    if not agent: return JSONResponse({"error": "Agent offline"}, status_code=503)
    data = await request.json()
    config = {"configurable": {"thread_id": data.get("session_id", "default")}}

    async def generator():
        try:
            state = await agent.aget_state(config)
            msgs = state.values.get("messages", []) if state.values else []
            input_msgs = [HumanMessage(content=data.get("message", ""))]
            if not msgs: input_msgs.insert(0, SYSTEM_PROMPT)

            async for chunk in agent.astream({"messages": input_msgs}, config=config, stream_mode="updates"):
                for node, values in chunk.items():
                    msgs = values.get("messages", [])
                    if not isinstance(msgs, list): msgs = [msgs]
                    for msg in msgs:
                        if isinstance(msg, ToolMessage):
                            yield f"data: {json.dumps({'type': 'tool', 'name': msg.name, 'content': str(msg.content)})}\n\n"
                        elif isinstance(msg, AIMessage) and msg.content:
                            yield f"data: {json.dumps({'type': 'answer', 'content': str(msg.content)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type='text/event-stream')

app = Starlette(
    debug=True,
    routes=[
        Route("/", lambda r: HTMLResponse(HTML_TEMPLATE)),
        Route("/chat", chat_endpoint, methods=["POST"]),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])],
    on_startup=[startup]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)