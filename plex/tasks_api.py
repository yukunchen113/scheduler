import multiprocessing
import os
import os.path
import time
from functools import cache
from typing import Optional, TypedDict, Union

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# If modifying these scopes, delete the file token.json.
# note: documentation - https://googleapis.github.io/google-api-python-client/docs/dyn/tasks_v1.html
SCOPES = ["https://www.googleapis.com/auth/tasks"]

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
                os.path.join(CREDENTIALS_BASEPATH, "credentials.json"), SCOPES
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


def get_tasks(
    tasklist_name: str, show_completed: bool = False
) -> list[dict[str, Union[list, str]]]:
    """
    Gets tasks to do.
    Will look at the first instance of a tasklist named 'tasklist_name'.
    """

    # Call the Tasks API
    service = get_task_service()
    tasklist = get_tasklist(tasklist_name)
    if not tasklist:
        return []
    results = (
        service.tasks()
        .list(
            tasklist=tasklist["id"],
            showCompleted=show_completed,
            showHidden=show_completed,
        )
        .execute()
    )
    tasks = results.get("items", [])
    # if not show_completed:
    #     tasks = [task for task in tasks if task["status"] == "needsAction"]
    return tasks


def get_tasklists():
    """Gets all tasklists"""
    service = get_task_service()
    results = service.tasklists().list().execute()
    tasklists = results.get("items", [])
    return tasklists


class GTaskList(TypedDict):
    name: str  # name of task.
    subtasks: list[str]  # subtasks of task


def delete_task(tasklist, task):
    service = get_task_service()
    service.tasks().delete(tasklist=tasklist["id"], task=task["id"]).execute()
    print(f"done: {task['title']}")


def put_gtasklists(tasklist_id: str, tasklist_name: str, gtasklists: list[GTaskList]):
    """Creates/updates task (and tasklist if not created already)"""
    ### Get or Create Tasklist ###
    tasklist_title = f"{tasklist_id} - {tasklist_name}"
    service = get_task_service()
    # find tasklist that begins with tasklist_id
    for tasklist in get_tasklists():
        if tasklist["title"].startswith(tasklist_id):
            # update tasklist to new title
            tasklist["title"] = tasklist_title
            service.tasklists().update(tasklist=tasklist["id"], body=tasklist).execute()

    # create tasklist if not found
    tasklist = get_tasklist(tasklist_title)
    if tasklist is None:
        tasklist = service.tasklists().insert(body={"title": tasklist_title}).execute()

    ### Populate with Tasks ###
    # cur tasks
    start_time = time.time()
    cur_tasks = get_tasks(tasklist_title)
    # consolidate cur tasks
    parents = {task["title"]: task["id"] for task in cur_tasks}  # name: id
    parents[""] = ""
    # convert gtaskslists
    new_tasks = []
    for gtasklist in gtasklists:
        new_tasks.append({"title": gtasklist["name"]})
        for subtask in gtasklist["subtasks"]:
            new_tasks.append({"title": subtask, "parent": gtasklist["name"]})

    # identify diff
    old_tasks = []
    for ctask in cur_tasks:
        nchange = len(new_tasks)
        if new_tasks := [
            ntask
            for ntask in new_tasks
            if not (
                ntask["title"] == ctask["title"]
                and (
                    parents[ntask.get("parent", "")]
                    == ctask.get(
                        "parent", ""
                    )  # these parents don't match since one is an id and one is a title
                    or ctask["status"] == "completed"
                )
            )
        ]:
            if len(new_tasks) == nchange:  # task doesn't exist in new_tasks, delete
                old_tasks.append(ctask)
    print(f"getting tasks took {time.time() - start_time} seconds")

    # delete tasks
    start_time = time.time()

    multiprocessing.Pool(10).starmap(
        func=delete_task, iterable=[(tasklist, i) for i in old_tasks]
    )
    print(f"deleting tasks took {time.time() - start_time} seconds")
    start_time = time.time()

    for task in new_tasks:
        if "parent" not in task:
            response = (
                service.tasks().insert(tasklist=tasklist["id"], body=task).execute()
            )
    print(f"inserting parent tasks took {time.time() - start_time} seconds")
    start_time = time.time()

    # regen parents
    parents = {
        task["title"]: task["id"] for task in get_tasks(tasklist_title)
    }  # name: id
    parents[""] = ""

    # assign children
    for task in new_tasks:
        if "parent" in task:
            response = (
                service.tasks().insert(tasklist=tasklist["id"], body=task).execute()
            )
            service.tasks().move(
                tasklist=tasklist["id"],
                task=response["id"],
                parent=parents[task["parent"]],
            ).execute()
    print(f"inserting and moving child tasks took {time.time() - start_time} seconds")

    # # get current tasks
    # parents = {}
    # for task in get_tasks(tasklist_title):
    #     if [
    #         ntask for ntask in new_tasks
    #         if ntask["title"] == task["title"]
    #         and (
    #             ntask.get("parent", "") == task.get("parent", "") # these parents don't match since one is an id and one is a title
    #             or task["status"] == "completed")
    #     ]:
    #         new_tasks = [
    #             ntask for ntask in new_tasks
    #             if ntask["title"] != task["title"]
    #             or ntask.get("parent", "") != task.get("parent", "")
    #         ]
    #         if not task.get("parent", ""):
    #             parents[task["title"]] = task["id"]
    #     else:
    #         service.tasks().delete(tasklist=tasklist["id"], task=task["id"]).execute()
    # # add new tasks
    # for task in sorted(new_tasks, key=lambda x: x.get("parent", "")):
    #     if "parent" not in task:
    #         response = service.tasks().insert(tasklist=tasklist["id"], body=task).execute()
    #         parents[response["title"]] = response["id"]
    #     else:
    #         response = service.tasks().insert(
    #             tasklist=tasklist["id"],
    #             body=task
    #         ).execute()
    #         service.tasks().move(
    #             tasklist=tasklist["id"],
    #             task=response["id"],
    #             parent=parents[task["parent"]]
    #         ).execute()
