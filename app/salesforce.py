import sys
import os
import logging

# Configure logging to print to the server console
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salesforce_tools")

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# ----------------

from simple_salesforce import Salesforce
from properties import (
    SALESFORCE_USERNAME, 
    SALESFORCE_PASSWORD, 
    SALESFORCE_SECURITY_TOKEN,
    SALESFORCE_DOMAIN
)

# CRITICAL IMPORT
try:
    from server_instance import mcp_application
except ImportError:
    print("❌ IMPORT ERROR: Could not import 'mcp_application' from 'server_instance'.")
    raise

def get_salesforce_client() -> Salesforce:
    """Helper to establish a Salesforce connection."""
    logger.info("🔌 Connecting to Salesforce...")
    try:
        kwargs = {
            'username': SALESFORCE_USERNAME,
            'password': SALESFORCE_PASSWORD,
            'security_token': SALESFORCE_SECURITY_TOKEN,
        }
        if SALESFORCE_DOMAIN:
            kwargs['domain'] = SALESFORCE_DOMAIN
            
        sf = Salesforce(**kwargs)
        logger.info("✅ Salesforce Connection Established.")
        return sf
    except Exception as e:
        logger.error(f"❌ Salesforce Connection Failed: {e}")
        raise e

@mcp_application.tool()
def execute_soql_query(query: str) -> str:
    """Execute a SOQL query."""
    logger.info(f"🔍 TOOL CALL: execute_soql_query -> {query}")
    try:
        sf = get_salesforce_client()
        results = sf.query(query)
        
        records = results.get('records', [])
        logger.info(f"   Found {len(records)} records.")
        
        if not records:
            return "Query executed successfully but returned no records."
        
        formatted_results = []
        for rec in records:
            rec.pop('attributes', None)
            formatted_results.append(str(rec))
            
        return f"Found {results['totalSize']} records. Showing first {len(records)}:\n" + "\n---\n".join(formatted_results)

    except Exception as e:
        logger.error(f"   ❌ QUERY ERROR: {str(e)}")
        return f"Error executing SOQL query: {str(e)}"

@mcp_application.tool()
def describe_object(object_name: str) -> str:
    """Get metadata about a specific Salesforce object."""
    logger.info(f"📋 TOOL CALL: describe_object -> {object_name}")
    try:
        sf = get_salesforce_client()
        desc = sf.__getattr__(object_name).describe()
        
        fields = [f"{f['name']} ({f['type']})" for f in desc['fields']]
        result = f"Object: {desc['name']}\nLabel: {desc['label']}\nFields ({len(fields)}): {', '.join(fields[:50])}..."
        
        logger.info("   ✅ Description retrieved successfully.")
        return result
        
    except Exception as e:
        logger.error(f"   ❌ DESCRIBE ERROR: {str(e)}")
        return f"Error describing object '{object_name}': {str(e)}"