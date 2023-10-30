import dataclasses
from datetime import datetime
from typing import Optional


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
