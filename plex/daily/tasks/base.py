import dataclasses
from datetime import datetime, timedelta
from typing import Optional, TypedDict, Any
import uuid


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

    uuid: str = ""
    # this uuid is regenerated whenever a new task is created.
    # this will not be persisted
    # this means that whenever a config is read, this uuid will change.
    # this uuid is also not used in Task comparisons and is only used
    # when explicitly specified.

    def __post_init__(self):
        object.__setattr__(self, "uuid", str(uuid.uuid4()))

    def __eq__(self, __o: object) -> bool:
        return (
            type(self) == type(__o)
            and self.name == __o.name
            and self.time == __o.time
            and self.subtaskgroups == __o.subtaskgroups
            and self.notes == __o.notes
        )


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
        if self.tasks[-1].end_diff is not None and self.tasks[-1].end_diff < 0:
            end = self.tasks[-1].end - timedelta(minutes=self.tasks[-1].end_diff)
        else:
            end = self.tasks[-1].end
        if self.user_specified_end is not None:
            end = max(self.user_specified_end, end)
        return end

    @property
    def is_empty(self):
        return not len(self.tasks)


def get_all_tasks_in_taskgroups(taskgroups: list[TaskGroup]) -> list[Task]:
    """Gets all tasks and subtasks in taskgroups"""
    tasks = []
    for taskgroup in taskgroups:
        for task in taskgroup.tasks:
            tasks += get_all_tasks_in_taskgroups(task.subtaskgroups)
            tasks.append(task)
    return tasks


def update_taskgroups_with_changes(
    taskgroups: list[TaskGroup], changes: dict[str, dict[str, Any]]
) -> list[TaskGroup]:
    # validate
    for taskgroup in taskgroups:
        new_tasks = []
        for task in taskgroup.tasks:
            update_taskgroups_with_changes(task.subtaskgroups, changes)
            if task.uuid in changes:
                task = dataclasses.replace(task, **changes[task.uuid])
            new_tasks.append(task)
        taskgroup.tasks = new_tasks
    return taskgroups
