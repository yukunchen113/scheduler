import dataclasses
from datetime import datetime, timedelta
from typing import Optional, Union

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
    return TaskGroup(tasks=tasks, start=start, end=end)


def get_task_unique_key(task: Task) -> tuple:
    subtask_keys = tuple(
        (get_task_unique_key(subtask) for subtask in taskgroup.tasks)
        for taskgroup in task.subtaskgroups
    )
    return (task.name, subtask_keys)


def correct_timing_in_taskgroups(
    timing_tasks: list[Task], taskgroups: list[TaskGroup]
) -> list[TaskGroup]:
    """If times in the timings have changed,
    this will correct them in the taskgroups.
    """
    desired_times: dict[tuple, list[tuple[int, list[TaskGroup]]]] = {}
    for task in timing_tasks:
        key = get_task_unique_key(task)
        if key not in desired_times:
            desired_times[key] = []
        desired_times[key].append((task.time, task.subtaskgroups))

    for taskgroup in taskgroups:
        new_tasks = []
        for task in taskgroup.tasks:
            key = get_task_unique_key(task)
            if key in desired_times and desired_times[key]:
                task_times = [i[0] for i in desired_times[key]]
                if task.end_diff:
                    # if task is already done, then don't change the time
                    if task.time in task_times:
                        tasktime = task_times.index(task.time)
                        desired_times[key].pop(tasktime)
                    else:
                        # if task is done and no time is found in timings,
                        # pop first occurance
                        desired_times[key].pop(0)
                else:
                    # change the times
                    # process subtasks:
                    timing_taskgroups = desired_times[key][0][1]
                    timing_tasks = []
                    for timing_taskgroup in timing_taskgroups:
                        timing_tasks += timing_taskgroup.tasks
                    subtaskgroups = correct_timing_in_taskgroups(
                        timing_tasks, task.subtaskgroups
                    )
                    # change times
                    task = dataclasses.replace(
                        task, time=task_times[0], subtaskgroups=subtaskgroups
                    )
                    # key doesn't change here, since we are not changing the key
                    desired_times[key].pop(0)
            new_tasks.append(task)
        taskgroup.tasks = new_tasks
    return taskgroups


def correct_deleted_and_added_timings_in_taskgroup(
    timing_tasks: list[Task], taskgroups: list[TaskGroup]
) -> list[TaskGroup]:
    # additional timings - add to end
    # unique key for distinuishing between different tasks are (description, minutes)
    # note there can be more than 1 of the same task
    timing_tasks_counts: dict[str, list[tuple[int, list[TaskGroup]]]] = {}
    for task in timing_tasks:
        key = task.name
        if not key in timing_tasks_counts:
            timing_tasks_counts[key] = []
        timing_tasks_counts[key].append((task.time, task.subtaskgroups))

    for taskgroup in taskgroups:
        new_tasks = []
        for task in taskgroup.tasks:
            # correct subtasks first, as they will affect the unique key
            key = task.name
            # deleted timings
            if not key in timing_tasks_counts or not timing_tasks_counts[key]:
                # check if any are missing
                # subtract last occurances
                if task.start_diff or task.end_diff:
                    # don't delete already done/started tasks
                    new_tasks.append(task)
            else:
                _, timing_subtaskgroups = timing_tasks_counts[key].pop(0)
                timing_subtasks = []
                for timing_subtaskgroup in timing_subtaskgroups:
                    timing_subtasks += timing_subtaskgroup.tasks
                subtaskgroups = correct_deleted_and_added_timings_in_taskgroup(
                    timing_subtasks,
                    task.subtaskgroups,
                )
                new_tasks.append(
                    dataclasses.replace(
                        task,
                        subtaskgroups=subtaskgroups,
                    )
                )
        taskgroup.tasks = new_tasks

    # check if any are added
    extra_tasks = [
        Task(name=name, time=minutes, subtaskgroups=subtaskgroups)
        for name, minutes_list in timing_tasks_counts.items()
        for minutes, subtaskgroups in minutes_list
    ]
    if not taskgroups:
        taskgroups = [TaskGroup(tasks=extra_tasks)]
    else:
        taskgroups[-1].tasks += extra_tasks
    return taskgroups


def sync_taskgroups_with_timing(
    timings: list[TimingConfig], taskgroups: list[TaskGroup]
) -> list[TaskGroup]:
    # additional timings - add to end
    timing_tasks: list[Task] = [
        k for k in get_taskgroup_from_timing_configs(timings).tasks
    ]
    taskgroups = correct_deleted_and_added_timings_in_taskgroup(
        timing_tasks, taskgroups
    )
    # correct the task.times in the taskgroups
    taskgroups = correct_timing_in_taskgroups(timing_tasks, taskgroups)
    # recalculate start and ends
    taskgroups = calculate_times_in_taskgroup_list(taskgroups)
    return taskgroups


def calculate_tasks_with_start_end_using_start(
    tasks: list[Task], default_start_time: Optional[datetime] = None
) -> list[Task]:
    if default_start_time is None:
        start_time = datetime.now()
        start_time = start_time.replace(hour=7, minute=30, second=0, microsecond=0)
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
    if taskgroup.end is not None:
        tasks = calculate_tasks_with_start_end_using_end(taskgroup.tasks, taskgroup.end)
    else:
        tasks = calculate_tasks_with_start_end_using_start(
            taskgroup.tasks, taskgroup.start or default_start_time
        )
    return dataclasses.replace(taskgroup, tasks=tasks)


def calculate_times_in_taskgroup_list(
    taskgroups: list[TaskGroup], default_start_time: Optional[datetime] = None
) -> list[TaskGroup]:
    newtgs = []
    start_time = default_start_time
    for taskgroup in taskgroups:
        newtg = calculate_times_in_taskgroup(taskgroup, start_time)
        if len(newtg.tasks):
            assert newtg.tasks[-1].start
            start_time = newtg.tasks[-1].start + timedelta(minutes=newtg.tasks[-1].time)
            newtgs.append(newtg)
    return newtgs
