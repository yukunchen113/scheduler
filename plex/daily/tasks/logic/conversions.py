from datetime import datetime
from typing import Optional

from plex.daily.tasks import Task, TaskGroup
from plex.daily.timing import TimingConfig


def get_taskgroup_from_timing_configs(
    timing_configs: list[TimingConfig],
    start: Optional[datetime] = None,
    end: Optional[datetime] = None,
) -> TaskGroup:
    tasks = []
    for timing_config in timing_configs:
        tasks += [
            Task(
                name=timing_config.task_description,
                time=minutes,
                subtaskgroups=(
                    []
                    if timing_config.subtimings is None
                    else [get_taskgroup_from_timing_configs(timing_config.subtimings)]
                ),
            )
            for minutes in timing_config.timings
        ]
    return TaskGroup(tasks=tasks, user_specified_start=start, user_specified_end=end)
