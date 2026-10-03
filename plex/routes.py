"""
Plex Routes & Commute Planning Engine

Provides:
1. Google Routes API calculation with caching and offline fallback.
2. In-file idempotent parsing and serialization of location tags and commute lines:
     @Campus → @Office [30] 🚗 //{::commute::}
3. Location resolution against ~/.config/plex/config.json.
"""

import json
import math
import os
import re
import urllib.error
import urllib.request
from datetime import datetime
from typing import Any, Optional, Union

from plex.config import get_config_dir, get_locations, get_routes_config, save_location
from plex.daily.config_format import SPLITTER

TRANSPORT_MODES = {
    "drive": {"emoji": "🚗", "factor": 1.0, "google_mode": "DRIVE"},
    "transit": {"emoji": "🚇", "factor": 1.35, "google_mode": "TRANSIT"},
    "bike": {"emoji": "🚲", "factor": 1.25, "google_mode": "BICYCLE"},
    "walk": {"emoji": "🚶", "factor": 3.2, "google_mode": "WALK"},
}

EMOJI_TO_MODE = {v["emoji"]: k for k, v in TRANSPORT_MODES.items()}
COMMUTE_MARKER = "//{::commute::}"

# Regex patterns
COMMUTE_LINE_REGEX = re.compile(
    r"^(@\S+)\s*→\s*(@\S+)\s*\[([^\]]+)\]\s*([🚗🚇🚲🚶])(?:\s*//\s*\{::commute::\}|\s*//\{::commute::\})?",
    re.UNICODE,
)
LEGACY_COMMUTE_REGEX = re.compile(
    r"^commute to\s+(.+?)(?:\s*\|[^\|]+\|)?\s*\[([^\]]+)\]\s*([🚗🚇🚲🚶])?(?:\s*//\s*(@\S+)\s*→\s*(@\S+))?",
    re.UNICODE,
)
TASK_LINE_REGEX = re.compile(
    r"^([^\n\[\|]+?)(?:\s*\|([^\|]+)\|)?\s*\[([^\]]+)\](?:\s*\(([^)]+)\))?(?:\s*(@\S+))?"
)


def get_cache_file() -> str:
    return str(get_config_dir() / "routes_cache.json")


def load_routes_cache() -> dict[str, Any]:
    cache_path = get_cache_file()
    if os.path.exists(cache_path):
        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def save_routes_cache(cache: dict[str, Any]) -> None:
    cache_path = get_cache_file()
    try:
        with open(cache_path, "w", encoding="utf-8") as f:
            json.dump(cache, f, indent=2)
    except Exception:
        pass


def calculate_buffered_minutes(
    raw_minutes: float, buffer_multiplier: float = 1.25
) -> int:
    """Calculates buffered minutes rounded up to nearest 5-minute increment (min 5 mins)."""
    buffered = raw_minutes * buffer_multiplier
    rounded = math.ceil(buffered / 5.0) * 5
    return max(5, int(rounded))


def compute_route_duration(
    origin: str,
    destination: str,
    mode: str = "drive",
    buffer_multiplier: float = 1.25,
    api_key: Optional[str] = None,
) -> tuple[int, int, bool]:
    """Computes commute duration between origin and destination.

    Returns:
        tuple[int, int, bool]: (buffered_minutes, raw_minutes, is_live_google_route)
    """
    mode = mode.lower()
    if mode not in TRANSPORT_MODES:
        mode = "drive"

    routes_cfg = get_routes_config()
    api_key = api_key or routes_cfg.get("api_key")

    # Resolve locations if names given
    locations = get_locations()
    origin_addr = locations.get(origin, origin)
    dest_addr = locations.get(destination, destination)

    if origin_addr == dest_addr:
        return 0, 0, False

    cache_key = f"{origin_addr}::{dest_addr}::{mode}"
    cache = load_routes_cache()

    if cache_key in cache:
        raw_min = cache[cache_key]["raw_minutes"]
        return (
            calculate_buffered_minutes(raw_min, buffer_multiplier),
            raw_min,
            cache[cache_key].get("is_live", False),
        )

    # Attempt Google Routes API call if API key provided
    if api_key:
        try:
            url = "https://routes.googleapis.com/directions/v2:computeRoutes"
            payload = {
                "origin": {"address": origin_addr},
                "destination": {"address": dest_addr},
                "travelMode": TRANSPORT_MODES[mode]["google_mode"],
            }
            if mode == "drive":
                payload["routingPreference"] = "TRAFFIC_AWARE"

            headers = {
                "Content-Type": "application/json",
                "X-Goog-Api-Key": api_key,
                "X-Goog-FieldMask": "routes.duration,routes.distanceMeters",
            }

            req = urllib.request.Request(
                url,
                data=json.dumps(payload).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(req, timeout=5) as response:
                res_data = json.loads(response.read().decode("utf-8"))
                if "routes" in res_data and len(res_data["routes"]) > 0:
                    dur_str = res_data["routes"][0].get("duration", "1200s")
                    dur_sec = int(dur_str.rstrip("s"))
                    raw_min = max(1, math.ceil(dur_sec / 60.0))

                    cache[cache_key] = {
                        "raw_minutes": raw_min,
                        "distanceMeters": res_data["routes"][0].get(
                            "distanceMeters", 0
                        ),
                        "timestamp": datetime.now().isoformat(),
                        "is_live": True,
                    }
                    save_routes_cache(cache)
                    return (
                        calculate_buffered_minutes(raw_min, buffer_multiplier),
                        raw_min,
                        True,
                    )
        except Exception:
            # Fall back to offline estimation on error
            pass

    # Offline Fallback Estimation (Deterministic based on preset distance or char hash)
    # Default city travel baseline: ~18 mins drive, scaled by mode factor
    h = abs(hash(f"{origin_addr}->{dest_addr}")) % 15 + 10  # 10 to 24 mins
    factor = TRANSPORT_MODES[mode]["factor"]
    raw_min = int(round(h * factor))

    cache[cache_key] = {
        "raw_minutes": raw_min,
        "is_live": False,
        "timestamp": datetime.now().isoformat(),
    }
    save_routes_cache(cache)

    return calculate_buffered_minutes(raw_min, buffer_multiplier), raw_min, False


def parse_daily_commute_plan(lines: list[str]) -> dict[str, Any]:
    """Parses a daily .ans file's lines above the splitter into structured tasks and commutes."""
    tasks = []
    commutes = []
    splitter_idx = -1

    for idx, raw_line in enumerate(lines):
        line = raw_line.strip()
        if not line:
            continue
        if line.startswith(SPLITTER):
            splitter_idx = idx
            break

        # Check for explicit commute line: @From → @To [timing] emoji //{::commute::}
        c_match = COMMUTE_LINE_REGEX.match(line)
        if c_match:
            from_loc = c_match.group(1)
            to_loc = c_match.group(2)
            duration = c_match.group(3)
            emoji = c_match.group(4)
            mode = EMOJI_TO_MODE.get(emoji, "drive")
            commutes.append(
                {
                    "fromLoc": from_loc,
                    "toLoc": to_loc,
                    "duration": duration,
                    "mode": mode,
                    "emoji": emoji,
                    "lineIndex": idx,
                }
            )
            continue

        # Check for legacy commute line format
        l_match = LEGACY_COMMUTE_REGEX.match(line)
        if l_match:
            duration = l_match.group(2)
            emoji = l_match.group(3) or "🚗"
            from_loc = l_match.group(4) or "@Origin"
            to_loc = l_match.group(5) or "@Destination"
            mode = EMOJI_TO_MODE.get(emoji, "drive")
            commutes.append(
                {
                    "fromLoc": from_loc,
                    "toLoc": to_loc,
                    "duration": duration,
                    "mode": mode,
                    "emoji": emoji,
                    "lineIndex": idx,
                }
            )
            continue

        # Check for regular task
        t_match = TASK_LINE_REGEX.match(line)
        if t_match:
            task_desc = t_match.group(1).strip()
            uuid_tag = t_match.group(2)
            duration = t_match.group(3).strip()
            set_time = t_match.group(4)
            location = t_match.group(5)
            tasks.append(
                {
                    "id": f"task_{len(tasks)}",
                    "text": task_desc,
                    "duration": duration,
                    "time": set_time,
                    "location": location,
                    "uuid": uuid_tag,
                    "lineIndex": idx,
                }
            )

    return {
        "tasks": tasks,
        "commutes": commutes,
        "splitter_index": splitter_idx,
    }


def serialize_daily_commute_plan(
    tasks: list[dict[str, Any]],
    commutes: list[dict[str, Any]],
    buffer_multiplier: float = 1.25,
) -> str:
    """Serializes tasks and commutes back into concise .ans DSL syntax above the splitter."""
    lines = []
    task_by_id = {t["id"]: t for t in tasks}

    for i, t in enumerate(tasks):
        # Find if there is an incoming commute to this task
        incoming_commute = None
        for c in commutes:
            # Matches if toLoc equals this task's location or explicit destId
            if c.get("destId") == t["id"]:
                incoming_commute = c
                break
            elif t.get("location") and c.get("toLoc") == t.get("location"):
                # Check origin matches preceding location task
                prev_loc = None
                for prev_t in tasks[:i]:
                    if prev_t.get("location"):
                        prev_loc = prev_t.get("location")
                if prev_loc and c.get("fromLoc") == prev_loc:
                    incoming_commute = c
                    break

        if incoming_commute:
            mode = incoming_commute.get("mode", "drive")
            mode_info = TRANSPORT_MODES.get(mode, TRANSPORT_MODES["drive"])
            emoji = mode_info["emoji"]
            dur = incoming_commute.get("duration")
            if not dur:
                buffered, _, _ = compute_route_duration(
                    incoming_commute["fromLoc"],
                    incoming_commute["toLoc"],
                    mode,
                    buffer_multiplier,
                )
                dur = str(buffered)

            lines.append(
                f"{incoming_commute['fromLoc']} → {incoming_commute['toLoc']} [{dur}] {emoji} {COMMUTE_MARKER}"
            )

        # Task line
        task_str = t["text"]
        if t.get("uuid"):
            task_str += f" |{t['uuid']}|"
        task_str += f" [{t['duration']}]"
        if t.get("time"):
            task_str += f" ({t['time']})"
        if t.get("location"):
            task_str += f" {t['location']}"
        lines.append(task_str)

    lines.append(SPLITTER)
    lines.append("")
    return "\n".join(lines) + "\n"


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == "test":
        sample = [
            "lecture [1h30] (10am) @Campus\n",
            "@Campus → @Office [30] 🚗 //{::commute::}\n",
            "lab [2h] (14:00) @Office\n",
            "workout [1h] @Gym\n",
            "-------------\n",
        ]
        parsed = parse_daily_commute_plan(sample)
        print("Parsed:", json.dumps(parsed, indent=2))
        serialized = serialize_daily_commute_plan(parsed["tasks"], parsed["commutes"])
        print("\nSerialized:\n" + serialized)
