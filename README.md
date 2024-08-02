# How to Use

## Starting from Scratch

Run the module with the command:

```bash
python -m plex
```

This will create a folder called `daily` and the file for today's date, called the `daily file`, with a `splitter`:

```text
-------------


```

## Basic Usage of Daily File

Start by creating some tasks with the related expected time of completion, called `timing`. Add the timings above the splitter, or you can delete the splitter (it will be regenerated after running the command again)

For your mental health and for a long term usage of the schedule, you would want to set a time that gives you a good amount of breathing room.

Timings are in the form of `<task> [time]`

Here's an example:

```text
wake up [10]
washroom [20]
skincare [10]
get ready [10]

commute to work [30]
work [8h10]
- lunch [1h]
go to hangout [30]

hangout with dinner [2h]
go home [30]

workout [1h]

project [2h]

get ready for bed [30]
-------------


```

Once your done outlining all the timings for the day, you can generate the daily schedule of `tasks`, run the execution command:

```bash
python -m plex
```

The above generates the following tasks below the splitter:

```
wake up [10]
washroom [20]
skincare [10]
get ready [10]

commute to work [30]
work [8h10]
- lunch [1h]
go to hangout [30]

hangout with dinner [2h]
go home [30]

workout [1h]

project [2h]

get ready for bed [30]
-------------

	7:30-7:40:	wake up (10)
	7:40-8:00:	washroom (20)
	8:00-8:10:	skincare (10)
	8:10-8:20:	get ready (10)
	8:20-8:50:	commute to work (30)
	8:50-17:00:	work (8h10)
		8:50-9:50:	lunch (1h)
	17:00-17:30:	go to hangout (30)
	17:30-19:30:	hangout with dinner (2h)
	19:30-20:00:	go home (30)
	20:00-21:00:	workout (1h)
	21:00-23:00:	project (2h)
	23:00-23:30:	get ready for bed (30)

```


# Modifying the Schedule

If you want to change the expected durations, you need to change it in the timing section,
and it will then be reflected in the scheduler section.

You can move `tasks` around in the schedule, and the movement will be persisted. For example, moving workout up a couple of rows. You can then rerun the execution command:

```
	7:30-7:40:	wake up (10)
	7:40-8:00:	washroom (20)
	8:00-8:10:	skincare (10)
	8:10-8:20:	get ready (10)
	8:20-8:50:	commute to work (30)
	8:50-17:00:	work (8h10)
		8:50-9:50:	lunch (1h)
	20:00-21:00:	workout (1h)
	17:00-17:30:	go to hangout (30)
	17:30-19:30:	hangout with dinner (2h)
	19:30-20:00:	go home (30)
	21:00-23:00:	project (2h)
	23:00-23:30:	get ready for bed (30)
```

```bash
python -m plex
```

```
	7:30-7:40:	wake up (10)
	7:40-8:00:	washroom (20)
	8:00-8:10:	skincare (10)
	8:10-8:20:	get ready (10)
	8:20-8:50:	commute to work (30)
	8:50-17:00:	work (8h10)
		8:50-9:50:	lunch (1h)
	17:00-18:00:	workout (1h)
	18:00-18:30:	go to hangout (30)
	18:30-20:30:	hangout with dinner (2h)
	20:30-21:00:	go home (30)
	21:00-23:00:	project (2h)
	23:00-23:30:	get ready for bed (30)
```

You can control the tasks by setting `start time` and `end time`.
- split the tasks into `taskgroups`, which are just separated by an empty line
- add the time to the
  - beginning of taskgroup if you want to specify start time
  - end of taskgroup if you want to specify end time
- make sure indentation of timing is correct for subtasks (see below for example)

```
8am
  7:30-7:40:	wake up (10)
  7:40-8:00:	washroom (20)
  8:00-8:10:	skincare (10)
  8:10-8:20:	get ready (10)
  8:20-8:50:	commute to work (30)
  8:50-17:00:	work (8h10)

  12
    8:50-9:50:	lunch (1h)

  20:00-21:00:	workout (1h)
  17:00-17:30:	go to hangout (30)
  17:30-19:30:	hangout with dinner (2h)
  19:30-20:00:	go home (30)
  21:00-23:00:	project (2h)

  23:00-23:30:	get ready for bed (30)
11:55pm
```

```bash
python -m plex
```

```
8:00
	8:00-8:10:	wake up (10)
	8:10-8:30:	washroom (20)
	8:30-8:40:	skincare (10)
	8:40-8:50:	get ready (10)
	8:50-9:20:	commute to work (30)
	9:20-17:30:	work (8h10)
	12:00
		12:00-13:00:	lunch (1h)

	17:30-18:30:	workout (1h)
	18:30-19:00:	go to hangout (30)
	19:00-21:00:	hangout with dinner (2h)
	21:00-21:30:	go home (30)
	[91m21:30-23:30:	project (2h)[0m

	23:25-23:55:	get ready for bed (30)
23:55
```

For tasks that overlap, ansi coloring will show red for that task. (See project task in example above)

## Marking Tasks as Started and Completed

To mark tasks as completed

...


# TODO:


## Daily Improvements

- allow pulling of timings
  - useful for:
    - other apis (strength app)
    - daily calendar offerings for goals
    - work calendar (oncl, normal day, holiday)
    - default tasks
      - these tasks are every day routine and correspond to a configuration of standard tasks (translation unit)
      - reach out to external libraries for tasks of tasks
      - these tasks will be gathered by "allow default tasks"
  - phase 1:
    - only worry about pulling the task, don't calculate timing unless if it's the default tasks
- allow spec of a hour:min for start/end diffs
- timing improvments:
  - specify time of when a task is supposed to start in timing
  - indicate timing overlaps
- correction of timings
  - must be greater than sum of subtask times?
    - might not be desirable since we can have multiple timing specs, how do you modify that?
- add timing sections
  - current: tasks to do today
  - off: tasks that are not included in today's calculation
  - future: tasks that will be forwarded ot the next day's list
- better estimations for key in deletion/addition

## Calendar Improvements

- add calendar processing

## Other

- documentation
  - enrich features with examples on how to do it
  - add notes on values

# Features:

Given timings, will generate a schedule
You can add sub timings, which will generate subtasks.
If you add or delete timings, the change will be reflected in the tasks.
If you change the main times for the timings, it will be reflected in the tasks

Task schedule can be adjustable you can shift things around to your needs.

You can add or subtract times based on if you started or finished earlier or later than expected

- note, to encourage breaks and increase flexibility, this is how adding/subtracting time works (until end or hard start time) These are called start/end diffs:
  - subtract from task start will shift everything early
  - add to the start will shift everything later
  - subtract from task end will not affect subsequent tasks, only the current task end time. This is to encourage breaks and lessen the need to complete everything early - if you feel the need to complete everything early, plan less.
  - add to the end will shift everything later

You can define a hard start time

- the tasks from then onwards (until a empty line) will be adjusted to this start time.

You can define a soft end time

- the tasks will re-adjust backwards
- this is applied before the subtracts/adds to time

You can add notes to the schedule
