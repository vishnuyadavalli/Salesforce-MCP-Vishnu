import logging
import json
from atlassian import Confluence
# Ensure we import from the local properties file
try:
    from properties import CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN
except ImportError:
    from confluence_app.properties import CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN

from server_instance import mcp_application

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("confluence_tools")

def get_client():
    """Establishes connection to Confluence."""
    # Debug log to terminal
    logger.info(f"🔌 Connecting to: {CONFLUENCE_URL} as {CONFLUENCE_USERNAME}")
    
    try:
        return Confluence(
            url=CONFLUENCE_URL,
            username=CONFLUENCE_USERNAME,
            password=CONFLUENCE_API_TOKEN,
            cloud=True
        )
    except Exception as e:
        logger.error(f"Failed to connect to Confluence: {e}")
        raise e

@mcp_application.tool()
def search_documentation(query: str) -> str:
    """
    Search Confluence pages using CQL. 
    Returns a JSON string of results.
    """
    logger.info(f"🔎 Searching Confluence for: {query}")
    
    try:
        confluence = get_client()
        
        # 1. Try a broader search if the specific one is empty
        cql = f'type="page" AND text ~ "{query}"'
        results = confluence.cql(cql, limit=5)
        
        found = []
        for res in results.get('results', []):
            # Safely get ID (it can be at top level or inside content)
            page_id = res.get('content', {}).get('id') or res.get('id')
            
            found.append({
                "id": page_id,
                "title": res.get('title'),
                "url": CONFLUENCE_URL.rstrip('/') + res.get('url', '')
            })
            
        # DEBUG: If empty, return debug info as a "fake" result so the user sees it
        if not found:
            # Check if we can even see the current user
            try:
                myself = confluence.get_user_details_by_userkey(
                    confluence.get_user_details_by_username(CONFLUENCE_USERNAME)['userKey']
                )
                user_name = myself.get('displayName', 'Unknown')
            except:
                user_name = "Authentication Failed"

            return json.dumps([{
                "id": "error",
                "title": f"No Results Found (Connected as: {user_name})",
                "url": "#",
                "debug": f"Checked URL: {CONFLUENCE_URL}. Query: {cql}"
            }])
            
        return json.dumps(found)

    except Exception as e:
        logger.error(f"Search Error: {str(e)}")
        return json.dumps({"error": str(e)})

@mcp_application.tool()
def read_page_content(page_id: str) -> str:
    """
    Fetch the full content of a specific Confluence page.
    """
    logger.info(f"📖 Reading Page ID: {page_id}")
    
    if page_id == "error":
        return "This is a debug entry, not a real page."

    try:
        confluence = get_client()
        page = confluence.get_page_by_id(page_id, expand='body.storage')
        
        body = page.get('body', {}).get('storage', {}).get('value', '')
        title = page.get('title')
        
        return json.dumps({
            "title": title,
            "body": f"<h1>{title}</h1>{body}"
        })
    except Exception as e:
        return json.dumps({"error": f"Error reading page: {str(e)}"})

@mcp_application.tool()
def list_spaces() -> str:
    """List available Confluence spaces."""
    try:
        confluence = get_client()
        spaces = confluence.get_all_spaces(start=0, limit=20, expand='description.plain')
        output = []
        for s in spaces.get('results', []):
            output.append({"name": s['name'], "key": s['key']})
        return json.dumps(output)
    except Exception as e:
        return json.dumps({"error": str(e)})