"""
Utilities to modify daily config files
"""

from plex.daily.config_format import SPLITTER
from plex.daily.template.base import ReplacementsType
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr


def process_replacements(lines: list[TransformStr], replacements: ReplacementsType):
    """replaces the templates with the routines in the timing file lines

    Will not add newline characters.
    """
    new_lines = []
    for idx, line in enumerate(lines):
        if line.startswith(SPLITTER):
            new_lines += lines[idx:]
            break
        if line in replacements:
            new_lines += TRANSFORM.nreplace(line, replacements[line])
        else:
            new_lines.append(line)
    return new_lines
