import logging
import json
from atlassian import Confluence
from properties import CONFLUENCE_URL, CONFLUENCE_USERNAME, CONFLUENCE_API_TOKEN
from server_instance import mcp_application

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("confluence_tools")

def get_client():
    """Establishes connection to Confluence."""
    try:
        # Validate credentials existence
        if not CONFLUENCE_URL or not CONFLUENCE_USERNAME or not CONFLUENCE_API_TOKEN:
            raise ValueError("Missing Confluence credentials in environment variables.")

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
    Returns a JSON string of results: [{"id": "...", "title": "...", "url": "..."}]
    """
    logger.info(f"🔎 Searching Confluence for: {query}")
    try:
        confluence = get_client()
        cql = f'type="page" AND text ~ "{query}"'
        results = confluence.cql(cql, limit=5)
        
        found = []
        for res in results.get('results', []):
            found.append({
                "id": res.get('content', {}).get('id'),
                "title": res.get('title'),
                "url": CONFLUENCE_URL.rstrip('/') + res.get('url', '')
            })
            
        # Return raw JSON string so the Agent doesn't have to hallucinate the format
        return json.dumps(found)

    except Exception as e:
        error_msg = f"Error searching Confluence: {str(e)}"
        logger.error(error_msg)
        return json.dumps({"error": error_msg})

@mcp_application.tool()
def read_page_content(page_id: str) -> str:
    """
    Fetch the full content of a specific Confluence page.
    """
    logger.info(f"📖 Reading Page ID: {page_id}")
    try:
        confluence = get_client()
        page = confluence.get_page_by_id(page_id, expand='body.storage')
        
        return json.dumps({
            "title": page.get('title'),
            "body": page.get('body', {}).get('storage', {}).get('value', '')
        })
    except Exception as e:
        return json.dumps({"error": f"Error reading page: {str(e)}"})

@mcp_application.tool()
def list_spaces() -> str:
    """List available Confluence spaces as JSON."""
    try:
        confluence = get_client()
        spaces = confluence.get_all_spaces(start=0, limit=20, expand='description.plain')
        output = []
        for s in spaces.get('results', []):
            output.append({"name": s['name'], "key": s['key']})
        return json.dumps(output)
    except Exception as e:
        return json.dumps({"error": str(e)})