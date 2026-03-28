"""
get_oauth_token.py — Run this LOCALLY to get a fresh YouTube OAuth access token.

Usage:
  python get_oauth_token.py --slot 0

It will open a browser, ask you to authorize, then print the access token
and refresh token. Paste the access token into your GitHub Secret.

Requirements:
  pip install google-auth-oauthlib google-auth-httplib2 google-api-python-client

IMPORTANT: Each channel MUST use credentials from its own Google account.
Run this separately for each slot with the correct Google account logged in.
"""
import os, sys, json, argparse

def get_token(slot):
    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
        from google.auth.transport.requests import Request
        import google.oauth2.credentials
    except ImportError:
        print("Run: pip install google-auth-oauthlib google-auth-httplib2")
        sys.exit(1)

    CLIENT_SECRETS_FILE = f"client_secrets_slot{slot}.json"
    SCOPES = [
        "https://www.googleapis.com/auth/youtube.upload",
        "https://www.googleapis.com/auth/youtube.force-ssl",
        "https://www.googleapis.com/auth/youtube",
        "https://www.googleapis.com/auth/youtubepartner",
    ]

    if not os.path.exists(CLIENT_SECRETS_FILE):
        print(f"\n❌ Missing: {CLIENT_SECRETS_FILE}")
        print("Download OAuth 2.0 client credentials from Google Cloud Console:")
        print("  1. Go to console.cloud.google.com")
        print("  2. Select/Create project for this channel")
        print("  3. APIs & Services → Credentials → Create OAuth 2.0 Client ID")
        print("  4. Application type: Desktop app")
        print(f"  5. Download JSON → save as '{CLIENT_SECRETS_FILE}'")
        sys.exit(1)

    flow = InstalledAppFlow.from_client_secrets_file(CLIENT_SECRETS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    print("\n" + "="*60)
    print(f"✅ Token obtained for slot {slot}")
    print("="*60)
    print(f"\nACCESS TOKEN (add as GitHub Secret 'YT_OAUTH_TOKEN_{slot}'):")
    print(f"\n{creds.token}\n")
    print(f"REFRESH TOKEN (save this locally for renewal):")
    print(f"\n{creds.refresh_token}\n")
    print("="*60)
    print("\n⚠️  ACCESS TOKENS EXPIRE IN ~1 HOUR.")
    print("You will need to refresh this token monthly.")
    print("Save the refresh token and client_secrets file securely.")

    # Save to local file for convenience
    token_data = {
        "slot": slot,
        "access_token":  creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri":     creds.token_uri,
        "client_id":     creds.client_id,
        "client_secret": creds.client_secret,
        "scopes":        list(creds.scopes or SCOPES),
    }
    with open(f"token_slot{slot}.json", "w") as f:
        json.dump(token_data, f, indent=2)
    print(f"\nFull token data saved to: token_slot{slot}.json")
    print("⚠️  NEVER commit this file to GitHub.\n")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--slot", type=int, required=True,
                        help="Channel slot number (0, 1, 2...)")
    args = parser.parse_args()
    get_token(args.slot)
