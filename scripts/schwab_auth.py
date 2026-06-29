"""
One-time Schwab OAuth setup script.

Run this ONCE to authenticate with Schwab and save the token file.
After this, the app loads tokens automatically (auto-refreshes when expired).

Usage:
    python scripts/schwab_auth.py

What it does:
  1. Opens your browser to the Schwab login page
  2. After you log in and approve, copy the redirect URL back into the terminal
  3. Saves the token to env/schwab_token.json

Prerequisites:
  - env/.env must have SCHWAB_API_KEY, SCHWAB_API_SECRET, SCHWAB_CALLBACK_URL set
  - Your Schwab app at developer.schwab.com must have the callback URL registered
"""
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import Config

import schwab

token_path = Path(Config.SCHWAB_TOKEN_PATH)
token_path.parent.mkdir(parents=True, exist_ok=True)

print("=" * 60)
print("Schwab OAuth Setup")
print("=" * 60)
print(f"API Key      : {Config.SCHWAB_API_KEY[:8]}...")
print(f"Callback URL : {Config.SCHWAB_CALLBACK_URL}")
print(f"Token will be saved to: {token_path}")
print()
print("A browser window will open. Log in to Schwab and approve access.")
print("Then paste the redirect URL back here when prompted.")
print()

try:
    client = schwab.auth.client_from_login_flow(
        api_key=Config.SCHWAB_API_KEY,
        app_secret=Config.SCHWAB_API_SECRET,
        callback_url=Config.SCHWAB_CALLBACK_URL,
        token_path=str(token_path),
    )
    print()
    print("Authentication successful!")
    print(f"Token saved to: {token_path}")
    print()
    print("You can now run the app normally. Set DATA_PROVIDER=schwab in env/.env")
except Exception as e:
    print(f"\nAuthentication failed: {e}")
    sys.exit(1)
