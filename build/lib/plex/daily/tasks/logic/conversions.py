from datetime import datetime
from collections import defaultdict

from plex.daily.tasks import Task, TaskGroup
from plex.daily.timing.base import TimingConfig


def get_taskgroups_from_timing_configs(
    timing_configs: list[TimingConfig],
    uuid_count:dict[str, int] = defaultdict(lambda: 0)
) -> list[TaskGroup]:
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
                uuid=f"{timing_config.uuid}:{midx}",
                subtaskgroups=(
                    []
                    if timing_config.subtimings is None
                    else get_taskgroups_from_timing_configs(timing_config.subtimings)
                ),
            )
            for midx, minutes in enumerate(timing_config.timings, uuid_count[timing_config.uuid])
        ]
        uuid_count[timing_config.uuid] += len(timing_config.timings)
        if timing_config.set_time:
            if timing_config.set_time.is_start:
                new_taskgroup = TaskGroup(
                    tasks=tasks, user_specified_start=timing_config.set_time.datetime
                )
            else:
                new_taskgroup = TaskGroup(
                    tasks=tasks, user_specified_end=timing_config.set_time.datetime
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
