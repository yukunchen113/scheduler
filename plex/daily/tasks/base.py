import dataclasses
from datetime import datetime, timedelta
from typing import Optional, TypedDict

class TimeType(TypedDict):
    hour: int
    minute: int
    second: int
    microsecond: int

DEFAULT_START_TIME: TimeType = dict(hour=7, minute=30, second=0, microsecond=0)

@dataclasses.dataclass(frozen=True)
class Task:
    name: str
    time: int
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    start_diff: Optional[int] = None
    end_diff: Optional[int] = None
    subtaskgroups: list["TaskGroup"] = dataclasses.field(default_factory=list)
    notes: str = ""


@dataclasses.dataclass
class TaskGroup:
    tasks: list[Task]
    user_specified_start: Optional[datetime] = None
    user_specified_end: Optional[datetime] = None

    def __post_init__(self):
        assert (
            self.user_specified_start is None or self.user_specified_end is None
        ), "can not specify both start and end"
    @property
    def start(self):
        assert self.tasks, "task list is empty"
        return self.user_specified_start or self.tasks[0].start

    @property
    def end(self):
        # calculate end without end diff
        assert self.tasks, "task list is empty"
        last_task_end = self.tasks[-1].start + \
                timedelta(minutes=self.tasks[-1].time)
        return self.user_specified_end or last_task_end

    @property
    def is_empty(self):
        return not len(self.tasks)

def get_all_tasks_in_taskgroups(taskgroups: list[TaskGroup]):
    """Gets all tasks and subtasks in taskgroups"""
    tasks = []
    for taskgroup in taskgroups:
        for task in taskgroup.tasks:
            tasks+=get_all_tasks_in_taskgroups(task.subtaskgroups)
            tasks.append(task)
    return tasks
