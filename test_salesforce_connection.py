import sys
import os

# Ensure we can import from the app folder
sys.path.insert(0, os.path.abspath("app"))

try:
    from properties import (
        SALESFORCE_USERNAME,
        SALESFORCE_PASSWORD,
        SALESFORCE_SECURITY_TOKEN,
        SALESFORCE_DOMAIN
    )
    from simple_salesforce import Salesforce
except ImportError as e:
    print(f"Import Error: {e}")
    print("Make sure you are running this from the project root and requirements are installed.")
    sys.exit(1)

def test_connection():
    print("\n--- TESTING SALESFORCE CREDENTIALS ---")
    print(f"Username: {SALESFORCE_USERNAME}")
    
    # Check for placeholders
    if "<your-" in SALESFORCE_USERNAME or "<your-" in SALESFORCE_PASSWORD:
        print("\n❌ ERROR: It looks like you are still using placeholder values.")
        print("   Please open 'app/properties.py' and add your real Salesforce credentials.")
        return

    print(f"Domain:   {SALESFORCE_DOMAIN or 'login (Production)'}")

    try:
        print("\n1. Attempting Login...")
        kwargs = {
            'username': SALESFORCE_USERNAME,
            'password': SALESFORCE_PASSWORD,
            'security_token': SALESFORCE_SECURITY_TOKEN,
        }
        if SALESFORCE_DOMAIN:
            kwargs['domain'] = SALESFORCE_DOMAIN
            
        sf = Salesforce(**kwargs)
        print("   ✅ Login Successful!")
        
        print("\n2. Testing Query (SELECT Id FROM Account LIMIT 1)...")
        res = sf.query("SELECT Id FROM Account LIMIT 1")
        print(f"   ✅ Query Successful! Total Records Found: {res['totalSize']}")
        
    except Exception as e:
        print(f"\n❌ CONNECTION FAILED: {e}")
        print("\nTROUBLESHOOTING:")
        print("1. Security Token: Did you generate a new one? (Settings > Reset My Security Token)")
        print("2. Domain: Are you using a Sandbox? If yes, set SALESFORCE_DOMAIN = 'test' in properties.py")
        print("3. Password: Did your password expire?")

if __name__ == "__main__":
    test_connection()