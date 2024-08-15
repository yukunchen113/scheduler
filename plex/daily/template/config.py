"""
Utilities to modify daily config files
"""
import re
from typing import Optional

from plex.daily.config_format import SPLITTER
from plex.daily.template.base import ReplacementsType
from plex.daily.timing.process import (
    TIMING_SET_TIME_PATTERN,
    gather_existing_uuids_from_lines,
    pack_timing_uuid,
    split_desc_and_uuid,
)
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr


def process_replacements(
    lines: list[TransformStr],
    replacements: ReplacementsType,
    used_uuids: Optional[set[str]] = None,
):
    """replaces the templates with the routines in the timing file lines

    Will not add newline characters.
    """
    new_lines = []
    if used_uuids is None:
        used_uuids = set()
    used_uuids.update(gather_existing_uuids_from_lines(lines))
    for idx, line in enumerate(lines):
        if line.startswith(SPLITTER):
            new_lines += lines[idx:]
            break
        if line in replacements:
            # pack uuids with index for unique timings.
            replacement_lines = []
            for timing_line in replacements[line]:
                timing = re.search(TIMING_SET_TIME_PATTERN, timing_line)
                if timing:
                    desc, timing_uuid_base = split_desc_and_uuid(
                        timing_line[: timing.start()],
                    )

                    increment = 0
                    while True:
                        timing_uuid = pack_timing_uuid(timing_uuid_base, increment)
                        if timing_uuid not in used_uuids:
                            break
                        increment += 1

                    timing_line = (
                        desc
                        + f"|{timing_uuid}| "
                        + timing_line[timing.start() : timing.end()]
                        + timing_line[timing.end() :]
                        + ("\n" if not timing_line.endswith("\n") else "")
                    )
                    used_uuids.add(timing_uuid)
                replacement_lines.append(timing_line)
            new_lines += TRANSFORM.nreplace(line, replacement_lines)
        else:
            new_lines.append(line)
    return new_lines
