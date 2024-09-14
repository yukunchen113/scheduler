import dataclasses
import re
from collections import defaultdict
from typing import Optional

from plex.daily.tasks.base import (
    Task,
    TaskGroup,
    TaskType,
    flatten_taskgroups_into_tasks,
)
from plex.daily.tasks.config import (
    convert_to_string,
    process_task_line,
    process_taskgroups_from_lines,
)
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.tasks.logic.conversions import (
    get_taskgroups_from_timing_configs,
    get_timing_uuid_from_task_uuid,
)
from plex.daily.template.routines import (
    is_template_line,
    process_replacements,
    process_template_lines,
)
from plex.daily.timing.base import TimingConfig, flatten_timings, unpack_timing_uuid
from plex.daily.timing.process import (
    convert_timing_to_str,
    gather_existing_uuids_from_lines,
    get_timing_from_lines,
    indent_line,
    is_valid_timing_str,
    split_desc_and_uuid,
)
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr


def apply_preprocessing(
    timing: list[TransformStr], tasks: list[TransformStr], datestr: str
) -> tuple[list[TransformStr], list[TransformStr]]:
    tasks = process_templates_from_tasks(timing, tasks, datestr)
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
    timing_lines: list[TransformStr], task_lines: list[TransformStr]
) -> tuple[list[TransformStr], list[TransformStr]]:
    timings, timing_lines = get_timing_from_lines(timing_lines)
    cur_timing_map = get_timing_uuid_mapping(timings)
    TRANSFORM.stop_recording()
    cur_tasks_map = {
        task.uuid: task
        for task in flatten_taskgroups_into_tasks(
            process_taskgroups_from_lines(task_lines, task_type=TaskType)
        )
    }
    TRANSFORM.start_recording()

    for line in task_lines:
        main_task, _ = process_task_line(line, task_type=TaskType.deletion_request)
        if main_task is None:
            continue
        main_task = cur_tasks_map[main_task.uuid]

        for task in [main_task] + flatten_taskgroups_into_tasks(
            main_task.subtaskgroups
        ):
            # delete related timing
            timing_uuid, index = get_timing_uuid_from_task_uuid(task.uuid)
            if timing_uuid not in cur_timing_map:
                # already deleted
                continue
            for cur_timing in flatten_timings([cur_timing_map[timing_uuid]]):
                existing_string = convert_timing_to_str(cur_timing)
                if existing_string in timing_lines:
                    line_num = timing_lines.index(existing_string)
                    remove_timing_index_from_timing(cur_timing, index)
                    if not cur_timing.timings:
                        TRANSFORM.delete(timing_lines.pop(line_num))
                        # delete notes as well
                        for note in cur_timing.notes:
                            TRANSFORM.delete(
                                timing_lines.pop(
                                    timing_lines.index(
                                        indent_line(
                                            note, cur_timing.subtiming_level + 1
                                        )
                                    )
                                )
                            )
                    else:
                        timing_lines[line_num] = TRANSFORM.replace(
                            timing_lines[line_num],
                            convert_timing_to_str(cur_timing),
                            dataclasses.replace(
                                TRANSFORM.get_metadata(
                                    timing_lines[line_num],
                                ),
                                is_preprocessed=True,
                            ),
                        )
    return timing_lines, task_lines


def replace_list_bullet_with_indent(line: str):
    indents = re.match(r"^\t*- ", line)
    if indents:
        line = line.replace(indents.group(), indents.group().replace("- ", "\t"))
    return line


def get_timing_lines_from_template_line(
    line: TransformStr, datestr: str, used_uuids: Optional[set] = None
) -> list[TransformStr]:
    replacements = process_template_lines([line], datestr, True)
    return process_replacements([line], replacements, used_uuids)


def process_templates_from_tasks(
    timing_lines: list[TransformStr], task_lines: list[TransformStr], datestr: str
) -> list[TransformStr]:
    new_task_lines = []
    used_uuids = gather_existing_uuids_from_lines(timing_lines)

    for line in task_lines:
        if is_template_line(line):
            indent = re.match(r"^\t*", line).group()
            task_lines = []
            for timing_line in get_timing_lines_from_template_line(
                line, datestr, used_uuids
            ):
                task_lines.append(
                    TRANSFORM.replace(
                        timing_line,
                        indent + replace_list_bullet_with_indent(timing_line),
                        metadata=Metadata(
                            section=LineSection.task, is_preprocessed=True
                        ),
                    )
                )
            for timing_line in timing_lines:
                used_uuids.add(
                    unpack_timing_uuid(
                        split_desc_and_uuid(timing_line.split("[")[0])[1]
                    )[0]
                )

        else:
            task_lines = [line]
        new_task_lines += task_lines
    return new_task_lines


def process_timings_in_task_section(
    timing_lines: list[TransformStr], task_lines: list[TransformStr]
) -> tuple[list[TransformStr], list[TransformStr]]:
    """
    Args:
        timing_lines (list[TransformStr]): timing lies
        task_lines (list[TransformStr]): task lines
    """
    new_task_lines = []
    task_uuid_count = defaultdict(lambda: 0)
    for line in task_lines:
        if is_valid_timing_str(line):
            timing_configs, _ = get_timing_from_lines(
                [line], existing_uuids=gather_existing_uuids_from_lines(timing_lines)
            )

            # add timing
            timing_lines += TRANSFORM.add_after(
                line,
                [convert_timing_to_str(config) for config in timing_configs],
                timing_lines[-1],
                Metadata(section=LineSection.timing, is_preprocessed=True),
            )

            # add task
            tasks = flatten_taskgroups_into_tasks(
                calculate_times_in_taskgroup_list(
                    get_taskgroups_from_timing_configs(timing_configs, task_uuid_count)
                )
            )
            task_lines = TRANSFORM.nreplace(
                line,
                [
                    len(re.match(r"^\t*", line).group()) * "\t"
                    + convert_to_string(task)[0]
                    for task in tasks
                ],
                metadata=Metadata(section=LineSection.task, is_preprocessed=True),
            )
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
