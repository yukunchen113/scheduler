import dataclasses
from datetime import datetime
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
    start: Optional[datetime] = None
    end: Optional[datetime] = None

    def __post_init__(self):
        assert (
            self.start is None or self.end is None
        ), "can not specify both start and end"


def get_all_tasks_in_taskgroups(taskgroups: list[TaskGroup]):
    """Gets all tasks and subtasks in taskgroups"""
    tasks = []
    for taskgroup in taskgroups:
        for task in taskgroup.tasks:
            tasks+=get_all_tasks_in_taskgroups(task.subtaskgroups)
            tasks.append(task)
    return tasks
