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

# Reuse your existing LLM setup
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

1. **FETCH CASE**: 
   - If the user provides a Case Number (e.g., "00001023"), use `execute_soql_query`.
   - Query pattern: `SELECT Subject, Description, Status, Priority FROM Case WHERE CaseNumber = 'THE_NUMBER' LIMIT 1`
   - If no case is found, stop and tell the user.

2. **ANALYZE & SEARCH**:
   - Extract key technical terms from the Case 'Subject' and 'Description'.
   - Use `search_documentation` to find relevant Confluence pages using those keywords.

3. **READ & RESOLVE**:
   - Use `read_page_content` to get the documentation details.
   - **CRITICAL RENDERING RULE**: The tool returns HTML.
   - If you want to display the documentation content to the user, return the **Raw HTML** wrapped in `<article>` tags.
   - Example: `<article><h1>Title</h1><p>Content...</p></article>`
   - Do NOT escape the tags (e.g. do not use &lt;).
   - Do NOT wrap it in a Markdown code block.
   - You can add a brief summary *before* the `<article>` tag if needed.

### 🛡️ RULES:
- Always verify the Case exists first.
- Do not hallucinate solutions.
- Be professional.
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
        
        /* Standard Chat Styles */
        .prose p { margin-bottom: 0.5rem; }
        .prose ul { list-style-type: disc; margin-left: 1.5rem; }
        .prose pre { background: #1e293b; color: #e2e8f0; padding: 0.75rem; border-radius: 0.5rem; overflow-x: auto; font-size: 0.85rem; }

        /* Confluence Wiki Content Styles */
        .wiki-content { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif; color: #172b4d; font-size: 0.95rem; }
        .wiki-content h1 { font-size: 1.5em; font-weight: 600; margin-top: 1em; margin-bottom: 0.5em; color: #172b4d; }
        .wiki-content h2 { font-size: 1.25em; font-weight: 500; margin-top: 1em; margin-bottom: 0.5em; border-bottom: 1px solid #ebecf0; }
        .wiki-content p { margin-bottom: 0.75em; line-height: 1.5; }
        .wiki-content ul, .wiki-content ol { margin-bottom: 1em; padding-left: 1.5em; }
        .wiki-content ul { list-style-type: disc; }
        .wiki-content ol { list-style-type: decimal; }
        .wiki-content pre { background: #f4f5f7; padding: 0.75rem; border-radius: 4px; overflow-x: auto; border: 1px solid #dfe1e6; font-family: monospace; }
        .wiki-content code { background: #f4f5f7; padding: 0.1em 0.3em; border-radius: 3px; font-family: monospace; color: #c7254e; }
        .wiki-content table { border-collapse: collapse; width: 100%; margin: 1em 0; font-size: 0.9em; }
        .wiki-content th { background-color: #f4f5f7; font-weight: 600; text-align: left; border: 1px solid #dfe1e6; padding: 8px; }
        .wiki-content td { border: 1px solid #dfe1e6; padding: 8px; }
        .wiki-content a { color: #0052cc; text-decoration: none; }
        .wiki-content a:hover { text-decoration: underline; }
        .wiki-content img { max-width: 100%; height: auto; margin: 0.5em 0; border-radius: 3px; }
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
            handleMessage(`I have a Salesforce Case with number '${caseNum}'. Fetch its details and find a resolution in Confluence.`);
        }

        function showTyping(text="Thinking...") {
            if (typingIndicatorElement) {
                typingIndicatorElement.querySelector('span').innerText = text;
                return;
            }
            
            const div = document.createElement('div');
            div.id = "typing-indicator";
            div.className = 'flex justify-start fade-in';
            div.innerHTML = `
                <div class="bg-white border border-slate-200 p-4 rounded-2xl rounded-tl-sm shadow-sm flex items-center gap-3">
                    <div class="flex gap-1">
                        <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce"></div>
                        <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.1s"></div>
                        <div class="w-2 h-2 bg-indigo-400 rounded-full animate-bounce" style="animation-delay: 0.2s"></div>
                    </div>
                    <span class="text-xs font-medium text-slate-500 uppercase tracking-wide">${text}</span>
                </div>`;
            
            messagesDiv.appendChild(div);
            messagesDiv.scrollIntoView({ behavior: "smooth", block: "end" });
            typingIndicatorElement = div;
        }

        function hideTyping() {
            if (typingIndicatorElement) {
                typingIndicatorElement.remove();
                typingIndicatorElement = null;
            }
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
                if (text.includes('<article>')) {
                    // HTML MODE
                    bubble.className = base + "bg-white border border-slate-200 text-slate-800 rounded-tl-sm wiki-content overflow-x-auto";
                    let content = text;
                    try { content = text.split('<article>')[1].split('</article>')[0]; } catch(e) {}
                    content = content.replace(/```html/g, '').replace(/```/g, '');
                    content = content.replace(/\\\\n/g, '').replace(/\\\\"/g, '"'); 
                    if(content.includes('&lt;')) {
                        const txt = document.createElement("textarea");
                        txt.innerHTML = content;
                        content = txt.value;
                    }
                    bubble.innerHTML = content;
                } else {
                    // MARKDOWN MODE
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
            
            let hasReceivedResponse = false;

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
                    
                    if (done) {
                        if(buffer.trim()) {
                            if(processBuffer(buffer)) hasReceivedResponse = true;
                        }
                        break;
                    }
                    
                    buffer += decoder.decode(value, {stream: true});
                    // FIX: Use correct single-backslash newline splitter
                    let parts = buffer.split('\n\n');
                    buffer = parts.pop();
                    
                    parts.forEach(part => {
                        if(processBuffer(part)) hasReceivedResponse = true;
                    });
                }
                
                if (!hasReceivedResponse) {
                    hideTyping();
                    addMessage('system', "Error: No response received from server.", 'error');
                }

            } catch(e) {
                hideTyping();
                addMessage('system', "Error: " + e.message);
            } finally {
                hideTyping();
            }
        }
        
        function processBuffer(chunk) {
            const trimmed = chunk.trim();
            if (!trimmed.startsWith('data: ')) return false;
            
            const jsonStr = trimmed.substring(6); // Remove "data: "
            try {
                const data = JSON.parse(jsonStr);
                if (data.type === 'tool') {
                    showTyping(`Running: ${data.name}...`);
                } else if (data.type === 'answer') {
                    hideTyping();
                    addMessage('ai', data.content);
                } else if (data.type === 'error') {
                    addMessage('system', `Error: ${data.content}`, 'tool');
                }
                return true;
            } catch(e) {
                console.warn("JSON Parse Error:", e);
                return false;
            }
        }
        
        document.getElementById('chat-form').addEventListener('submit', (e) => { e.preventDefault(); const t = userInput.value.trim(); if(t) handleMessage(t); });
    </script>
</body>
</html>
"""

async def startup():
    global mcp_client, agent
    print("\n--- UNIFIED CLIENT STARTING ---")
    
    # Retry Logic for Connections
    for name, url in [("Salesforce", SALESFORCE_SERVER_URL), ("Confluence", CONFLUENCE_SERVER_URL)]:
        print(f"🔎 Connecting to {name} ({url})...")
        connected = False
        for i in range(5):
            try:
                async with httpx.AsyncClient() as client:
                    await client.get(url, timeout=2.0)
                    print(f"   ✅ {name} Online")
                    connected = True
                    break
            except httpx.TimeoutException:
                print(f"   ✅ {name} Online (Streaming)")
                connected = True
                break
            except Exception as e:
                print(f"   ⏳ Waiting for {name}... ({i+1}/5)")
                await asyncio.sleep(2)
        
        if not connected:
            print(f"   ❌ {name} seems OFFLINE.")

    try:
        llm = get_llm()
        mcp_client = MultiServerMCPClient({
            "salesforce": {"transport": "sse", "url": SALESFORCE_SERVER_URL},
            "confluence": {"transport": "sse", "url": CONFLUENCE_SERVER_URL}
        })
        
        print("   ✅ Fetching Unified Toolset...")
        try:
            mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=10.0)
            print(f"   ✅ Loaded {len(mcp_tools)} tools.")
            memory = MemorySaver()
            agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
            print(f"🚀 UNIFIED AGENT READY! http://localhost:{WEB_PORT}")
        except Exception as e:
             print(f"   ⚠️ Failed to load tools: {e}")

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