import time
import requests
from langchain_openai import AzureChatOpenAI
from typing import Optional
import os
import sys
import pathlib

# Add project root to path to allow importing from app
project_root = pathlib.Path(__file__).resolve().parents[1]
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

from app.properties import (
    CIRCUIT_LLM_API_APP_KEY,
    CIRCUIT_LLM_API_CLIENT_ID,
    CIRCUIT_LLM_API_CLIENT_SECRET,
    CIRCUIT_LLM_API_ENDPOINT,
    CIRCUIT_LLM_API_MODEL_NAME,
    CIRCUIT_LLM_API_VERSION,
    OAUTH_ENDPOINT,
)

access_token: Optional[str] = None
last_generated = 0.0

def generate_bearer_token(client_id: str, client_secret: str) -> str | None:
    """
    Generates a bearer token.
    """
    global access_token, last_generated
    url = OAUTH_ENDPOINT
    headers = {'Content-Type': 'application/x-www-form-urlencoded'}
    auth_info = {'client_id': f'{client_id}',
                 'client_secret': f'{client_secret}',
                 'grant_type': "client_credentials"}
    
    try:
        response = requests.post(url, data=auth_info, headers=headers)
        if response.status_code != 200:
            print(f"Token generation failed: {response.status_code} {response.text}")
            return None
            
        json_response = response.json()
        access = json_response.get('access_token')
        if access:
            access_token = access
            last_generated = time.time()
        return access_token
    except Exception as e:
        print(f"Error generating token: {e}")
        return None


def get_llm():
    # Refresh token if missing or older than ~3500 seconds
    if access_token is None or int(time.time()) > (last_generated + 3500):
        generate_bearer_token(CIRCUIT_LLM_API_CLIENT_ID, CIRCUIT_LLM_API_CLIENT_SECRET)

    if not access_token:
        raise RuntimeError("Failed to obtain access token for LLM usage.")

    return AzureChatOpenAI(
        azure_endpoint=CIRCUIT_LLM_API_ENDPOINT,
        api_key=access_token,
        api_version=CIRCUIT_LLM_API_VERSION,
        model=CIRCUIT_LLM_API_MODEL_NAME,
        default_headers={'client-id': CIRCUIT_LLM_API_CLIENT_ID},
        model_kwargs={'user': f'{{"appkey": "{CIRCUIT_LLM_API_APP_KEY}"}}'},
        temperature=0,
        streaming=True
    )