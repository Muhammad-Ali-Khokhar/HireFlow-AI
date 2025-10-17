from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
import os

# All required scopes
SCOPES = [
    'https://www.googleapis.com/auth/gmail.send',
    'https://www.googleapis.com/auth/calendar.events',
    'https://www.googleapis.com/auth/calendar',
    'https://www.googleapis.com/auth/gmail.modify',
    'https://www.googleapis.com/auth/gmail.readonly',
    'https://www.googleapis.com/auth/gmail.compose',
    'https://www.googleapis.com/auth/gmail.metadata',
    'https://www.googleapis.com/auth/gmail.settings.basic',
    'https://www.googleapis.com/auth/calendar.acls',
    'https://www.googleapis.com/auth/calendar.readonly'
]

TOKEN_PATH = 'token.json'
CRED_PATH = 'credentials.json'

def main():
    try:
        creds = None

        # Load existing token if present
        if os.path.exists(TOKEN_PATH):
            creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)

        # Check if token is missing, invalid, or missing scopes
        if not creds or not creds.valid or not creds.has_scopes(SCOPES):
            print("[auth_gmail] Token missing or incomplete, forcing re-authentication...")

            # Remove old token to ensure full re-consent
            if os.path.exists(TOKEN_PATH):
                os.remove(TOKEN_PATH)
                print(f"[auth_gmail] Old {TOKEN_PATH} deleted")

            if not os.path.exists(CRED_PATH):
                raise FileNotFoundError(f"[auth_gmail] {CRED_PATH} not found")

            # Start OAuth flow
            flow = InstalledAppFlow.from_client_secrets_file(CRED_PATH, SCOPES)
            flow.redirect_uri = 'http://localhost:8080/'
            creds = flow.run_local_server(
                port=8080,
                access_type='offline',
                prompt='consent'  # Force full consent every time scopes change
            )

            # Save the new token
            with open(TOKEN_PATH, 'w') as token:
                token.write(creds.to_json())
            print(f"[auth_gmail] New token saved with all scopes: {TOKEN_PATH}")
        else:
            print("[auth_gmail] Valid token found with all required scopes")

        # Final confirmation of scopes
        print(f"[auth_gmail] Active token scopes: {creds.scopes}")

    except Exception as e:
        print(f"[auth_gmail] Error during authentication: {e}")
        raise


if __name__ == '__main__':
    main()
