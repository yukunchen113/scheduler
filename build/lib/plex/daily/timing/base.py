from datetime import datetime
from dataclasses import dataclass
from typing import Optional
import re


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
    uuid: Optional[str] = None
    
    # these parameters are for string reconstruction
    raw_description: str = ""
    raw_timespec: str = ""
    
    