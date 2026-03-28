"""
token_refresh.py — Auto-refreshes YouTube OAuth access token using stored refresh token.
Called at the start of every workflow run. Sets YT_OAUTH_TOKEN_0 environment variable.
No manual token refresh ever needed again.
"""
import os
import sys
import requests
import json

def refresh():
    refresh_token = os.environ.get("YT_REFRESH_TOKEN", "")
    client_id     = os.environ.get("YT_CLIENT_ID", "")
    client_secret = os.environ.get("YT_CLIENT_SECRET", "")

    if not all([refresh_token, client_id, client_secret]):
        print("[TOKEN] Missing refresh credentials, checking for direct access token...")
        token = os.environ.get("YT_OAUTH_TOKEN_0", "")
        if token:
            print("[TOKEN] Using existing YT_OAUTH_TOKEN_0")
            return token
        print("[TOKEN] ERROR: No tokens available at all!")
        sys.exit(1)

    print("[TOKEN] Refreshing access token...")
    r = requests.post("https://oauth2.googleapis.com/token", data={
        "client_id":     client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type":    "refresh_token",
    }, timeout=15)

    if r.status_code != 200:
        print(f"[TOKEN] Refresh failed ({r.status_code}): {r.text[:200]}")
        # Fallback to existing token
        token = os.environ.get("YT_OAUTH_TOKEN_0", "")
        if token:
            print("[TOKEN] Falling back to existing YT_OAUTH_TOKEN_0")
            return token
        sys.exit(1)

    new_token = r.json().get("access_token", "")
    if not new_token:
        print("[TOKEN] No access_token in refresh response")
        sys.exit(1)

    print(f"[TOKEN] Fresh token obtained (expires in {r.json().get('expires_in', '?')}s)")

    # Write to GitHub Actions environment so subsequent steps can use it
    github_env = os.environ.get("GITHUB_ENV", "")
    if github_env:
        with open(github_env, "a") as f:
            f.write(f"YT_OAUTH_TOKEN_0={new_token}\n")
        print("[TOKEN] Written to GITHUB_ENV for subsequent steps")
    else:
        # Running locally
        print(f"[TOKEN] Access token: {new_token[:20]}...{new_token[-10:]}")

    return new_token

if __name__ == "__main__":
    refresh()
