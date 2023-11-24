from datetime import datetime

from plex.daily.tasks import Task, TaskGroup
from plex.daily.timing.base import TimingConfig


def get_taskgroups_from_timing_configs(
    timing_configs: list[TimingConfig],
) -> list[TaskGroup]:
    taskgroups: list[TaskGroup] = []
    tasks: list[Task] = []
    for timing_config in timing_configs:
        if timing_config.set_time and tasks:
            if not taskgroups:
                taskgroups.append(TaskGroup(tasks=tasks))
            else:
                taskgroups[-1].tasks += tasks
            tasks = []
        tasks += [
            Task(
                name=timing_config.task_description,
                time=minutes,
                subtaskgroups=(
                    []
                    if timing_config.subtimings is None
                    else get_taskgroups_from_timing_configs(timing_config.subtimings)
                ),
            )
            for minutes in timing_config.timings
        ]
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
        if not taskgroups:
            taskgroups.append(TaskGroup(tasks))
        else:
            taskgroups[-1].tasks += tasks

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
