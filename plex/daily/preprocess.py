from plex.daily.timing.read import split_lines_across_splitter
from plex.daily.timing.process import get_timing_from_lines, is_valid_timing_str, gather_existing_uuids_from_lines
from plex.daily.tasks.logic.calculations import calculate_times_in_taskgroup_list
from plex.daily.tasks.logic.conversions import get_taskgroups_from_timing_configs
from plex.daily.tasks.base import TaskGroup, Task
from plex.daily.timing.base import TimingConfig
from plex.daily.tasks.config import convert_task_to_string, process_taskgroups_from_lines
from plex.daily.template.routines import process_template_lines, is_template_line
import re
from collections import defaultdict

def apply_preprocessing(filename: str, datestr: str) -> None:
	with open(filename) as file:
		timing, tasks = split_lines_across_splitter(file.readlines())
		splitter_line, tasks = tasks[0], tasks[1:] # first line of tasks is the splitter
	tasks = process_templates(tasks, datestr)
	timing, tasks = process_timings_in_task_section(timing, tasks)

	with open(filename, "w") as file:
		file.writelines(timing + [splitter_line] + tasks)

def replace_list_bullet_with_indent(line: str):
	indents = re.match(r"^\t*- ", line)
	if indents:
		line = line.replace(indents.group(), indents.group().replace("- ", "\t"))
	return line

def process_templates(task_lines:list[str], datestr: str) -> tuple[list[str], list[str]]:
	new_task_lines = []
	used_uuids = defaultdict(lambda: 0)
	for line in task_lines:
		if is_template_line(line):
			indent = re.match(r"^\t*", line).group()
			task_lines = [indent+replace_list_bullet_with_indent(i) for i in sum(
				process_template_lines([line], datestr, True, used_uuids).values(), start=[]
			)]
		else:
			task_lines = [line]
		new_task_lines += task_lines
	return new_task_lines

def flatten_taskgroups_into_tasks(taskgroups: list[TaskGroup]) -> list[Task]:
	tasks = []
	for taskgroup in taskgroups:
		for task in taskgroup.tasks:
			tasks.append(task)
			tasks += flatten_taskgroups_into_tasks(task.subtaskgroups)
	return tasks

def process_timings_in_task_section(timing_lines: list[str], task_lines:list[str]) -> tuple[list[str], list[str]]:
	"""
	Args:
		timing_lines (list[str]): timing lies
		task_lines (list[str]): task lines
	"""
	new_task_lines = []
	task_uuid_count = defaultdict(lambda: 0)
	for line in task_lines:
		if is_valid_timing_str(line):
			timing_configs, new_timing_lines = get_timing_from_lines([line], existing_uuids=gather_existing_uuids_from_lines(timing_lines))
			
			# add timing
			timing_lines += new_timing_lines
			indent = re.match(r"^\t*", line).group()

			# add task
			tasks = flatten_taskgroups_into_tasks(calculate_times_in_taskgroup_list(
				get_taskgroups_from_timing_configs(timing_configs, task_uuid_count)
			))
			task_lines = [(len(indent)-1)*"\t"+convert_task_to_string(task) for task in tasks]
		else:
			task_lines = [line]

		new_task_lines += task_lines
	return timing_lines, new_task_lines

def get_uuid_adj_list(taskgroups: list[TaskGroup]):
	adj_list = {}
	def traverse(taskgroups: list[TaskGroup]):
		tasks = [task for taskgroup in taskgroups for task in taskgroup.tasks]
		for task in tasks:
			subtasks = traverse(task.subtaskgroups)
			adj_list[task.uuid] = {subtask.uuid for subtask in subtasks}
		return tasks
	traverse(taskgroups)
	return adj_list
