""" 
Defines functions for pushing notes to the google tasks
"""
from plex.daily.tasks.base import TaskGroup, Task
from datetime import datetime, date
from typing import TypedDict, Optional
from dataclasses import dataclass
from collections import defaultdict
import re
from plex.notion_api.page import update_task_set, NotionContent, NotionType, NotionContentGroup, delete_block
from plex.daily.cache import save_to_cache, load_from_cache

def sync_tasks_todo(taskgroups: list[TaskGroup]) -> None:
    """Syncs with notion tasks"""
    refresh_tasks_tasklists(taskgroups)

def refresh_tasks_tasklists(taskgroups: list[TaskGroup]) -> None:
    """Push notes to notion tasks"""
    
    # get current task, next task
    ctime = datetime.now()
    ctime = datetime(2024, 7, 17).replace(hour=9, minute=35).astimezone()
    ctasks, ntasks = [], []
    def get_relevant_tasks(taskgroups: list[TaskGroup]) -> str:
        for taskgroup in taskgroups:
            for tidx,task in enumerate(taskgroup.tasks): # flatten tasks
                if task.start <= ctime <= task.end:
                    ctasks.append(task)
                    if tidx+1 < len(taskgroup.tasks):
                        ntasks.append(taskgroup.tasks[tidx+1])
                    get_relevant_tasks(task.subtaskgroups)
    get_relevant_tasks(taskgroups)
    updater = NotionTasksPageUpdater()
    updater.update_task(ctasks, ntasks)

class NotionTasksPageUpdater:
    
    cache_file = "cache_files/notion_tasks_page_updater.pickle"
    
    def __init__(self) -> None:
        self.headings:dict[str, NotionContent] = {}
        self.next_tasks:dict[str, NotionContentGroup] = {}
        self.current_tasks:dict[str, NotionContentGroup] = {}
        
        # load
        cached_obj = load_from_cache("", self.cache_file)
        if cached_obj:
            self.__dict__.update(cached_obj)
        
    def _get_heading(self, heading_date: date):
        if heading_date not in self.headings:
            self.headings[heading_date] =  NotionContent(
                NotionType.heading_1,
                "",
                heading_date
            )
        return self.headings.get(heading_date)
    
    def _get_next_tasks(self, heading_date: date, ntasks: list[Task]):
        contents = [
            NotionContent(NotionType.paragraph, "Next Task(s):"),
        ] + [
            NotionContent(
                NotionType.bulleted_list_item, 
                ntask.name + " ", 
                ndatetime=ntask.start
            ) for ntask in ntasks
        ]
        if heading_date not in self.next_tasks: # create
            self.next_tasks[heading_date] = NotionContentGroup(
                contents
            )
        else: # update
            self.next_tasks[heading_date].contents = contents # update string
        return self.next_tasks.get(heading_date)
        
    def _resolve_ctask(self, task: Task):
        # TODO: index by name for now, but this should be by uuid in the future.
        task_heading_str = f"{task.name} | Ends "
        todo_strs = re.findall(r"\t*-\s?(.+)", task.notes)
        if task.name not in self.current_tasks: # create
            self.current_tasks[task.name] = NotionContentGroup(
                contents=[
                    NotionContent(
                        NotionType.heading_2,
                        task_heading_str,
                        ndatetime=task.end
                    )
                ] + [
                    NotionContent(
                        NotionType.to_do,
                        todo
                    ) for todo in todo_strs
                ]
            )
        # else: # update
        #     self.current_tasks[task.name].contents = []
            # self.current_tasks[task.name].contents[0].content = task_heading_str
            # existing_todos = {i.content:i for i in self.current_tasks[task.name].contents[1:]}
            # # remove unused strings
            # existing = []
            # for etodo_str, etodo in existing_todos.items():
            #     if etodo_str not in todo_strs:
            #         delete_block(etodo)
            #     else:
            #         existing.append(etodo)
            # # add new strings
            # self.current_tasks[task.name].todos = existing + [
            #     NotionContent(
            #         NotionType.to_do,
            #         todo_str 
            #     )
            #     for todo_str in todo_strs
            #     if todo_str not in existing_todos
            # ]
        ctask = self.current_tasks.get(task.name)
        return ctask
        
    def _make_heading_str_from_task(self, task: Task):
        return task.start.date()
    
    def update_task(self, ctasks: list[Task], ntasks: list[Task]):
        """Updates tasks in notion

        Args:
            ctasks (list[Task]): current tasks
            ntasks (list[Task]): next tasks
        """
        tasks_by_heading = defaultdict(lambda: defaultdict(list)) # heading: {ctasks:[],ntasks:[]}
         
        # gather structure
        for ctask in ctasks:
            tasks_by_heading[ctask.start.date()]["ctasks"].append(ctask)

        for ntask in ntasks:
            tasks_by_heading[ntask.start.date()]["ntasks"].append(ntask)
        
        # create
        for heading_date, tasks in tasks_by_heading.items():
            heading = self._get_heading(heading_date)
            next_tasks = self._get_next_tasks(heading_date, tasks.get("ntasks"))
            update_task_set(
                heading,
                next_tasks,
                [self._resolve_ctask(ctask) for ctask in tasks.get("ctasks")]
            )
        save_to_cache(self.__dict__, "", self.cache_file)