import dataclasses
from collections import namedtuple
from datetime import datetime
from typing import Optional

from plex.daily.tasks import Task, TaskGroup
from plex.daily.tasks.base import add_tasks, pop_task
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.tasks.logic.conversions import get_taskgroups_from_timing_configs
from plex.daily.timing.base import TimingConfig


def correct_timing_in_taskgroups(
    timing_tasks: list[Task], taskgroups: list[TaskGroup]
) -> list[TaskGroup]:
    """If times in the timings have changed,
    this will correct them in the taskgroups.
    """
    desired_times: dict[str, list[tuple[int, list[TaskGroup]]]] = {}
    for task in timing_tasks:
        key = task.uuid
        if key not in desired_times:
            desired_times[key] = []
        desired_times[key].append((task.time, task.subtaskgroups))

    for taskgroup in taskgroups:
        new_tasks = []
        for task in taskgroup.tasks:
            key = task.uuid
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


CarriedOverFields = namedtuple(
    "CarriedOverFields",
    ["name", "time", "subtaskgroups", "uuid", "source_str", "is_source_timing"],
)


def correct_deleted_and_added_timings_in_taskgroup(
    timing_tasks: list[Task],
    taskgroups: list[TaskGroup],
    timing_tasks_counts: Optional[dict[str, list[CarriedOverFields]]] = None,
) -> list[TaskGroup]:
    # additional timings - add to end
    # unique key for distinuishing between different tasks are (description, minutes)
    # note there can be more than 1 of the same task
    if timing_tasks_counts is None:
        timing_tasks_counts: dict[
            str, list[CarriedOverFields]
        ] = {}  # must be ordered dictionary to keep timing add order.
    parent_uuids = {task_uuid for task_uuid in timing_tasks_counts.keys()}
    for task in timing_tasks:
        key = task.uuid
        if not key in timing_tasks_counts:
            timing_tasks_counts[key] = []
        timing_tasks_counts[key].append(
            CarriedOverFields(
                name=task.name,
                time=task.time,
                subtaskgroups=task.subtaskgroups,
                uuid=task.uuid,
                source_str=task.source_str,
                is_source_timing=task.is_source_timing,
            )
        )

    for taskgroup in taskgroups:
        new_tasks = []
        for task in taskgroup.tasks:
            key = task.uuid
            # deleted timings
            if key not in timing_tasks_counts or not timing_tasks_counts[key]:
                # check if any are missing
                # subtract last occurances
                if task.start_diff or task.end_diff:
                    # don't delete already done/started tasks
                    new_tasks.append(task)
            else:
                cur_task = timing_tasks_counts[key].pop(0)
                timing_subtaskgroups = cur_task.subtaskgroups
                timing_subtasks = []
                for timing_subtaskgroup in timing_subtaskgroups:
                    timing_subtasks += timing_subtaskgroup.tasks
                subtaskgroups = correct_deleted_and_added_timings_in_taskgroup(
                    timing_subtasks, task.subtaskgroups, timing_tasks_counts
                )
                new_tasks.append(
                    dataclasses.replace(
                        task,
                        name=cur_task.name,
                        time=cur_task.time,
                        subtaskgroups=subtaskgroups,
                    )
                )
        taskgroup.tasks = new_tasks

    # check if any are added
    extra_tasks = []
    for task_uuid in list(timing_tasks_counts.keys()):
        if task_uuid in parent_uuids:
            continue
        minutes_list = timing_tasks_counts.pop(task_uuid)
        extra_tasks += [
            Task(
                name=name,
                time=minutes,
                subtaskgroups=subtaskgroups,
                uuid=task_uuid,
                source_str=source_str,
                is_source_timing=is_source_timing,
            )
            for name, minutes, subtaskgroups, task_uuid, source_str, is_source_timing in minutes_list
        ]
    if not taskgroups:
        taskgroups = [TaskGroup(tasks=extra_tasks)]
    else:
        taskgroups[-1].tasks += extra_tasks
    return taskgroups


def sync_taskgroups_with_timing(
    timings: list[TimingConfig],
    taskgroups: list[TaskGroup],
    start_datetime: Optional[datetime] = None,
) -> list[TaskGroup]:
    # additional timings - add to end
    timing_tasks: list[Task] = [
        task
        for taskg in get_taskgroups_from_timing_configs(timings)
        for task in taskg.tasks
    ]
    taskgroups = correct_deleted_and_added_timings_in_taskgroup(
        timing_tasks, taskgroups
    )
    # correct the task.times in the taskgroups
    taskgroups = correct_timing_in_taskgroups(timing_tasks, taskgroups)
    # recalculate start and ends
    taskgroups = calculate_times_in_taskgroup_list(taskgroups, start_datetime)

    return taskgroups


def append_overlap_tasks_to_end(taskgroups: list[TaskGroup]) -> list[TaskGroup]:
    """
    Appends the overlapping times to end of taskgroup list
    """
    return taskgroups  # not done for now
    # preprocess
    for idx, tgroup in enumerate(taskgroups[:-1]):
        ntgroup = taskgroups[idx + 1]
        assert tgroup.start <= ntgroup.start
        if tgroup.end > ntgroup.start:  # overlap
            if ntgroup.user_specified_start and tgroup.user_specified_end:  # swap
                taskgroups[idx], taskgroups[idx + 1] = ntgroup, tgroup

    overlap = []
    for idx, tgroup in enumerate(taskgroups[:-1]):
        ntgroup = taskgroups[idx + 1]
        while (
            tgroup.tasks and ntgroup.tasks and tgroup.end > ntgroup.start
        ):  # overlap detected
            retain_one_item = not (
                (len(ntgroup.tasks) == 1 or ntgroup.user_specified_start)
                and (len(tgroup.tasks) == 1 or tgroup.user_specified_end)
            )
            # try to pop first
            if not (
                tgroup.user_specified_end or len(tgroup.tasks) == 1 and retain_one_item
            ):
                overlap.append(pop_task(tgroup))
            # try to pop second
            if not (
                ntgroup.user_specified_start
                or len(ntgroup.tasks) == 1
                and retain_one_item
            ):
                overlap.append(pop_task(tgroup))
    if overlap:
        taskgroups.append(TaskGroup(overlap))

    # remove empty taskgroups
    return [tgroup for i in taskgroups if tgroup.tasks]
