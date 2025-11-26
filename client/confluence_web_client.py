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
MCP_SERVER_URL = "http://localhost:8013/sse"
WEB_PORT = 8082

agent = None
mcp_client = None

# --- SYSTEM PROMPT ---
SYSTEM_PROMPT = SystemMessage(content="""
You are a Confluence Documentation API middleware.

1. **SEARCHING**: 
   - Call `search_documentation`.
   - The tool returns a JSON string. **Return that JSON string EXACTLY as your final answer.**
   - Do NOT add markdown, conversational text, or formatting. Just the raw JSON.

2. **READING**: 
   - Call `read_page_content`.
   - The tool returns a JSON object with "body" (HTML). 
   - **CRITICAL**: Return ONLY the raw HTML string from the "body" field. 
   - Do NOT wrap it in JSON. Do NOT escape the HTML tags (e.g. do not use &lt;).
   - Wrap the entire HTML output in `<article>` tags so the UI can find it.

3. **ERRORS**:
   - If the tool returns a JSON object with an "error" field, explain the error to the user in plain text.
""")

# --- HTML TEMPLATE ---
HTML_TEMPLATE = r"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Confluence Browser</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <script src="https://unpkg.com/lucide@latest"></script>
    <style>
        ::-webkit-scrollbar { width: 8px; }
        ::-webkit-scrollbar-track { background: #f1f5f9; }
        ::-webkit-scrollbar-thumb { background: #cbd5e1; border-radius: 4px; }
        .fade-in { animation: fadeIn 0.3s ease-in; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(5px); } to { opacity: 1; transform: translateY(0); } }
        
        /* Confluence Content Styling */
        .wiki-content { font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Oxygen, Ubuntu, "Fira Sans", "Droid Sans", "Helvetica Neue", sans-serif; color: #172b4d; }
        .wiki-content h1 { font-size: 2em; font-weight: 600; margin-top: 1.5em; margin-bottom: 0.5em; color: #172b4d; }
        .wiki-content h2 { font-size: 1.5em; font-weight: 500; margin-top: 1.5em; margin-bottom: 0.5em; border-bottom: 1px solid #ebecf0; padding-bottom: 0.3em; }
        .wiki-content h3 { font-size: 1.25em; font-weight: 500; margin-top: 1em; margin-bottom: 0.5em; }
        .wiki-content p { margin-bottom: 1em; line-height: 1.6; }
        .wiki-content ul, .wiki-content ol { margin-bottom: 1em; padding-left: 2em; }
        .wiki-content ul { list-style-type: disc; }
        .wiki-content ol { list-style-type: decimal; }
        .wiki-content pre { background: #f4f5f7; padding: 1rem; border-radius: 3px; overflow-x: auto; font-family: monospace; font-size: 0.9em; border: 1px solid #dfe1e6; }
        .wiki-content code { background: #f4f5f7; padding: 0.1em 0.4em; border-radius: 3px; font-family: monospace; font-size: 0.9em; color: #c7254e; }
        .wiki-content a { color: #0052cc; text-decoration: none; }
        .wiki-content a:hover { text-decoration: underline; }
        .wiki-content table { border-collapse: collapse; width: 100%; margin: 1em 0; }
        .wiki-content th { background-color: #f4f5f7; font-weight: 600; text-align: left; border: 1px solid #dfe1e6; padding: 8px; }
        .wiki-content td { border: 1px solid #dfe1e6; padding: 8px; }
        .wiki-content img { max-width: 100%; height: auto; margin: 1em 0; border-radius: 3px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .wiki-content blockquote { border-left: 4px solid #dfe1e6; padding-left: 1em; color: #6b778c; margin-left: 0; }
    </style>
</head>
<body class="bg-slate-100 h-screen flex overflow-hidden font-sans text-slate-800">

    <aside class="w-1/3 bg-white border-r border-slate-200 flex flex-col shadow-sm z-10">
        <div class="p-4 border-b border-slate-200 bg-slate-50">
            <div class="flex items-center gap-2 mb-4">
                <div class="bg-blue-600 p-1.5 rounded-lg"><i data-lucide="book" class="text-white w-5 h-5"></i></div>
                <h1 class="font-bold text-lg">DocuSearch</h1>
            </div>
            <form id="search-form" class="relative">
                <i data-lucide="search" class="absolute left-3 top-3 w-5 h-5 text-slate-400"></i>
                <input type="text" id="search-input" class="w-full bg-white border border-slate-300 pl-10 pr-4 py-2.5 rounded-xl text-sm outline-none focus:ring-2 focus:ring-blue-500" placeholder="Search docs..." autocomplete="off">
            </form>
        </div>
        <div id="results-list" class="flex-1 overflow-y-auto p-2 space-y-2">
            <div class="text-center mt-20 text-slate-400 px-6">
                <p class="text-sm">Search keywords to find pages.</p>
            </div>
        </div>
        <div class="p-3 border-t border-slate-200 bg-slate-50 text-xs text-slate-500 flex justify-between">
            <span id="status-text">Ready</span>
            <div id="spinner" class="hidden animate-spin w-4 h-4 border-2 border-blue-600 border-t-transparent rounded-full"></div>
        </div>
    </aside>

    <main class="flex-1 flex flex-col bg-white overflow-hidden relative">
        <div class="h-16 border-b border-slate-200 flex items-center justify-between px-6 bg-white shrink-0">
            <h2 id="page-title" class="text-xl font-bold text-slate-800 truncate">Select a page</h2>
        </div>
        <div id="content-viewer" class="flex-1 overflow-y-auto p-8 bg-white">
            <div class="max-w-4xl mx-auto wiki-content" id="article-body"></div>
        </div>
    </main>

    <script>
        lucide.createIcons();
        const sessionId = "conf_ui_" + Math.random().toString(36).substring(7);
        const searchForm = document.getElementById('search-form');
        const searchInput = document.getElementById('search-input');
        const resultsList = document.getElementById('results-list');
        const articleBody = document.getElementById('article-body');
        const pageTitle = document.getElementById('page-title');
        const spinner = document.getElementById('spinner');
        const statusText = document.getElementById('status-text');
        let isProcessing = false;

        function setLoading(loading, text="Ready") {
            isProcessing = loading;
            statusText.innerText = text;
            spinner.classList.toggle('hidden', !loading);
        }

        searchForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const query = searchInput.value.trim();
            if(!query || isProcessing) return;
            setLoading(true, "Searching...");
            resultsList.innerHTML = '';

            try {
                const response = await sendMessage(`Search for "${query}"`);
                
                // Attempt to find JSON array
                let pages = [];
                try {
                    const cleanJson = response.replace(/```json/g, '').replace(/```/g, '').trim();
                    pages = JSON.parse(cleanJson);
                } catch(e) {
                    const match = response.match(/\[.*\]/s);
                    if(match) pages = JSON.parse(match[0]);
                }

                if(Array.isArray(pages) && pages.length > 0) {
                    renderResults(pages);
                } else {
                    resultsList.innerHTML = `<div class="p-4 text-sm text-slate-500 text-center">No pages found.</div>`;
                }
            } catch(err) {
                console.error(err);
                resultsList.innerHTML = `<div class="p-4 text-sm text-red-500">Error searching.</div>`;
            }
            setLoading(false);
        });

        function renderResults(pages) {
            pages.forEach(page => {
                const card = document.createElement('div');
                card.className = "p-4 bg-white border border-slate-200 rounded-xl cursor-pointer hover:border-blue-500 hover:shadow-sm transition-all fade-in mb-2";
                card.innerHTML = `
                    <div class="flex items-start gap-3">
                        <div class="bg-slate-100 p-2 rounded-lg"><i data-lucide="file" class="w-4 h-4 text-slate-500"></i></div>
                        <div class="flex-1 min-w-0">
                            <h3 class="font-medium text-sm text-slate-900 truncate">${page.title}</h3>
                            <p class="text-xs text-slate-500 mt-0.5 truncate">ID: ${page.id}</p>
                        </div>
                    </div>`;
                card.onclick = () => loadPage(page.id, page.title);
                resultsList.appendChild(card);
            });
            lucide.createIcons();
        }

        async function loadPage(pageId, title) {
            if(isProcessing) return;
            setLoading(true, `Loading ${title}...`);
            pageTitle.innerText = title;
            articleBody.innerHTML = '<div class="animate-pulse text-slate-400">Loading content...</div>';

            try {
                const response = await sendMessage(`Read page ID ${pageId}`);
                let content = response;

                // 1. Unwrap <article> tags
                if(content.includes('<article>')) {
                    content = content.split('<article>')[1].split('</article>')[0];
                }

                // 2. Unwrap Markdown Code Blocks (```html ... ```)
                content = content.replace(/```html/g, '').replace(/```/g, '');

                // 3. Clean up JSON string literals (newlines/quotes)
                content = content.replace(/\\n/g, '').replace(/\\"/g, '"');
                
                // 4. Decode HTML entities if LLM escaped them (e.g. &lt;h1&gt;)
                if(content.includes('&lt;')) {
                    const txt = document.createElement("textarea");
                    txt.innerHTML = content;
                    content = txt.value;
                }

                articleBody.innerHTML = content;
            } catch(err) {
                articleBody.innerHTML = `<div class="text-red-500">Failed to load: ${err.message}</div>`;
            }
            setLoading(false);
        }

        async function sendMessage(message) {
            const response = await fetch('/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: sessionId })
            });
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let fullText = "";
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) {
                    if(buffer.trim().startsWith('data: ')) {
                         try {
                            const data = JSON.parse(buffer.trim().replace('data: ', ''));
                            if(data.type === 'answer') fullText += data.content;
                         } catch(e) {}
                    }
                    break;
                }
                buffer += decoder.decode(value, {stream: true});
                let parts = buffer.split('\\n\\n');
                buffer = parts.pop();
                for (const part of parts) {
                    if (part.trim().startsWith('data: ')) {
                        try {
                            const data = JSON.parse(part.trim().replace('data: ', ''));
                            if(data.type === 'answer') fullText += data.content;
                        } catch(e) {}
                    }
                }
            }
            return fullText;
        }
    </script>
</body>
</html>
"""

async def startup():
    global mcp_client, agent
    try:
        llm = get_llm()
        mcp_client = MultiServerMCPClient({
            "confluence": {"transport": "sse", "url": MCP_SERVER_URL}
        })
        mcp_tools = await asyncio.wait_for(mcp_client.get_tools(), timeout=5.0)
        memory = MemorySaver()
        agent = create_react_agent(llm, mcp_tools, checkpointer=memory)
        print(f"🚀 CLIENT READY: http://localhost:{WEB_PORT}")
    except Exception as e:
        print(f"❌ Startup Error: {e}")

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
                        if isinstance(msg, AIMessage) and msg.content:
                            yield f"data: {json.dumps({'type': 'answer', 'content': str(msg.content)})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'type': 'error', 'content': str(e)})}\n\n"

    return StreamingResponse(generator(), media_type='text/event-stream')

async def health(request):
    if agent: return JSONResponse({"status": "ok"})
    return JSONResponse({"status": "error"}, status_code=503)

app = Starlette(
    debug=True,
    routes=[
        Route("/", lambda r: HTMLResponse(HTML_TEMPLATE)),
        Route("/chat", chat_endpoint, methods=["POST"]),
        Route("/health", health),
    ],
    middleware=[Middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"])],
    on_startup=[startup]
)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=WEB_PORT)