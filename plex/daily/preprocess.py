import re
from collections import defaultdict
from typing import Optional

from plex.daily.tasks.base import (
    Task,
    TaskGroup,
    TaskType,
    flatten_taskgroups_into_tasks,
)
from plex.daily.tasks.config import convert_to_string, process_task_line
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.tasks.logic.conversions import (
    get_taskgroups_from_timing_configs,
    get_timing_uuid_from_task_uuid,
)
from plex.daily.template.routines import is_template_line, process_template_lines
from plex.daily.timing.base import TimingConfig, unpack_timing_uuid
from plex.daily.timing.process import (
    convert_timing_to_str,
    gather_existing_uuids_from_lines,
    get_timing_from_lines,
    is_valid_timing_str,
)


def apply_preprocessing(
    timing: list[str], tasks: list[str], datestr: str
) -> tuple[list[str], list[str]]:
    tasks = process_templates(timing, tasks, datestr)
    timing, tasks = process_timings_in_task_section(timing, tasks)
    timing, tasks = remove_timings_given_task_deletion_specification(timing, tasks)
    return timing, tasks


def get_timing_uuid_mapping(timings: list[TimingConfig]):
    timing_map = {}
    for mtiming in timings:
        for timing in [mtiming] + list(
            get_timing_uuid_mapping(mtiming.subtimings).values()
        ):
            if timing.uuid in timing_map:
                raise ValueError(
                    f"Timing uuid {timing.uuid} is found in 2 places. Unable to remove existing tasks."
                )
            timing_map[timing.uuid] = timing
    return timing_map


def remove_timing_index_from_timing(timing_config: TimingConfig, index: int):
    count = 0
    for tidx, timing in enumerate(timing_config.raw_timings):
        for idx, _ in enumerate(timing):
            if count == index:
                timing.pop(idx)
            count += 1
        if not timing:
            timing_config.raw_timings.pop(tidx)


def remove_timings_given_task_deletion_specification(
    timing_lines: list[str], task_lines: list[str]
) -> tuple[list[str], list[str]]:
    timings, timing_lines = get_timing_from_lines(timing_lines)
    cur_timing_map = get_timing_uuid_mapping(timings)
    for line in task_lines:
        task, _ = process_task_line(line, task_type=TaskType.deletion_request)
        if task is None:
            continue
        timing_uuid, index = get_timing_uuid_from_task_uuid(task.uuid)
        cur_timing = cur_timing_map[timing_uuid]
        existing_string = convert_timing_to_str(cur_timing)
        line_num = timing_lines.index(existing_string)
        remove_timing_index_from_timing(cur_timing, index)
        if not cur_timing.timings:
            timing_lines.pop(line_num)
        else:
            timing_lines[line_num] = convert_timing_to_str(cur_timing)
    return timing_lines, task_lines


def replace_list_bullet_with_indent(line: str):
    indents = re.match(r"^\t*- ", line)
    if indents:
        line = line.replace(indents.group(), indents.group().replace("- ", "\t"))
    return line


def process_templates(
    timing_lines: list[str], task_lines: list[str], datestr: str
) -> tuple[list[str], list[str]]:
    new_task_lines = []
    used_uuids = defaultdict(lambda: 0)

    for uuid in gather_existing_uuids_from_lines(timing_lines):
        used_uuids[unpack_timing_uuid(uuid)[0]] += 1

    for line in task_lines:
        if is_template_line(line):
            indent = re.match(r"^\t*", line).group()
            task_lines = [
                indent + replace_list_bullet_with_indent(i)
                for i in sum(
                    process_template_lines([line], datestr, True, used_uuids).values(),
                    start=[],
                )
            ]
        else:
            task_lines = [line]
        new_task_lines += task_lines
    return new_task_lines


def process_timings_in_task_section(
    timing_lines: list[str], task_lines: list[str]
) -> tuple[list[str], list[str]]:
    """
    Args:
        timing_lines (list[str]): timing lies
        task_lines (list[str]): task lines
    """
    new_task_lines = []
    task_uuid_count = defaultdict(lambda: 0)
    for line in task_lines:
        if is_valid_timing_str(line):
            timing_configs, _ = get_timing_from_lines(
                [line], existing_uuids=gather_existing_uuids_from_lines(timing_lines)
            )

            # add timing
            timing_lines += [convert_timing_to_str(config) for config in timing_configs]
            indent = re.match(r"^\t*", line).group()

            # add task
            tasks = flatten_taskgroups_into_tasks(
                calculate_times_in_taskgroup_list(
                    get_taskgroups_from_timing_configs(timing_configs, task_uuid_count)
                )
            )
            task_lines = [
                (len(indent) - 1) * "\t" + convert_to_string(task) for task in tasks
            ]
        else:
            task_lines = [line]

        new_task_lines += task_lines
    return timing_lines, new_task_lines


def get_uuid_adj_list(taskgroups: list[TaskGroup]):
    adj_list = {}

    def traverse(taskgroups: list[TaskGroup]):
        tasks = [task for taskgroup in taskgroups for task in taskgroup.tasks]
        for task in tasks:
            subtasks = traverse(task.subtaskgroups)
            adj_list[task.uuid] = {subtask.uuid for subtask in subtasks}
        return tasks

    traverse(taskgroups)
    return adj_list
