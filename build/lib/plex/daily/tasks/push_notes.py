""" 
Defines functions for pushing notes to the google tasks
"""
from plex.daily.tasks.base import TaskGroup
from datetime import datetime
from typing import TypedDict, Optional
import re
from plex.tasks_api import get_tasklists, put_gtasklists

def sync_tasks_todo(taskgroups: list[TaskGroup]) -> None:
    """Syncs with google tasks"""
    # refresh_google_tasks_tasklists(taskgroups)

def refresh_google_tasks_tasklists(taskgroups: list[TaskGroup]) -> None:
    """Push notes to google tasks"""
    
    ## Gather new tasks
    # get current task, next task, prev task
    
    # put_task(tasklist_id: str, tasklist_name: str, tasks: list[str], parent: str = "")

    ctime = datetime.now().replace(day=1, hour=9, minute=50).astimezone()
    current_gtasks = {"tasklist_id":"current", "tasklist_name":"", "gtasklists":[]}
    path = []
    def get_current_task(taskgroups: list[TaskGroup]) -> str:
        for taskgroup in taskgroups:
            for task in taskgroup.tasks:
                if task.start <= ctime <= task.end:
                    current_gtasks["tasklist_name"] = task.name if not path else path[0]
                    current_gtasks["gtasklists"].append({
                        "name": task.name,
                        "subtasks": [note for note in re.findall("-\s?(.+)", task.notes)]
                    })
                    path.append(task.name)
                    get_current_task(task.subtaskgroups)
                    path.pop()
    get_current_task(taskgroups)
    put_gtasklists(**current_gtasks)
                    
    
    ## Get current google tasks state
    ## Push new tasks and delete old tasks
    # print(get_tasklists())