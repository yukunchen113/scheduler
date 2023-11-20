import dataclasses
from datetime import datetime, timedelta
from typing import Optional

from plex.daily.tasks import Task, TaskGroup
from plex.daily.tasks.base import DEFAULT_START_TIME


def calculate_tasks_with_start_end_using_start(
    tasks: list[Task], default_start_time: Optional[datetime] = None
) -> list[Task]:
    if default_start_time is None:
        start_time = datetime.now().astimezone()
        start_time = start_time.replace(**DEFAULT_START_TIME)
    else:
        start_time = default_start_time
    new_seq = []
    for task in tasks:
        if task.start_diff is not None:
            start_time += timedelta(minutes=task.start_diff)
        end_time = start_time + timedelta(minutes=task.time)
        subtaskgroups = calculate_times_in_taskgroup_list(
            task.subtaskgroups, start_time
        )
        new_seq.append(
            dataclasses.replace(
                task,
                start=start_time,
                # add end diff for readability, but don't use it for next task calculation
                end=end_time
                + timedelta(minutes=0 if task.end_diff is None else task.end_diff),
                subtaskgroups=subtaskgroups,
            )
        )
        start_time = end_time
        if task.end_diff is not None and task.end_diff > 0:
            start_time += timedelta(minutes=task.end_diff)
    return new_seq


def calculate_tasks_with_start_end_using_end(
    tasks: list[Task], end_time: datetime
) -> list[Task]:
    """End times are pre-diff modification (start_diff, end_diff), so
    unlike calculate_tasks_with_start_end_using_start, this function
    will not use end_times as an absolute spec.
    """
    if not tasks:
        return []
    new_seq = []
    for task in tasks[::-1]:
        start_time = end_time - timedelta(minutes=task.time)
        subtaskgroups = calculate_times_in_taskgroup_list(
            task.subtaskgroups, start_time
        )
        new_seq.append(
            dataclasses.replace(
                task, start=start_time, end=end_time, subtaskgroups=subtaskgroups
            )
        )
        end_time = start_time
    new_seq = new_seq[::-1]
    return calculate_tasks_with_start_end_using_start(new_seq, new_seq[0].start)


def calculate_times_in_taskgroup(
    taskgroup: TaskGroup, default_start_time: Optional[datetime] = None
) -> TaskGroup:
    if taskgroup.user_specified_end is not None:
        tasks = calculate_tasks_with_start_end_using_end(
            taskgroup.tasks, taskgroup.user_specified_end)
    else:
        tasks = calculate_tasks_with_start_end_using_start(
            taskgroup.tasks, taskgroup.user_specified_start or default_start_time
        )
    return dataclasses.replace(taskgroup, tasks=tasks)


def calculate_times_in_taskgroup_list(
    taskgroups: list[TaskGroup], default_start_time: Optional[datetime] = None
) -> list[TaskGroup]:
    newtgs = []
    start_time = default_start_time
    for taskgroup in taskgroups:
        newtg = calculate_times_in_taskgroup(taskgroup, start_time)
        if not newtg.is_empty:
            assert newtg.end
            start_time = newtg.end
            newtgs.append(newtg)
    return newtgs
