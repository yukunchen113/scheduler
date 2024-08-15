from plex.daily.template.peers import update_peer_commands
from plex.daily.template.routines import update_routine_templates
from plex.transform.base import TRANSFORM, LineSection, Metadata, TransformStr


def update_templates(
    lines: list[TransformStr], datestr: str, is_main_file: bool
) -> list[TransformStr]:
    lines = update_peer_commands(lines)
    return update_routine_templates(lines, datestr, is_main_file)
