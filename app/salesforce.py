import sys
import os
import logging
import json

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

# --- READ TOOLS ---

@mcp_application.tool()
def execute_soql_query(query: str) -> str:
    """
    Execute a SOQL (Salesforce Object Query Language) query.
    Use this to find records or counts, e.g.:
    - "SELECT Id, Name FROM Account LIMIT 5"
    - "SELECT COUNT() FROM Contact"
    
    Args:
        query: The full SOQL query string.
    """
    logger.info(f"🔍 TOOL CALL: execute_soql_query -> {query}")
    try:
        sf = get_salesforce_client()
        results = sf.query(query)
        
        if results.get('totalSize') > 0 and not results.get('records'):
             return f"Query executed successfully. Total Count: {results['totalSize']}"

        records = results.get('records', [])
        logger.info(f"   Found {len(records)} records.")
        
        if not records:
             if results.get('totalSize') == 0:
                 return "Query executed successfully but returned no records."
             return f"Total Count: {results['totalSize']}"
        
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
    """Get metadata about a specific Salesforce object (fields, types)."""
    logger.info(f"📋 TOOL CALL: describe_object -> {object_name}")
    try:
        sf = get_salesforce_client()
        desc = sf.__getattr__(object_name).describe()
        
        fields = [f"{f['name']} ({f['type']})" for f in desc['fields']]
        result = f"Object: {desc['name']}\nLabel: {desc['label']}\nFields ({len(fields)}): {', '.join(fields[:50])}..."
        
        return result
    except Exception as e:
        return f"Error describing object '{object_name}': {str(e)}"

@mcp_application.tool()
def get_record_by_id(object_name: str, record_id: str) -> str:
    """Get all fields for a specific record by its ID."""
    logger.info(f"🆔 TOOL CALL: get_record_by_id -> {object_name} / {record_id}")
    try:
        sf = get_salesforce_client()
        record = sf.__getattr__(object_name).get(record_id)
        record.pop('attributes', None)
        return str(record)
    except Exception as e:
        return f"Error fetching record {record_id}: {str(e)}"

# --- SEARCH TOOLS ---

@mcp_application.tool()
def search_records(keyword: str) -> str:
    """
    Search for records using SOSL (Salesforce Object Search Language).
    Useful when you don't know the exact field to query.
    Example: "Find 'Acme'" will search Accounts, Contacts, Leads, etc.
    """
    logger.info(f"🔎 TOOL CALL: search_records -> {keyword}")
    try:
        sf = get_salesforce_client()
        # Simple SOSL search across all fields
        sosl = f"FIND {{{keyword}}} IN ALL FIELDS RETURNING Account(Id, Name), Contact(Id, Name, Email), Lead(Id, Name, Company)"
        results = sf.search(sosl)
        
        found = []
        # Iterate through search results (which are grouped by object type)
        if 'searchRecords' in results:
            for rec in results['searchRecords']:
                rec.pop('attributes', None)
                found.append(str(rec))
        
        if not found:
            return f"No records found for '{keyword}'."
            
        return f"Found {len(found)} records:\n" + "\n".join(found)
    except Exception as e:
        logger.error(f"   ❌ SEARCH ERROR: {str(e)}")
        return f"Error searching records: {str(e)}"

@mcp_application.tool()
def list_available_objects() -> str:
    """
    List all available SObjects (tables) in the Salesforce Org.
    Useful to find the API name of custom objects.
    """
    logger.info(f"📚 TOOL CALL: list_available_objects")
    try:
        sf = get_salesforce_client()
        desc = sf.describe()
        
        objects = []
        for obj in desc['sobjects']:
            if obj['queryable']: # Only show things we can actually query
                objects.append(f"{obj['name']} ({obj['label']})")
        
        return f"Found {len(objects)} queryable objects. First 50:\n" + ", ".join(objects[:50])
    except Exception as e:
        return f"Error listing objects: {str(e)}"

# --- WRITE TOOLS (Create / Update) ---

@mcp_application.tool()
def create_record(object_name: str, json_data: str) -> str:
    """
    Create a new record in Salesforce.
    
    Args:
        object_name: The API name of the object (e.g., 'Account', 'Lead')
        json_data: A JSON string containing the fields to set.
                   Example: '{"Name": "New Company", "Industry": "Tech"}'
    """
    logger.info(f"✨ TOOL CALL: create_record -> {object_name}")
    try:
        data = json.loads(json_data)
        sf = get_salesforce_client()
        
        result = sf.__getattr__(object_name).create(data)
        
        if result.get('success'):
            return f"✅ Successfully created {object_name}. ID: {result.get('id')}"
        else:
            return f"❌ Failed to create record. Errors: {result.get('errors')}"
            
    except json.JSONDecodeError:
        return "Error: json_data must be a valid JSON string."
    except Exception as e:
        logger.error(f"   ❌ CREATE ERROR: {str(e)}")
        return f"Error creating record: {str(e)}"

@mcp_application.tool()
def update_record(object_name: str, record_id: str, json_data: str) -> str:
    """
    Update an existing record in Salesforce.
    
    Args:
        object_name: The API name of the object (e.g., 'Account')
        record_id: The ID of the record to update.
        json_data: A JSON string containing the fields to update.
                   Example: '{"Status": "Closed", "Priority": "High"}'
    """
    logger.info(f"✏️ TOOL CALL: update_record -> {object_name} / {record_id}")
    try:
        data = json.loads(json_data)
        sf = get_salesforce_client()
        
        # The simple-salesforce update method returns 204 (None) on success
        result = sf.__getattr__(object_name).update(record_id, data)
        
        # If no exception was raised, it was successful
        return f"✅ Successfully updated {object_name} record {record_id}."
            
    except json.JSONDecodeError:
        return "Error: json_data must be a valid JSON string."
    except Exception as e:
        logger.error(f"   ❌ UPDATE ERROR: {str(e)}")
        return f"Error updating record: {str(e)}"

@mcp_application.tool()
def find_metadata_dependencies(metadata_id: str) -> str:
    """
    Find dependencies for a specific Metadata Component using the Tooling API.
    This helps analyze impact before changes.
    
    Args:
        metadata_id: The Salesforce ID of the metadata component (e.g., CustomField ID, ApexClass ID).
    """
    logger.info(f"🕸️ TOOL CALL: find_metadata_dependencies -> {metadata_id}")
    try:
        sf = get_salesforce_client()
        
        # 1. Find what this component DEPENDS ON (e.g., Apex Class uses Field X)
        # Query MetadataComponentDependency where MetadataComponentId is OUR ID
        query_uses = f"SELECT RefMetadataComponentName, RefMetadataComponentType FROM MetadataComponentDependency WHERE MetadataComponentId = '{metadata_id}'"
        res_uses = sf.tooling.query(query_uses)
        
        uses_list = []
        for rec in res_uses.get('records', []):
            uses_list.append(f"{rec['RefMetadataComponentType']}: {rec['RefMetadataComponentName']}")

        # 2. Find what DEPENDS ON this component (e.g., Layout Y uses Field X)
        # Query MetadataComponentDependency where RefMetadataComponentId is OUR ID
        query_used_by = f"SELECT MetadataComponentName, MetadataComponentType FROM MetadataComponentDependency WHERE RefMetadataComponentId = '{metadata_id}'"
        res_used_by = sf.tooling.query(query_used_by)
        
        used_by_list = []
        for rec in res_used_by.get('records', []):
            used_by_list.append(f"{rec['MetadataComponentType']}: {rec['MetadataComponentName']}")

        # Format Output
        output = f"Dependency Analysis for ID: {metadata_id}\n\n"
        
        output += f"🔻 USES ({len(uses_list)} items):\n"
        output += "\n".join(uses_list[:20]) if uses_list else "None"
        if len(uses_list) > 20: output += "\n... (truncated)"
        
        output += f"\n\n🔺 USED BY ({len(used_by_list)} items):\n"
        output += "\n".join(used_by_list[:20]) if used_by_list else "None"
        if len(used_by_list) > 20: output += "\n... (truncated)"
        
        return output

    except Exception as e:
        logger.error(f"   ❌ DEPENDENCY ERROR: {str(e)}")
        return f"Error finding dependencies: {str(e)}. Note: You must provide a valid 15 or 18 char Metadata ID."