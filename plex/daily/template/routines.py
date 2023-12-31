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
import os

from plex.daily.config_format import SPLITTER
from plex.daily.template.config import write_timings_inplace_of_template
from plex.daily.template.base import ReplacementsType

TEMPLATE_PATTERN = r"\{([^:]*)(?:\:([^:]*))?\}"
TEMPLATE_BASE_DIR = "routines"

DEFAULT_TEMPLATE_SECTION = "__default__:\n"


def read_sections_from_template(filename: str, datestr: str) -> ReplacementsType:
    sections: ReplacementsType = {DEFAULT_TEMPLATE_SECTION: []}

    if filename.endswith(".py"):
        output = subprocess.run(
            f"python3.10 {filename} --datestr {datestr}".split(),
            env=os.environ,
            capture_output=True,
        )
        lines = [line + "\n" for line in output.stdout.decode().split("\n")]
    else:
        with open(filename) as f:
            lines = f.readlines()

    last_key = None
    for line in lines:
        if line.endswith(":\n"):
            last_key = line.replace(":\n", "")
            sections[last_key] = []
        elif last_key is not None:
            sections[last_key].append(line)
        elif last_key is None:
            sections[DEFAULT_TEMPLATE_SECTION].append(line)
    return sections


def read_template_from_timing(filename: str, datestr: str) -> ReplacementsType:
    """
    reads the {} templates in timing file
    """
    with open(filename) as f:
        lines = f.readlines()
    templates: ReplacementsType = {}
    for line in lines:
        if re.match(TEMPLATE_PATTERN, line):
            dfile, section = re.findall(TEMPLATE_PATTERN, line)[0]
            path = os.path.join(TEMPLATE_BASE_DIR, dfile + ".*")
            files = glob.glob(path)
            if len(files) != 1:
                print(
                    f"pattern '{line}' returned '{files}', must be "
                    "exactly 1 file. Ignoring pattern."
                )
                continue
            file = files[0]
            tsections = read_sections_from_template(file, datestr)
            if section:
                timing_lines = tsections[section]
            else:
                timing_lines = sum(tsections.values(), [])
            templates[line] = timing_lines
        if line.startswith(SPLITTER):
            return templates
    return templates


def update_routine_templates(filename, datestr):
    replacements = read_template_from_timing(filename, datestr=datestr)
    write_timings_inplace_of_template(filename, replacements)
