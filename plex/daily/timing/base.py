import re
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional

from plex.transform.base import TransformStr


@dataclass(frozen=True)
class SetTime:
    datetime: datetime
    is_start: bool = True


@dataclass(frozen=True)
class TimingConfig:
    task_description: str
    raw_timings: list[list[int]] = field(default_factory=list)
    subtimings: Optional[list["TimingConfig"]] = None
    set_time: Optional[SetTime] = None
    uuid: Optional[str] = None

    # these parameters are for string reconstruction
    end_line: str = ""
    subtiming_level: int = 0
    source_str: Optional[TransformStr] = None

    @property
    def timings(self):
        return [i for j in self.raw_timings for i in j]


def pack_timing_uuid(section: str, num: int) -> str:
    return f"{section}/{num}"


def unpack_timing_uuid(uuid: str) -> tuple[str, Optional[int]]:
    parts = uuid.split("/")
    if len(parts) == 2:
        return parts[0], int(parts[1])
    else:
        return parts[0], None
