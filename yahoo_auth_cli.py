#!/usr/bin/env python3
"""
Interactive Yahoo Fantasy OAuth2 Authentication CLI
Usage: python3 yahoo_auth_cli.py
"""

import os
import sys
import webbrowser
from yahoo_service import YahooFantasyClient, load_env_vars, TOKEN_CACHE_FILE

def main():
    print("=" * 65)
    print("🏈 Yahoo Fantasy Sports OAuth2 Setup Assistant")
    print("=" * 65)

    env_vars = load_env_vars()
    client_id = os.getenv("YAHOO_CLIENT_ID") or env_vars.get("YAHOO_CLIENT_ID", "")
    client_secret = os.getenv("YAHOO_CLIENT_SECRET") or env_vars.get("YAHOO_CLIENT_SECRET", "")

    if not client_id:
        print("\n📝 No YAHOO_CLIENT_ID found.")
        print("Please create an app at: https://developer.yahoo.com/apps/create/")
        print("Set Application Name: 'Fantasy Dashboard'")
        print("Set Application Type: 'Installed Application'")
        print("Set Callback Domain / Redirect URI: 'oob' or 'https://localhost:8080'")
        print("Permissions: 'Fantasy Sports' (Read)")
        print("-" * 65)
        client_id = input("Enter your Yahoo Client ID (Consumer Key): ").strip()
        client_secret = input("Enter your Yahoo Client Secret (Consumer Secret): ").strip()

    if not client_id or not client_secret:
        print("❌ Error: Client ID and Client Secret are required.")
        sys.exit(1)

    client = YahooFantasyClient(client_id=client_id, client_secret=client_secret, redirect_uri="oob")
    
    auth_url = client.get_authorization_url()
    print("\n🌐 Step 1: Open the following URL in your browser to authorize:")
    print("-" * 65)
    print(auth_url)
    print("-" * 65)

    try:
        webbrowser.open(auth_url)
    except Exception:
        pass

    print("\n🔑 Step 2: After approving, Yahoo will provide an authorization code / verification code.")
    auth_code = input("Paste the Authorization Code here: ").strip()

    if not auth_code:
        print("❌ Error: No authorization code entered.")
        sys.exit(1)

    print("\n⏳ Exchanging authorization code for OAuth2 tokens...")
    try:
        tokens = client.exchange_code_for_token(auth_code)
        print("✅ Success! OAuth2 tokens acquired and cached successfully.")
        print(f"Token cache file: {TOKEN_CACHE_FILE}")

        # Test fetching leagues
        print("\n🏈 Testing Connection: Fetching your active Yahoo leagues...")
        leagues = client.get_user_leagues()
        if leagues:
            print(f"Found {len(leagues)} active league(s):")
            for idx, lg in enumerate(leagues, 1):
                print(f"  {idx}. {lg.get('name')} (ID: {lg.get('league_id')}, Season: {lg.get('season')}, Scoring: {lg.get('scoring_type')})")
        else:
            print("Connected successfully! (No active NFL leagues found or season not started yet).")
    except Exception as e:
        print(f"❌ Authentication Failed: {e}")
        sys.exit(1)

    print("\n🎉 Setup complete! Launch the Streamlit dashboard: streamlit run dashboard.py")

if __name__ == "__main__":
    main()
