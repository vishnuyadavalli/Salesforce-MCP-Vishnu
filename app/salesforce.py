import sys
import os
import logging
import json

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("salesforce_tools")

# --- PATH FIX ---
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)
# ----------------

from simple_salesforce import Salesforce
from org_manager import org_manager
from server_instance import mcp_application

# --- HELPER ---
def get_salesforce_client(org_alias: str = None) -> Salesforce:
    """
    Establish a connection. 
    If org_alias is provided, connects to that specific org.
    Otherwise, connects to the default org.
    """
    creds = org_manager.get_creds(org_alias)
    
    if not creds:
        raise ValueError(f"No credentials found for org alias: {org_alias or org_manager.default_org}")

    logger.info(f"🔌 Connecting to Salesforce Org: {org_alias or org_manager.default_org}...")
    try:
        kwargs = {
            'username': creds['username'],
            'password': creds['password'],
            'security_token': creds['security_token'],
        }
        if creds.get('domain'):
            kwargs['domain'] = creds['domain']
            
        sf = Salesforce(**kwargs)
        return sf
    except Exception as e:
        logger.error(f"❌ Salesforce Connection Failed: {e}")
        raise e

# --- ORG MANAGEMENT TOOLS ---

@mcp_application.tool()
def add_salesforce_org(alias: str, username: str, password: str, token: str, domain: str = None) -> str:
    """
    Register a new Salesforce Org locally for comparison.
    Args:
        alias: A short name (e.g., 'UAT', 'Production', 'DevBox1')
        username: Salesforce Username
        password: Salesforce Password
        token: Security Token
        domain: Optional (e.g., 'test' for sandbox)
    """
    creds = {
        "username": username,
        "password": password,
        "security_token": token,
        "domain": domain
    }
    org_manager.save_org(alias, creds)
    return f"✅ Org '{alias}' added successfully. You can now use it for comparisons."

@mcp_application.tool()
def list_connected_orgs() -> str:
    """List all Salesforce organizations currently configured."""
    orgs = org_manager.list_orgs()
    default = org_manager.default_org
    return f"Connected Orgs: {', '.join(orgs)}. (Current Default: {default})"

@mcp_application.tool()
def set_default_org(alias: str) -> str:
    """Set the default org for standard queries."""
    if org_manager.set_default(alias):
        return f"✅ Default org switched to '{alias}'."
    return f"❌ Org '{alias}' not found."

# --- COMPARISON & METADATA TOOLS ---

@mcp_application.tool()
def fetch_metadata_source(org_alias: str, metadata_type: str, component_name: str) -> str:
    """
    Fetches the actual code/markup body of a metadata component for comparison.
    Supported Types: ApexClass, ApexTrigger, ApexPage (Visualforce), ApexComponent.
    
    Args:
        org_alias: The alias of the org to fetch from (e.g., 'Primary', 'UAT').
        metadata_type: e.g., 'ApexClass'
        component_name: e.g., 'MyController'
    """
    logger.info(f"📜 Fetching {metadata_type} / {component_name} from {org_alias}")
    try:
        sf = get_salesforce_client(org_alias)
        
        # Different objects store code in different fields
        query_field = "Body"
        if metadata_type in ["ApexPage", "ApexComponent"]:
            query_field = "Markup"
            
        query = f"SELECT {query_field} FROM {metadata_type} WHERE Name = '{component_name}' LIMIT 1"
        
        # FIX: Use sf.restful() to query the Tooling API correctly
        # simple-salesforce does not have a built-in .tooling.query() method
        result = sf.restful("tooling/query", params={"q": query})
        
        if result['totalSize'] == 0:
            return f"❌ Component '{component_name}' not found in org '{org_alias}'."
            
        code = result['records'][0][query_field]
        return f"--- BEGIN CODE ({org_alias}) ---\n{code}\n--- END CODE ---"

    except Exception as e:
        return f"Error fetching metadata from {org_alias}: {str(e)}"

# --- STANDARD TOOLS ---

@mcp_application.tool()
def execute_soql_query(query: str) -> str:
    """Execute a SOQL query against the DEFAULT org."""
    logger.info(f"🔍 TOOL CALL: execute_soql_query -> {query}")
    try:
        sf = get_salesforce_client() # Uses default
        results = sf.query(query)
        
        if results.get('totalSize') > 0 and not results.get('records'):
             return f"Query executed successfully. Total Count: {results['totalSize']}"

        records = results.get('records', [])
        if not records:
             if results.get('totalSize') == 0: return "Query executed successfully but returned no records."
             return f"Total Count: {results['totalSize']}"
        
        formatted_results = []
        for rec in records:
            rec.pop('attributes', None)
            formatted_results.append(str(rec))
            
        return f"Found {results['totalSize']} records. Showing first {len(records)}:\n" + "\n---\n".join(formatted_results)

    except Exception as e:
        return f"Error executing SOQL query: {str(e)}"

@mcp_application.tool()
def describe_object(object_name: str) -> str:
    """Get metadata about a specific Salesforce object (fields, types)."""
    try:
        sf = get_salesforce_client()
        desc = sf.__getattr__(object_name).describe()
        fields = [f"{f['name']} ({f['type']})" for f in desc['fields']]
        return f"Object: {desc['name']}\nLabel: {desc['label']}\nFields ({len(fields)}): {', '.join(fields[:50])}..."
    except Exception as e:
        return f"Error describing object '{object_name}': {str(e)}"

@mcp_application.tool()
def get_record_by_id(object_name: str, record_id: str) -> str:
    """Get all fields for a specific record by its ID."""
    try:
        sf = get_salesforce_client()
        record = sf.__getattr__(object_name).get(record_id)
        record.pop('attributes', None)
        return str(record)
    except Exception as e:
        return f"Error fetching record {record_id}: {str(e)}"

@mcp_application.tool()
def search_records(keyword: str) -> str:
    """Search for records using SOSL (Salesforce Object Search Language)."""
    try:
        sf = get_salesforce_client()
        sosl = f"FIND {{{keyword}}} IN ALL FIELDS RETURNING Account(Id, Name), Contact(Id, Name, Email), Lead(Id, Name, Company)"
        results = sf.search(sosl)
        found = []
        if 'searchRecords' in results:
            for rec in results['searchRecords']:
                rec.pop('attributes', None)
                found.append(str(rec))
        if not found: return f"No records found for '{keyword}'."
        return f"Found {len(found)} records:\n" + "\n".join(found)
    except Exception as e:
        return f"Error searching records: {str(e)}"

@mcp_application.tool()
def create_record(object_name: str, json_data: str) -> str:
    """Create a new record in Salesforce."""
    try:
        data = json.loads(json_data)
        sf = get_salesforce_client()
        result = sf.__getattr__(object_name).create(data)
        if result.get('success'): return f"✅ Successfully created {object_name}. ID: {result.get('id')}"
        else: return f"❌ Failed to create record. Errors: {result.get('errors')}"
    except Exception as e:
        return f"Error creating record: {str(e)}"

@mcp_application.tool()
def update_record(object_name: str, record_id: str, json_data: str) -> str:
    """Update an existing record in Salesforce."""
    try:
        data = json.loads(json_data)
        sf = get_salesforce_client()
        sf.__getattr__(object_name).update(record_id, data)
        return f"✅ Successfully updated {object_name} record {record_id}."
    except Exception as e:
        return f"Error updating record: {str(e)}"