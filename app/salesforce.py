from typing import Any, List, Dict
from simple_salesforce import Salesforce
from fastmcp_instantiator import mcp_application
from properties import (
    SALESFORCE_USERNAME, 
    SALESFORCE_PASSWORD, 
    SALESFORCE_SECURITY_TOKEN,
    SALESFORCE_DOMAIN
)

def get_salesforce_client() -> Salesforce:
    """Helper to establish a Salesforce connection."""
    # If domain is provided (e.g., 'test' for sandbox), pass it, otherwise default to login.salesforce.com
    kwargs = {
        'username': SALESFORCE_USERNAME,
        'password': SALESFORCE_PASSWORD,
        'security_token': SALESFORCE_SECURITY_TOKEN,
    }
    if SALESFORCE_DOMAIN:
        kwargs['domain'] = SALESFORCE_DOMAIN
        
    return Salesforce(**kwargs)

@mcp_application.tool()
def execute_soql_query(query: str) -> str:
    """
    Execute a SOQL (Salesforce Object Query Language) query.
    Use this to find records, e.g., "SELECT Id, Name, Industry FROM Account LIMIT 5".
    
    Args:
        query: The full SOQL query string.
    """
    try:
        sf = get_salesforce_client()
        results = sf.query(query)
        
        records = results.get('records', [])
        if not records:
            return "Query executed successfully but returned no records."
            
        # Format results simply for the LLM
        formatted_results = []
        for rec in records:
            # Remove attributes metadata to save tokens
            rec.pop('attributes', None)
            formatted_results.append(str(rec))
            
        return f"Found {results['totalSize']} records. Showing first {len(records)}:\n" + "\n---\n".join(formatted_results)

    except Exception as e:
        return f"Error executing SOQL query: {str(e)}"

@mcp_application.tool()
def describe_object(object_name: str) -> str:
    """
    Get metadata about a specific Salesforce object (fields, types, etc.).
    Useful for understanding what fields are available before querying.
    
    Args:
        object_name: The API name of the object (e.g., 'Account', 'Contact', 'CustomObject__c')
    """
    try:
        sf = get_salesforce_client()
        desc = sf.__getattr__(object_name).describe()
        
        fields = [f"{f['name']} ({f['type']})" for f in desc['fields']]
        
        info = f"""
        Object: {desc['name']}
        Label: {desc['label']}
        Key Prefix: {desc['keyPrefix']}
        Fields ({len(fields)} total): {', '.join(fields[:50])}
        (Truncated field list to first 50)
        """
        return info
        
    except Exception as e:
        return f"Error describing object '{object_name}': {str(e)}"

@mcp_application.tool()
def get_record_by_id(object_name: str, record_id: str) -> str:
    """
    Get all fields for a specific record by its ID.
    
    Args:
        object_name: The API name of the object (e.g. Account)
        record_id: The Salesforce ID of the record
    """
    try:
        sf = get_salesforce_client()
        record = sf.__getattr__(object_name).get(record_id)
        record.pop('attributes', None)
        return str(record)
    except Exception as e:
        return f"Error fetching record {record_id}: {str(e)}"