import sys
import os

# 1. Setup Paths
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

print("--- CONFLUENCE CONNECTION DEBUGGER ---")

# 2. Check for Properties File
try:
    import confluence_app.properties as props
except ImportError:
    print("\n❌ ERROR: Could not import 'confluence_app.properties'.")
    print("   - Did you create the file 'confluence_app/properties.py'?")
    print("   - Did you create the empty file 'confluence_app/__init__.py'?")
    sys.exit(1)

# 3. Validate Credentials
print(f"URL:   {props.CONFLUENCE_URL}")
print(f"User:  {props.CONFLUENCE_USERNAME}")
token_mask = "*" * 5 + props.CONFLUENCE_API_TOKEN[-4:] if props.CONFLUENCE_API_TOKEN else "None"
print(f"Token: {token_mask}")

if "your-domain" in props.CONFLUENCE_URL or "your-email" in props.CONFLUENCE_USERNAME:
    print("\n❌ ERROR: You are still using placeholder credentials.")
    print("   -> Open 'confluence_app/properties.py' and add your real details.")
    sys.exit(1)

# 4. Attempt Connection
try:
    from atlassian import Confluence
    print("\n🔌 Connecting to Atlassian API...")
    
    conf = Confluence(
        url=props.CONFLUENCE_URL,
        username=props.CONFLUENCE_USERNAME,
        password=props.CONFLUENCE_API_TOKEN,
        cloud=True
    )
    
    # Test 1: Who am I?
    user = conf.get_user_details_by_userkey(
        conf.get_user_details_by_username(props.CONFLUENCE_USERNAME)['userKey']
    )
    print(f"   ✅ Authentication Success! Logged in as: {user.get('displayName')}")

    # Test 2: Search
    print("\n🔎 Testing Search (Query: 'onboarding')...")
    results = conf.cql('type="page" AND text ~ "onboarding"', limit=3)
    hits = results.get('results', [])
    
    if hits:
        print(f"   ✅ Search Success! Found {len(hits)} pages.")
        for h in hits:
            print(f"      - {h.get('title')} (ID: {h.get('content', {}).get('id')})")
    else:
        print("   ⚠️  Search returned 0 results (Check your permissions or try a different query).")

except Exception as e:
    print(f"\n❌ CONNECTION FAILED: {e}")
    print("   - Check your API Token.")
    print("   - Ensure the URL starts with https://")