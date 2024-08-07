from collections import defaultdict
from datetime import datetime
from typing import Optional

from plex.daily.tasks import Task, TaskGroup
from plex.daily.timing.base import TimingConfig


def get_timing_uuid_from_task_uuid(task_uuid: str) -> tuple[str, int]:
    timing_uuid, index = task_uuid.split(":")
    return timing_uuid, int(index)


def get_task_uuid_from_timing_uuid(timing_uuid: str, index: int) -> str:
    return f"{timing_uuid}:{index}"


def get_taskgroups_from_timing_configs(
    timing_configs: list[TimingConfig], uuid_count: Optional[dict[str, int]] = None
) -> list[TaskGroup]:
    if uuid_count is None:
        uuid_count = defaultdict(lambda: 0)
    taskgroups: list[TaskGroup] = []
    tasks: list[Task] = []
    for timing_config in timing_configs:
        if timing_config.set_time and tasks:
            taskgroups.append(TaskGroup(tasks=tasks))
            tasks = []
        tasks += [
            Task(
                name=timing_config.task_description,
                time=minutes,
                uuid=get_task_uuid_from_timing_uuid(timing_config.uuid, midx),
                subtaskgroups=(
                    []
                    if timing_config.subtimings is None
                    else get_taskgroups_from_timing_configs(
                        timing_config.subtimings, uuid_count
                    )
                ),
                source_str=timing_config.source_str,
                is_source_timing=True,
            )
            for midx, minutes in enumerate(
                timing_config.timings, uuid_count[timing_config.uuid]
            )
        ]
        uuid_count[timing_config.uuid] += len(timing_config.timings)
        if timing_config.set_time:
            if timing_config.set_time.is_start:
                new_taskgroup = TaskGroup(
                    tasks=tasks,
                    user_specified_start=timing_config.set_time.datetime,
                    is_user_specified_start_source_str_timing=True,
                )
            else:
                new_taskgroup = TaskGroup(
                    tasks=tasks,
                    user_specified_end=timing_config.set_time.datetime,
                    is_user_specified_end_source_str_timing=True,
                )

            taskgroups.append(new_taskgroup)
            tasks = []
    if tasks:
        taskgroups.append(TaskGroup(tasks))

    # only sort the time specified taskgroups:
    timed_tgs, timed_tg_idx = [], []
    for tgidx, taskgroup in enumerate(taskgroups):
        if taskgroup.start:
            timed_tgs.append(taskgroup)
            timed_tg_idx.append(tgidx)
    timed_tgs = sorted(timed_tgs, key=lambda x: x.start or datetime.now().astimezone())
    for idx, taskgroup in zip(timed_tg_idx, timed_tgs):
        taskgroups[idx] = taskgroup
    return taskgroups
