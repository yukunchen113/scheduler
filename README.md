# Plex: Intentional Time-Blocking & Execution Engine

A keyboard-centric daily & weekly time-blocking planner optimized for VS Code, terminal, and Google Calendar.

## Quickstart (One-Stop Setup)

Set up a complete workspace with starter templates, configuration, secrets, and VS Code integration in one command:

```bash
# 1. Install Plex
pip install -e .

# 2. Run the one-stop setup wizard
plex setup
```

The wizard will:
1. **Scaffold workspace directories**: `routines/`, `daily/`, `weekly/`.
2. **Seed starter templates**: `routines/daily.txt` and `routines/school.txt`.
3. **Configure secrets & settings**: securely saved into `~/.config/plex/config.json` (mode 0600).
4. **Optional Google Calendar OAuth**: runs browser authentication and saves tokens.
5. **Optional Notion integration**: prompts and stores your Notion API key.
6. **VS Code Extension**: links `plex-vscode` so CodeLens and commands work immediately.

For a 1-second, zero-prompt offline setup:
```bash
plex setup --default
```

---

# How to Use

## Basic Daily Planning

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

## Managing Execution & Drift (Start / End Diffs)

As your day progresses and deviations happen, you adjust tasks directly in the schedule section:

* **Starting Late**: Add `+<mins>` to the start of the task line (before the timestamp):
  ```text
  +20	8:20-8:30:	wake up (10)
  ```
  *Result*: Shifts this task and all subsequent tasks 20 minutes later.
* **Starting Early**: Add `-<mins>` to the start:
  ```text
  -10	7:50-8:00:	wake up (10)
  ```
* **Running Long**: Add `+<mins>` to the end of the line:
  ```text
  	8:00-8:10:	wake up (10)	+15
  ```
  *Result*: Extends this task by 15 minutes and pushes subsequent tasks back.
* **Finishing Early (The Protected Break Rule)**: Add `-<mins>` to the end:
  ```text
  	8:00-8:10:	wake up (10)	-5
  ```
  *Result*: Marks the task as completed 5 minutes early, but **does not** pull subsequent tasks forward. It preserves that gap as intentional breathing room to avoid burnout.


## Advanced Macros & Timing Syntax

### 1. Multiplier Macro: `[duration]*N`
Spawn multiple instances of a task with identical duration:
```text
S + C [25]*2
```
*Result*: Generates two distinct 25-minute workout blocks in the schedule.

### 2. Explicit Start and End Anchors on Timings: `(time s)` vs `(time e)`
Anchor tasks directly within the timings section above the splitter:
* **Start Anchor (`s`)**:
  ```text
  wake up [20] (7:30am)
  ```
  *Forces task to start at 7:30 AM.*
* **End Deadline Anchor (`e`)**:
  ```text
  commute to work [30] (9ame)
  ```
  *Forces the task to finish by 9:00 AM, back-calculating its start time to 8:30 AM.*

### 3. Deletion Request Macro: `(-)`
To delete a task from the schedule and simultaneously remove its definition from the top timings section:
```text
	11:00-11:40:	wake up (-)
```
On the next `python -m plex` run, this task and its original line above the splitter will be permanently purged.

### 4. Cross-Section Auto-Promotion
If you are working in your schedule below the splitter and want to add an ad-hoc task:
```text
nap [20]
```
Simply type it directly into the task section. On the next execution, the engine automatically extracts it and moves it above the splitter into the timing definitions section.


## Templates & Modular Routines

Reference reusable routine files located in `routines/`:

* **Full Routine**: `{daily}` pulls all default sections from `routines/daily.txt`.
* **Specific Section**: `{daily:morning}` or `{food:out}` pulls only that designated section.
* **Inline Task Expansion**: You can invoke a template directly inside a block below the splitter (e.g. inside `work`):
  ```text
  	9:00-17:30:	work (8h30)
  		{food:out}
  ```
* **Executable Routine Scripts**: Execute Python scripts in `routines/` passing options:
  ```text
  {strength.py:legs}
  ```
  *Calls `python routines/strength.py --datestr <date> --options legs` and reads stdout into your schedule.*


## Inter-File Peer Commands (Cross-File Task Forwarding)

Exchange and forward tasks between different daily files:

### Forward Tasks to Another Date: `[target:send]` ... `[:end]`
Forward leftover or deferred tasks directly to another day's file:
```text
[2024-07-16:send]
budget:plan [2h]
oil change [1h]
[:end]
```
*What happens*:
1. Opens `daily/2024-07-16.txt` (creating it if needed) and prepends the tasks to its timings section.
2. Removes the tasks from today's file, replacing the block with a duration record: `[2024-07-16:send] (3h)`.

### Remote Date Duration Summary: `[target:summary]`
```text
[2024-07-16:summary]
```
Replaced with the evaluated total time and schedule span:
```text
[2024-07-16:summary] (7h30: |8:00-15:30|)
```


## Interactive Commute & Route Planning

Estimate real-world travel durations directly in your daily schedule using Google Routes API and interactive dark-themed maps:

```text
lecture [1h30] (10am) @Campus
@Campus → @Office [30] 🚗 //{::commute::}
lab [2h] (14:00) @Office
workout [1h] @Gym
-------------
```

* **Task Location Tag**: Append `@Location` (e.g. `@Campus`, `@Office`, `@Home`) to any task line.
* **Commute Bridge**: `@From → @To [timing] [emoji] //{::commute::}` specifies the travel segment.
* **Transport Modes**: `🚗` (Drive), `🚇` (Transit), `🚲` (Bike), `🚶` (Walk).
* **Buffer Multiplier**: Automatically applied to raw transit times (default: `1.25x`, customizable).
* **Idempotent Reloads**: 100% human-readable plain-text DSL. No hidden state or sidecar files.

### VS Code Interactive Planner (`plex-vscode`)
* **Launch**: Click the **`$(location) Plan Commutes`** CodeLens button above `-------------` in any daily file (`daily/*.ans`), or press `Cmd+K C` (`Ctrl+K C`).
* **Navigation & Hotkeys**:
  - `↑` / `↓`: Move cursor focus across task and commute lines.
  - `T`: Cycle transport mode (`🚗 ➔ 🚇 ➔ 🚲 ➔ 🚶 ➔ 🚗`) and recalculate timings instantly.
  - `⌥↑` / `⌥↓` (or drag-and-drop): Reorder tasks. Attached commutes follow along, automatically flipping direction if origin and destination cross (`@Campus → @Office` ⇄ `@Office → @Campus`).
  - `+ @loc`: Expands an inline dark Google Maps canvas to pick preset pins or search any address with autocomplete.


## CLI Reference & Everyday Recipes

You can run commands using `python -m plex` or directly via `plex` when installed (`pip install -e .`):

### Available Flags

| Flag | Default | Description |
| :--- | :---: | :--- |
| `(no flags)` | — | Process and calculate today's schedule (`daily/YYYY-MM-DD.ans`). |
| `--tomorrow` | `False` | Process and calculate tomorrow's schedule. |
| `--date <YYYY-MM-DD>` | `None` | Process a specific historical or future date. |
| `--filename <path>` | `None` | Override the daily file path (defaults to the date). |
| `--autoupdate` | `False` | **Live Watch Mode**: Continuously monitors the daily file. Updates within 1s on changes; sleeps in 5s polling when idle. Syncs with Google Calendar every 60s. |
| `--push` | `False` | One-time push of calculated blocks to Google Calendar and Notion. |
| `--sync` | `False` | Live bi-directional sync daemon: syncs file edits to Google Calendar and pulls calendar edits back into start/end diffs. |
| `--source <file\|notion>` | `"file"` | Source of truth for tasks. Use `notion` to sync directly with your Notion `"Schedule"` page. |
| `--is_skip_calendar` | `False` | Skips Google Calendar API operations (ideal for offline use). |
| `--print_json` | `False` | Prints the parsed JSON tasklist to stdout (for scripting and piping). |
| `--no_process_daily` | `False` | Skips local daily file processing. |
| `--authenticate` | `False` | Re-authorizes Google Calendar and Google Tasks OAuth tokens via browser. |
| `--week` | `False` | Evaluate and open the single-file weekly planner (`weekly/YYYY-WWW.txt`). |
| `--week_watch` | `False` | Live watch mode for the single-file weekly planner in VS Code. |
| `--init <routine>` | `None` | Initialize weekly plan pre-populated with a routine template (.txt) or generator script (.py). (e.g. `plex --init school`) |
| `--week_init <routine>` | `None` | Alias for `--init <routine>`. |
| `--overwrite` | `False` | Overwrite existing weekly plan file when re-initializing. |

### Everyday CLI Recipes

* **Morning Kickoff (Start the day)**:
  ```bash
  python -m plex
  ```
* **Nightly Planning (Plan tomorrow before bed)**:
  ```bash
  python -m plex --tomorrow
  ```
* **Single-File Weekly Planning (VS Code Workflow)**:
  ```bash
  # 1. Initialize this week's plan pre-populated with your school schedule generator:
  python -m plex.weekly --init school
  # Or via main CLI:
  plex --init school

  # (Optional: specify custom generator scripts or templates)
  # python -m plex.weekly --init routines/my_generator.py

  # 2. Open in VS Code
  code weekly/$(date +%Y)-W$(date +%V).txt

  # 3. Leave watcher running in a terminal split (re-evaluates in 0.1s on save)
  python -m plex.weekly --watch
  # Or: plex --week_watch

  # 4. Use VS Code shortcuts:
  #    - Option+Up / Option+Down to slide tasks between classes or days
  #    - Option+Shift+Down to duplicate tasks
  #    - Hit Cmd+S to see scheduled hours, slack, and bedtime warnings update in-place!

  # 5. Export finalized weekly plan to daily files (daily/YYYY-MM-DD.ans)
  python -m plex.weekly --export-daily
  ```
* **Ambient Desk Companion (Leave running in a terminal split)**:
  ```bash
  python -m plex --autoupdate
  ```
* **Sync to Phone / Calendar Before Heading Out**:
  ```bash
  python -m plex --push
  ```
* **Offline / In-Flight Mode (No calendar network calls)**:
  ```bash
  python -m plex --autoupdate --is_skip_calendar
  ```
* **Data Extraction / Piping into `jq`**:
  ```bash
  python -m plex --print_json | jq '.[] | {name: .name, start: .start, end: .end}'
  ```
* **Re-Authenticate Expired Google Tokens**:
  ```bash
  python -m plex --authenticate
  ```




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
