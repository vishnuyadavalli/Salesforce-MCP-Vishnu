import os

# LLM Specific
CIRCUIT_LLM_API_APP_KEY = os.environ.get('CIRCUIT_LLM_API_APP_KEY', "egai-prd-operations-123431302-coding-1752766159822")
CIRCUIT_LLM_API_CLIENT_ID = os.environ.get('CIRCUIT_LLM_API_CLIENT_ID', "0oapnrztf8a0LeJD45d7")
CIRCUIT_LLM_API_CLIENT_SECRET = os.environ.get('CIRCUIT_LLM_API_CLIENT_SECRET', "hxypG8roXynJRk85bxcJjPPWhrwgeVcCjrxBOa1KrWzj1BmnN2RfAk9y8ceddtXP")
CIRCUIT_LLM_API_MODEL_NAME = os.environ.get('CIRCUIT_LLM_API_MODEL_NAME', "gpt-4.1") 
CIRCUIT_LLM_API_ENDPOINT = os.environ.get('CIRCUIT_LLM_API_ENDPOINT', "https://chat-ai.cisco.com")
CIRCUIT_LLM_API_VERSION = os.environ.get('CIRCUIT_LLM_API_VERSION', "2025-04-01-preview")

# Salesforce Specific
SALESFORCE_USERNAME = os.environ.get('SALESFORCE_USERNAME', "dddddd")
SALESFORCE_PASSWORD = os.environ.get('SALESFORCE_PASSWORD', "ddddddd")
SALESFORCE_SECURITY_TOKEN = os.environ.get('SALESFORCE_SECURITY_TOKEN', "ddddd")
# Optional: If using a sandbox or custom domain
SALESFORCE_DOMAIN = os.environ.get('SALESFORCE_DOMAIN', 'test') 

# Auth / Identity
JWKS_URI = os.environ.get('JWKS_URI', "<your-jwks-value-here>")
AUDIENCE = os.environ.get('AUDIENCE', "<your-aud-here>")
ISSUER = os.environ.get('ISSUER', "<your-iss-here>")
CIRCUIT_CLIENT_ID = os.environ.get('CIRCUIT_CLIENT_ID', "<your-clientid-here>")

OAUTH_ENDPOINT = os.environ.get('OAUTH_ENDPOINT', "https://id.cisco.com/oauth2/default/v1/token")