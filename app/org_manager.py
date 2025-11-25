import json
import os
import sys

# Ensure we can find properties.py
current_dir = os.path.dirname(os.path.abspath(__file__))
if current_dir not in sys.path:
    sys.path.insert(0, current_dir)

try:
    from properties import (
        SALESFORCE_USERNAME, 
        SALESFORCE_PASSWORD, 
        SALESFORCE_SECURITY_TOKEN,
        SALESFORCE_DOMAIN
    )
except ImportError:
    # Fallback if properties aren't set yet
    SALESFORCE_USERNAME = None
    SALESFORCE_PASSWORD = None
    SALESFORCE_SECURITY_TOKEN = None
    SALESFORCE_DOMAIN = None

ORG_FILE = "salesforce_orgs.json"

class OrgManager:
    def __init__(self):
        self.orgs = self._load_orgs()
        self.default_org = "Primary"
        
        # FIX: Always overwrite "Primary" with latest data from properties.py
        # This ensures that if you edit properties.py, the changes take effect.
        if SALESFORCE_USERNAME:
            print(f"⚙️ Syncing 'Primary' org credentials from properties.py...")
            self.save_org("Primary", {
                "username": SALESFORCE_USERNAME,
                "password": SALESFORCE_PASSWORD,
                "security_token": SALESFORCE_SECURITY_TOKEN,
                "domain": SALESFORCE_DOMAIN
            })

    def _load_orgs(self):
        if not os.path.exists(ORG_FILE):
            return {}
        try:
            with open(ORG_FILE, 'r') as f:
                return json.load(f)
        except:
            return {}

    def save_org(self, alias, creds):
        # Load fresh first to avoid overwriting other updates
        self.orgs = self._load_orgs()
        self.orgs[alias] = creds
        with open(ORG_FILE, 'w') as f:
            json.dump(self.orgs, f, indent=2)

    def get_creds(self, alias=None):
        # Always reload to get latest creds
        self.orgs = self._load_orgs()
        target = alias if alias else self.default_org
        return self.orgs.get(target)

    def list_orgs(self):
        # CRITICAL FIX: Reload from disk to see orgs added by the MCP Server process
        self.orgs = self._load_orgs()
        return list(self.orgs.keys())

    def set_default(self, alias):
        self.orgs = self._load_orgs()
        if alias in self.orgs:
            self.default_org = alias
            return True
        return False

# Singleton instance
org_manager = OrgManager()