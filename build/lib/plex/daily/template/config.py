"""
Utilities to modify daily config files
"""
from plex.daily.config_format import SPLITTER
from plex.daily.template.base import ReplacementsType


def write_timings_inplace_of_template(
    filename: str, replacements: ReplacementsType
) -> None:
    """replaces the templates with the routines in the timing file

    Will not add newline characters.
    """
    with open(filename) as f:
        lines = f.readlines()
    new_lines = process_replacements(lines, replacements)
    with open(filename, "w") as f:
        f.write("".join(new_lines))


def process_replacements(lines: list[str], replacements: ReplacementsType):
    new_lines = []
    for idx, line in enumerate(lines):
        if line.startswith(SPLITTER):
            new_lines += lines[idx:]
            break
        if line in replacements:
            new_lines += replacements[line]
        else:
            new_lines.append(line)
    return new_lines
