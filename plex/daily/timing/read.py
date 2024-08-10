from datetime import datetime
from typing import Optional

from plex.daily.config_format import SPLITTER
from plex.daily.timing.base import TimingConfig
from plex.daily.timing.process import get_timing_from_lines


def split_splitter_and_tasks(task_lines_with_splitter: list[str]):
    if task_lines_with_splitter:
        splitter_line, task_lines = [
            task_lines_with_splitter[0]
        ], task_lines_with_splitter[
            1:
        ]  # first line of tasks is the splitter
    else:
        splitter_line, task_lines = [], []
    return splitter_line, task_lines


def split_lines_across_splitter(
    all_lines: list[str], is_separate_splitter: bool = False
) -> list[str]:
    lines = []
    next_lines = []
    for lidx, line in enumerate(all_lines):
        if line.startswith(SPLITTER):
            # splitter
            next_lines = all_lines[lidx:]
            break
        lines.append(line)
    if is_separate_splitter:
        splitter, tasks = split_splitter_and_tasks(next_lines)
        return lines, splitter, tasks
    return lines, next_lines


def get_timing_from_file(
    filename: str, config_date: Optional[datetime] = None, is_process: bool = True
) -> list[TimingConfig]:
    with open(filename) as r:
        lines, other_lines = split_lines_across_splitter(r.readlines())
    output, new_tim_lines = get_timing_from_lines(lines, config_date)

    if is_process:
        with open(filename, "w") as file:
            file.writelines(new_tim_lines + other_lines)

    return output
