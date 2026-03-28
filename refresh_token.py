"""
refresh_token.py — Refresh expired YouTube OAuth access tokens using saved refresh tokens.
Run locally monthly to keep all channel tokens fresh.

Usage:
  python refresh_token.py --slot 0
  python refresh_token.py --all     # refresh all slots
"""
import os, sys, json, argparse, requests

TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"

def refresh_slot(slot):
    token_file = f"token_slot{slot}.json"
    if not os.path.exists(token_file):
        print(f"❌ No token file for slot {slot}. Run get_oauth_token.py first.")
        return None

    with open(token_file) as f:
        data = json.load(f)

    r = requests.post(TOKEN_ENDPOINT, data={
        "client_id":     data["client_id"],
        "client_secret": data["client_secret"],
        "refresh_token": data["refresh_token"],
        "grant_type":    "refresh_token",
    })

    if r.status_code != 200:
        print(f"❌ Refresh failed for slot {slot}: {r.text}")
        return None

    new_token = r.json()["access_token"]
    data["access_token"] = new_token
    with open(token_file, "w") as f:
        json.dump(data, f, indent=2)

    print(f"\n✅ Slot {slot} token refreshed.")
    print(f"\nUpdate GitHub Secret 'YT_OAUTH_TOKEN_{slot}' with:\n\n{new_token}\n")
    return new_token

def main():
    parser = argparse.ArgumentParser()
    group  = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--slot", type=int, help="Refresh specific slot")
    group.add_argument("--all",  action="store_true", help="Refresh all slots")
    args   = parser.parse_args()

    if args.all:
        import glob
        files = sorted(glob.glob("token_slot*.json"))
        if not files:
            print("No token files found.")
            sys.exit(1)
        for f in files:
            slot = int(f.replace("token_slot","").replace(".json",""))
            refresh_slot(slot)
    else:
        refresh_slot(args.slot)

    print("\n⚠️  Remember: paste the new access tokens into your GitHub Secrets.")
    print("Settings → Secrets and variables → Actions → Update YT_OAUTH_TOKEN_X")

if __name__ == "__main__":
    main()
