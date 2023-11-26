import os
import os.path
from typing import Union, Optional
from functools import cache

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
SCOPES = ["https://www.googleapis.com/auth/tasks.readonly"]

CREDENTIALS_BASEPATH = os.path.join(os.environ["HOME"], ".credentials/")


@cache
def get_task_service():
    creds = None
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first
    # time.
    credentials_token_file = os.path.join(CREDENTIALS_BASEPATH, "token.json")
    if os.path.exists(credentials_token_file):
        creds = Credentials.from_authorized_user_file(credentials_token_file, SCOPES)
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "/Users/ychen/.credentials/credentials.json", SCOPES
            )
            creds = flow.run_local_server(port=0)
        # Save the credentials for the next run
        with open(credentials_token_file, "w") as token:
            token.write(creds.to_json())
    service = build("tasks", "v1", credentials=creds)
    return service


@cache
def get_tasklist(tasklist_name: str) -> Optional[dict[str, str]]:
    service = get_task_service()
    # Call the Tasks API
    results = service.tasklists().list().execute()
    tasklists = results.get("items", [])

    if tasklists:
        for tasklist in tasklists:
            if tasklist["title"] == tasklist_name:
                return tasklist
    return None


def get_tasks(tasklist_name: str) -> list[dict[str, Union[list, str]]]:
    """
    Gets tasks to do.
    Will look at the first instance of a tasklist named 'tasklist_name'.
    """

    # Call the Tasks API
    service = get_task_service()
    tasklist = get_tasklist(tasklist_name)
    if not tasklist:
        return []
    results = service.tasks().list(tasklist=tasklist["id"]).execute()
    tasks = results.get("items", [])
    return tasks
