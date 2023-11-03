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
from typing import Union
import re
from plex.daily.config_format import SPLITTER
import os
import glob

TEMPLATE_PATTERN = r"\{([^:]*)(?:\:([^:]*))?\}\n"
TEMPLATE_BASE_DIR = "routines"


def read_sections_from_template(filename: str) -> dict[str, list[str]]:
    sections: dict[str, list[str]] = {}
    with open(filename) as f:
        lines = f.readlines()
        last_key = None
        for line in lines:
            if line.endswith(":\n"):
                last_key = line.replace(":\n", "")
                sections[last_key] = []
            elif last_key is not None:
                sections[last_key].append(line)
    return sections


def read_template_from_timing(filename: str) -> dict[str, list[str]]:
    """
    reads the {} templates in timing file
    """
    with open(filename) as f:
        lines = f.readlines()
    templates: dict[str, list[str]] = {}
    for line in lines:
        if re.match(TEMPLATE_PATTERN, line):
            dfile, section = re.findall(TEMPLATE_PATTERN, line)[0]
            path = os.path.join(TEMPLATE_BASE_DIR, dfile+".*")
            files = glob.glob(path)
            if len(files) != 1:
                print(
                    f"pattern '{line}' returned '{files}', must be "
                    "exactly 1 file. Ignoring pattern.")
                continue
            file = files[0]
            tsections = read_sections_from_template(file)
            if section:
                timing_lines = tsections[section]
            else:
                timing_lines = sum(tsections.values(), [])
            templates[line] = timing_lines
        if line.startswith(SPLITTER):
            return templates
    return templates


def write_timings_inplace_of_template(filename: str, replacements: dict[str, list[str]]) -> None:
    """replaces the templates with the routines in the timing file
    """
    with open(filename) as f:
        lines = f.readlines()
    new_lines = []
    for idx,line in enumerate(lines):
        if line.startswith(SPLITTER):
            new_lines += lines[idx:]
            break
        if line in replacements:
            new_lines+=replacements[line]
        else:
            new_lines.append(line)
    with open(filename,"w") as f:
        f.write("".join(new_lines))


def update_templates_in_file(filename: str) -> None:
    replacements = read_template_from_timing(filename)
    write_timings_inplace_of_template(filename, replacements)
