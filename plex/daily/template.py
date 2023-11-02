""" 
Processes templates in the timing section

Structured as per {...}

where ... is a valid template specifier.

... can be:
y
x:y
x:y:z
y:z

in the template folder (default: {project base dir}/routine/):
- y is a file (if no x, then is in the root template folder)
- x is a folder that y is in
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
import re
from plex.daily.config_format import SPLITTER

TEMPLATE_PATTERN = r"\{(?:(.*)\:)?(.*)(?:\:(.*))?\}\n"


def read_template_from_timing(filename: str) -> list[str]:
    """
    reads the {} templates in timing file
    """
    with open(filename) as f:
        lines = f.readlines()
    templates: list[str] = []
    for line in lines:
        if re.match(TEMPLATE_PATTERN, line):
            print(re.findall(TEMPLATE_PATTERN, line))
            folder, dfile, section = re.findall(TEMPLATE_PATTERN, line)[0]
            print("folder: \t", folder)
            print("dfile: \t", dfile)
            print("section: \t", section)
            # templates.append()
        if line.startswith(SPLITTER):
            return templates


def write_timings_inplace_of_template(filename: str) -> None:
    """replaces the templates with the routines in the timing file
    """


def get_specs_for_template(template: str) -> dict[str, list[str]]:
    """gets a set of specifictions given a template"""


def update_templates_in_file(filename: str) -> None:
    read_template_from_timing(filename)
