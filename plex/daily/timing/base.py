from datetime import datetime
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class SetTime:
    datetime: datetime
    is_start: bool = True


@dataclass(frozen=True)
class TimingConfig:
    task_description: str
    timings: list[int]
    subtimings: Optional[list["TimingConfig"]] = None
    set_time: Optional[SetTime] = None
