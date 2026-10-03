import json
import os
import pickle
import shutil

from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from plex.config import get_credentials_path, get_token_json_path, get_token_pickle_path

SCOPES = [
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/tasks",
]


def authenticate(credentials_path: str = None) -> None:
    """Refreshes and authenticates Google Calendar and Google Tasks OAuth credentials."""
    client_secrets = credentials_path or get_credentials_path()
    token_json = get_token_json_path()
    token_pickle = get_token_pickle_path()

    if not os.path.exists(client_secrets):
        raise FileNotFoundError(
            f"OAuth client secrets file not found at '{client_secrets}'. "
            "Please download credentials.json from Google Cloud Console or run 'plex setup'."
        )

    # Ensure target directory exists
    os.makedirs(os.path.dirname(token_json), exist_ok=True)
    os.makedirs(os.path.dirname(token_pickle), exist_ok=True)

    # Backup existing tokens if present
    if os.path.exists(token_json):
        shutil.copyfile(token_json, token_json + ".bak")
        print(f"Backed up {token_json} to {token_json}.bak")
    if os.path.exists(token_pickle):
        shutil.copyfile(token_pickle, token_pickle + ".bak")
        print(f"Backed up {token_pickle} to {token_pickle}.bak")

    print("\nStarting Google OAuth authentication flow...")
    print("Requested scopes:")
    for scope in SCOPES:
        print(f"  - {scope}")

    flow = InstalledAppFlow.from_client_secrets_file(client_secrets, SCOPES)
    creds = flow.run_local_server(port=0)

    # Save Google Tasks token as JSON
    with open(token_json, "w") as f:
        f.write(creds.to_json())
    print(f"Saved {token_json}")

    # Save Google Calendar token as pickle (used by gcsa)
    with open(token_pickle, "wb") as f:
        pickle.dump(creds, f)
    print(f"Saved {token_pickle}")

    print("\nVerifying Google Tasks API access...")
    try:
        tasks_service = build("tasks", "v1", credentials=creds)
        tasklists = tasks_service.tasklists().list(maxResults=5).execute()
        print(
            f"Tasks check: Success! Found {len(tasklists.get('items', []))} tasklist(s)."
        )
    except Exception as err:
        print(f"Warning: Tasks API verification returned an error: {err}")

    print("Verifying Google Calendar API access...")
    try:
        cal_service = build("calendar", "v3", credentials=creds)
        cals = cal_service.calendarList().list(maxResults=5).execute()
        print(
            f"Calendar check: Success! Found {len(cals.get('items', []))} calendar(s)."
        )
    except Exception as err:
        print(f"Warning: Calendar API verification returned an error: {err}")

    print("\nGoogle API tokens successfully refreshed and ready to use!")


if __name__ == "__main__":
    authenticate()
