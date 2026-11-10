"""Pure parsing: club-system JSON (dict) -> pandas DataFrames.

No file I/O and no prompts here, so it is easy to test and to extend.
If the club system adds new fields, they usually need a change only in this file.

Every table has a `session_id` column (the club system's unique game ID),
which is the key used to overwrite a game when it is re-imported.
"""
from __future__ import annotations

import re
from typing import Any

import pandas as pd

SUPPORTED_PACKAGE_VERSIONS = {2}  # warn (not fail) if the export format changes
PERIODS = ("total", "first_half", "second_half", "extra_time")


def clean_name(name: str | None) -> str | None:
    """Collapse repeated whitespace, e.g. 'Kipras  Urbanavičius' -> 'Kipras Urbanavičius'."""
    if name is None:
        return None
    return re.sub(r"\s+", " ", str(name)).strip()


def _num(x: Any) -> float | None:
    """Coordinates come as strings ('49.23'); convert, keep None as NaN."""
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


# --------------------------------------------------------------------------- match
def parse_match(data: dict) -> dict:
    m = data["match"]
    score = m.get("score") or {}
    return {
        "session_id": m["session_id"],
        "season": m.get("season"),
        "date": m.get("date"),
        "team_id": (m.get("team") or {}).get("id"),
        "team_name": (m.get("team") or {}).get("name"),
        "opponent": clean_name(m.get("opponent")),
        "goals_for": score.get("ours"),
        "goals_against": score.get("opponent"),
        "tagging_version_id": data.get("tagging_version_id"),
        "data_quality_status": (data.get("data_quality") or {}).get("status"),
        "data_quality_version": (data.get("data_quality") or {}).get("version"),
        "exported_at": data.get("generated_at"),
        "package_version": data.get("package_version"),
    }


def goals_from_events(data: dict) -> tuple[int, int]:
    """Count goals from shot events tagged 'goal' (cross-check for the score)."""
    ours = opp = 0
    for e in data.get("events", []):
        if e.get("event_code") == "shot" and "goal" in (e.get("tags") or []):
            if e.get("team") == "ours":
                ours += 1
            else:
                opp += 1
    return ours, opp


# --------------------------------------------------------------------------- team stats
def parse_team_stats(data: dict) -> pd.DataFrame:
    """Long format: session_id, period, metric, label, type, ours, opponent."""
    sid = data["match"]["session_id"]
    rows = []
    for period in PERIODS:
        for item in (data.get("team_metrics") or {}).get(period, []):
            rows.append(
                {
                    "session_id": sid,
                    "period": period,
                    "metric": item["key"],
                    "label": item.get("label"),
                    "type": item.get("type"),
                    "ours": item.get("ours"),
                    "opponent": item.get("opponent"),
                }
            )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- players
def parse_appearances(data: dict) -> pd.DataFrame:
    """One row per squad member in the match (starters, subs used, unused bench)."""
    sid = data["match"]["session_id"]
    rows = []
    for r in data["players"]["rows"]:
        rows.append(
            {
                "session_id": sid,
                "player_id": r["id"],
                "name": clean_name(r["name"]),
                "jersey_number": r.get("jersey_number"),
                "lineup_role": r.get("lineup_role"),  # starting / substitute / bench
                "position_system": r.get("lineup_position"),  # as logged in the club system
                "position": r.get("lineup_position"),  # final value; manual override applies here
                "position_overridden": False,
                "minutes_played": r.get("minutes_played"),
                "ball_possession_minutes": r.get("ball_possession_minutes"),
            }
        )
    return pd.DataFrame(rows)


def parse_player_stats(data: dict) -> pd.DataFrame:
    """Long format: session_id, player_id, metric, value.

    A metric a player does not have is simply absent (NOT turned into 0).
    All ~60 metrics are kept; prune later in the display layer.
    """
    sid = data["match"]["session_id"]
    rows = []
    for r in data["players"]["rows"]:
        for key, value in (r.get("metrics") or {}).items():
            rows.append({"session_id": sid, "player_id": r["id"], "metric": key, "value": value})
    return pd.DataFrame(rows)


def parse_metrics_dictionary(data: dict) -> pd.DataFrame:
    """Reference table: metric key -> name/category/type/description (club system's dictionary)."""
    rows = []
    for m in data.get("metrics_dictionary", []):
        rows.append({k: m.get(k) for k in ("key", "name", "category", "type", "source", "description", "counted_as", "player_attribution", "team_scope")})
    ind = {i["statistic_key"]: i for i in (data.get("players") or {}).get("indicators", [])}
    df = pd.DataFrame(rows)
    if not df.empty:
        df["player_indicator"] = df["key"].isin(ind)
    return df


# --------------------------------------------------------------------------- substitutions
def parse_substitutions(data: dict) -> pd.DataFrame:
    sid = data["match"]["session_id"]
    rows = []
    for s in data.get("substitutions", []):
        rows.append(
            {
                "session_id": sid,
                "event_id": s.get("event_id"),
                "match_time": s.get("match_time"),
                "match_time_formatted": s.get("match_time_formatted"),
                "half": s.get("half"),
                "player_out_id": s.get("player_out_id"),
                "player_out_name": clean_name(s.get("player_out_name")),
                "player_out_position": s.get("player_out_position"),
                "player_in_id": s.get("player_in_id"),
                "player_in_name": clean_name(s.get("player_in_name")),
                "player_in_position": s.get("player_in_position"),
            }
        )
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- events
def parse_events(data: dict) -> pd.DataFrame:
    sid = data["match"]["session_id"]
    rows = []
    for e in data.get("events", []):
        rows.append(
            {
                "session_id": sid,
                "event_id": e["id"],
                "possession_id": e.get("possession_id"),
                "match_time": e.get("match_time"),
                "time": e.get("match_time_formatted"),
                "half": e.get("half"),
                "team": e.get("team"),
                "phase": e.get("phase"),
                "event": e.get("event_code"),
                "tags": "|".join(e.get("tags") or []),
                "player_from_id": e.get("player_from_id"),
                "player_from": clean_name(e.get("player_from_name")),
                "player_to_id": e.get("player_to_id"),
                "player_to": clean_name(e.get("player_to_name")),
                "player_id": e.get("player_id"),
                "player": clean_name(e.get("player_name")),
                "from_zone": e.get("from_zone_code"),
                "to_zone": e.get("to_zone_code"),
                "from_x": _num(e.get("from_coordinates_x")),
                "from_y": _num(e.get("from_coordinates_y")),
                "to_x": _num(e.get("coordinates_x")),
                "to_y": _num(e.get("coordinates_y")),
                "source": e.get("source"),
                "incomplete": bool(e.get("is_incomplete")),
            }
        )
    df = pd.DataFrame(rows)
    for col in ("possession_id", "player_from_id", "player_to_id", "player_id"):
        if col in df:
            df[col] = df[col].astype("Int64")
    return df


# --------------------------------------------------------------------------- sequences
def parse_sequences(data: dict) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Returns (sequences, sequence_players, sequence_events).

    sequence_events only links sequence_id -> event_id (full event data lives in the events file).
    """
    sid = data["match"]["session_id"]
    seq_rows, player_rows, event_rows = [], [], []
    for s in (data.get("sequences") or {}).get("list", []):
        seq_rows.append(
            {
                "session_id": sid,
                "sequence_id": s["id"],
                "team": s.get("team"),
                "half": s.get("half"),
                "started_at": s.get("started_at"),
                "ended_at": s.get("ended_at"),
                "duration_seconds": s.get("duration_seconds"),
                "event_count": s.get("event_count"),
                "start_event": s.get("start_event_code"),
                "end_event": s.get("end_event_code"),
                "start_tags": "|".join(s.get("start_tags") or []),
                "end_tags": "|".join(s.get("end_tags") or []),
                "time": s.get("match_time_formatted"),
            }
        )
        for p in s.get("players") or []:
            player_rows.append({"session_id": sid, "sequence_id": s["id"], "player_id": p.get("id"), "jersey_number": p.get("jersey_number")})
        for ev in s.get("events") or []:
            event_rows.append({"session_id": sid, "sequence_id": s["id"], "event_id": ev.get("event_id"), "sort_order": ev.get("sort_order"), "role": ev.get("role")})
    return pd.DataFrame(seq_rows), pd.DataFrame(player_rows), pd.DataFrame(event_rows)


def parse_sequence_overview(data: dict) -> pd.DataFrame:
    sid = data["match"]["session_id"]
    rows = []
    for side, vals in ((data.get("sequences") or {}).get("overview") or {}).items():
        rows.append({"session_id": sid, "side": side, **vals})
    return pd.DataFrame(rows)


# --------------------------------------------------------------------------- everything
def parse_all(data: dict) -> dict[str, pd.DataFrame | dict]:
    seq, seq_players, seq_events = parse_sequences(data)
    return {
        "match": parse_match(data),
        "team_stats": parse_team_stats(data),
        "appearances": parse_appearances(data),
        "player_stats": parse_player_stats(data),
        "substitutions": parse_substitutions(data),
        "events": parse_events(data),
        "sequences": seq,
        "sequence_players": seq_players,
        "sequence_events": seq_events,
        "sequence_overview": parse_sequence_overview(data),
        "metrics_dictionary": parse_metrics_dictionary(data),
    }
