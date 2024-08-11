"""
Processes templates in the timing section

Structured as per {...}

where ... is a valid template specifier.

... can be:
y
y:z

in the template folder (default: {project base dir}/routines/):
- y is a file (if no x, then is in the root template folder)
- z is a category.

A file can be structured as:
'''
timing spec
timing spec
'''
in which case {y} can be used

or :
'''
x:
timing spec
timing spec
'''
in which case {y:x} can be used
"""

import glob
import os
import re
import subprocess
from collections import defaultdict
from typing import Optional

from plex.daily.config_format import SPLITTER
from plex.daily.template.base import ReplacementsType
from plex.daily.template.config import process_replacements
from plex.daily.timing.base import pack_timing_uuid
from plex.daily.timing.process import (
    TIMING_SET_TIME_PATTERN,
    gather_existing_uuids_from_lines,
    split_desc_and_uuid,
    unpack_timing_uuid,
)
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr

TEMPLATE_PATTERN = r"\{([^:]*)(?:\:([^:]*))?\}"
TEMPLATE_BASE_DIR = "routines"

DEFAULT_TEMPLATE_SECTION = "__default__:\n"


def get_template_base_dir():
    return TEMPLATE_BASE_DIR


def read_sections_from_template(
    filename: str,
    datestr: str,
    is_main_file: bool,
    options: str = "",
    template_name: str = "",
    used_uuids: Optional[dict[str, int]] = None,
) -> ReplacementsType:
    sections: ReplacementsType = {DEFAULT_TEMPLATE_SECTION: []}
    command = f"python3.10 {filename} --datestr {datestr}"
    if is_main_file:
        command += " --is_main_file"
    if options:
        command += f" --options {options}"
    if filename.endswith(".py"):
        output = subprocess.run(
            command.split(),
            env=os.environ,
            capture_output=True,
        )
        if output.returncode:
            print(output.stderr.decode())
            exit()
        lines = [line + "\n" for line in output.stdout.decode().split("\n")]
    else:
        with open(filename) as f:
            lines = f.readlines()

    last_key = None

    if used_uuids is None:
        used_uuids = defaultdict(lambda: 0)

    for line in lines:
        timing = re.search(TIMING_SET_TIME_PATTERN, line)
        if timing:
            # embelish line with metadata on which template it came from.
            section = template_name
            if last_key is not None:
                section += f"-{last_key}"
            desc, timing_uuid = split_desc_and_uuid(
                line[: timing.start()],
                default_uuid=pack_timing_uuid(section, used_uuids[section]),
            )
            line = (
                desc
                + f"|{timing_uuid}| "
                + line[timing.start() : timing.end()]
                + line[timing.end() :]
            )
            used_uuids[section] += 1
        if line.endswith(":\n"):
            last_key = line.replace(":\n", "")
            sections[last_key] = []
        elif last_key is not None:
            sections[last_key].append(line)
        elif last_key is None:
            sections[DEFAULT_TEMPLATE_SECTION].append(line)
    return sections


def is_template_line(line: str) -> bool:
    return bool(re.search(TEMPLATE_PATTERN, line))


def process_template_lines(
    lines: list[TransformStr],
    datestr: str,
    is_main_file: bool,
    used_uuids: Optional[dict[str, int]] = None,
) -> ReplacementsType:
    templates: ReplacementsType = {}
    for line in lines:
        if is_template_line(line):
            dfile, section = re.findall(TEMPLATE_PATTERN, line)[0]
            path = os.path.join(get_template_base_dir(), dfile + ".*")
            files = glob.glob(path)
            if len(files) != 1:
                print(
                    f"pattern '{line}' returned '{files}', must be "
                    "exactly 1 file. Ignoring pattern."
                )
                continue
            file = files[0]
            tsections = read_sections_from_template(
                file, datestr, is_main_file, section, dfile, used_uuids
            )
            if section:
                if section not in tsections:
                    raise ValueError((dfile, section, tsections))
                timing_lines = tsections[section]
            else:
                timing_lines = sum(tsections.values(), [])
            templates[line] = timing_lines
        if line.startswith(SPLITTER):
            return templates
    return templates


def update_routine_templates_in_file(filename, datestr, is_main_file=False):
    with open(filename) as f:
        lines = f.readlines()
    new_lines = update_routine_templates(lines, datestr, is_main_file)
    with open(filename, "w") as f:
        f.write("".join(new_lines))


def update_routine_templates(
    lines: list[TransformStr], datestr: str, is_main_file: bool = False
) -> list[TransformStr]:
    used_uuids = defaultdict(lambda: 0)
    for uuid in gather_existing_uuids_from_lines(lines):
        used_uuids[unpack_timing_uuid(uuid)[0]] += 1
    replacements = process_template_lines(lines, datestr, is_main_file, used_uuids)
    return process_replacements(lines, replacements)
