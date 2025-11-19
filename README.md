Salesforce MCP Service

🌟 Purpose

This version demonstrates a Salesforce integration using Anthropic's Model Context Protocol (MCP).

It includes:

A Salesforce Server that exposes tools to query SOQL, describe objects, and fetch records.

A Client that discovers these tools and uses an LLM to answer natural language questions about your Salesforce data.

🚀 Features

✅ Connects to Salesforce via simple-salesforce.

✅ Exposes tools: execute_soql_query, describe_object, get_record_by_id.

✅ Fully async MCP client using the SDK.

📦 Project Structure

circuit-mcp-server-sample/
→ app/
    salesforce.py              # Salesforce tools logic (NEW)
    fastmcp_instantiator.py    # Initialize MCP server and connect to tools
    properties.py              # Config & Credentials

→ client/
    client.py                  # MCP SDK client

main.py                        # Starts the MCP server
requirements.txt               # Python dependencies


⚙️ Setup

Install Dependencies:

pip install -r requirements.txt


Configure Credentials:
Update app/properties.py (or set environment variables) with your Salesforce details:

SALESFORCE_USERNAME

SALESFORCE_PASSWORD

SALESFORCE_SECURITY_TOKEN

Run Server:

python3 app --host 0.0.0.0 --port 8006


Run Client:

python3 client/client.py
