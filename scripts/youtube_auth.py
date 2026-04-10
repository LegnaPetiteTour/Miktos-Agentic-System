"""
YouTube OAuth2 Authorization — run once to get a refresh token.

Usage:
  python scripts/youtube_auth.py --channel en
  python scripts/youtube_auth.py --channel fr

This opens a browser window for YouTube authorization.
After approval, prints the refresh token — copy it to .env as
YOUTUBE_REFRESH_TOKEN_EN or YOUTUBE_REFRESH_TOKEN_FR.

Required in .env before running:
  YOUTUBE_CLIENT_ID
  YOUTUBE_CLIENT_SECRET

These come from a Google Cloud OAuth2 Desktop App credential.
Create at: https://console.cloud.google.com/apis/credentials
Scopes required: youtube.force-ssl (for video update + playlist)

The script never stores credentials itself — it only prints the
refresh token for the operator to copy into .env.
"""

import argparse
import os
import sys

from dotenv import load_dotenv

load_dotenv()

_SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
_TOKEN_URI = "https://oauth2.googleapis.com/token"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Obtain a YouTube OAuth2 refresh token for .env"
    )
    parser.add_argument(
        "--channel",
        choices=["en", "fr"],
        required=True,
        help="Which channel to authorize (en or fr)",
    )
    args = parser.parse_args()

    client_id = os.environ.get("YOUTUBE_CLIENT_ID", "")
    client_secret = os.environ.get("YOUTUBE_CLIENT_SECRET", "")

    if not client_id or not client_secret:
        print(
            "Error: YOUTUBE_CLIENT_ID and YOUTUBE_CLIENT_SECRET must be set in .env\n"
            "Create OAuth2 Desktop App credentials at:\n"
            "  https://console.cloud.google.com/apis/credentials",
            file=sys.stderr,
        )
        sys.exit(1)

    try:
        from google_auth_oauthlib.flow import InstalledAppFlow
    except ImportError:
        print(
            "Error: google-auth-oauthlib not installed.\n"
            "Run: pip install google-auth-oauthlib",
            file=sys.stderr,
        )
        sys.exit(1)

    client_config = {
        "installed": {
            "client_id": client_id,
            "client_secret": client_secret,
            "redirect_uris": ["urn:ietf:wg:oauth:2.0:oob", "http://localhost"],
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": _TOKEN_URI,
        }
    }

    flow = InstalledAppFlow.from_client_config(client_config, scopes=_SCOPES)

    print(
        f"\nAuthorizing YouTube channel: {args.channel.upper()}\n"
        "A browser window will open. Log in with the account that owns "
        f"the {args.channel.upper()} channel.\n"
    )

    credentials = flow.run_local_server(port=0, open_browser=True)

    refresh_token = credentials.refresh_token
    env_key = (
        "YOUTUBE_REFRESH_TOKEN_EN" if args.channel == "en"
        else "YOUTUBE_REFRESH_TOKEN_FR"
    )

    print("\nAuthorization successful!\n")
    print("Add this to your .env file:\n")
    print(f"  {env_key}={refresh_token}\n")
    print(
        "Keep this token secret — it grants access to manage your YouTube channel.\n"
        "If you need to revoke it: https://myaccount.google.com/permissions"
    )


if __name__ == "__main__":
    main()
