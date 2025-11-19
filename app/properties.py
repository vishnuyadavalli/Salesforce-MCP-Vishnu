import os

# LLM Specific
CIRCUIT_LLM_API_APP_KEY = os.environ.get('CIRCUIT_LLM_API_APP_KEY', "<your-llm-appkey-here>")
CIRCUIT_LLM_API_CLIENT_ID = os.environ.get('CIRCUIT_LLM_API_CLIENT_ID', "<your-llm-clientid-here>")
CIRCUIT_LLM_API_CLIENT_SECRET = os.environ.get('CIRCUIT_LLM_API_CLIENT_SECRET', "<your-llm-secret-here>")
CIRCUIT_LLM_API_MODEL_NAME = os.environ.get('CIRCUIT_LLM_API_MODEL_NAME', "<your-llm-model-here>") 
CIRCUIT_LLM_API_ENDPOINT = os.environ.get('CIRCUIT_LLM_API_ENDPOINT', "<your-llm-endpoint-here>")
CIRCUIT_LLM_API_VERSION = os.environ.get('CIRCUIT_LLM_API_VERSION', "<your-llm-version-here>")

# Salesforce Specific
SALESFORCE_USERNAME = os.environ.get('SALESFORCE_USERNAME', "<your-sf-username>")
SALESFORCE_PASSWORD = os.environ.get('SALESFORCE_PASSWORD', "<your-sf-password>")
SALESFORCE_SECURITY_TOKEN = os.environ.get('SALESFORCE_SECURITY_TOKEN', "<your-sf-token>")
# Optional: If using a sandbox or custom domain
SALESFORCE_DOMAIN = os.environ.get('SALESFORCE_DOMAIN', None) 

# Auth / Identity
JWKS_URI = os.environ.get('JWKS_URI', "<your-jwks-value-here>")
AUDIENCE = os.environ.get('AUDIENCE', "<your-aud-here>")
ISSUER = os.environ.get('ISSUER', "<your-iss-here>")
CIRCUIT_CLIENT_ID = os.environ.get('CIRCUIT_CLIENT_ID', "<your-clientid-here>")

OAUTH_ENDPOINT = os.environ.get('OAUTH_ENDPOINT', "https://id.cisco.com/oauth2/default/v1/token")