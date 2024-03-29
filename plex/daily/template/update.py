from plex.daily.template.routines import update_routine_templates
from plex.daily.template.peers import update_peer_commands


def update_templates_in_file(filename: str, datestr: str, is_main_file:bool) -> None:
    update_peer_commands(filename)
    update_routine_templates(filename, datestr, is_main_file)
