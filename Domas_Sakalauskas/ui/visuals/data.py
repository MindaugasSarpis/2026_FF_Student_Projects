"""Loads the tables once for all visuals + shared helpers (game picker, cleaned shots)."""
import os
from pathlib import Path

import pandas as pd
import numpy as np
import streamlit as st

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = Path(os.environ.get("HUB_DATA_DIR", ROOT / "data" / "processed"))


@st.cache_data(show_spinner=False)
def _read(path: str, mtime: float) -> pd.DataFrame:  # mtime in the key: re-import -> fresh data
    return pd.read_csv(path)


def table(name: str) -> pd.DataFrame:
    path = DATA_DIR / f"{name}.csv"
    if not path.exists():
        return pd.DataFrame()
    return _read(str(path), path.stat().st_mtime)


def load() -> dict:
    """matches (newest first, with a readable 'label'), events, team_stats, appearances."""
    matches = table("matches").copy()
    if not matches.empty:
        date = matches["date"].astype(str).str[:10] if "date" in matches else matches["session_id"].astype(str)
        opp = matches["opponent"].astype(str) if "opponent" in matches else ""
        matches["label"] = date + " vs " + opp
        matches = matches.sort_values("label", ascending=False)
    events = table("events").copy()
    for col in ("from_x", "from_y", "to_x", "to_y"):
        if col in events:
            events[col] = pd.to_numeric(events[col], errors="coerce")
    return {"matches": matches, "events": events, "team_stats": table("team_stats"), "appearances": table("appearances")}

_ZONE = r"^(\d)(HL|L|C|HR|R)$"   # zone codes like 2L, 1HR, 4C: number = distance towards the goal being attacked
_SIDE = {"L": -2, "HL": -1, "C": 0, "HR": 1, "R": 2}


def _sign(a, b):
    """+1 if a grows with b, -1 if it shrinks (not enough data: +1)."""
    ok = a.notna() & b.notna()
    if ok.sum() < 10 or a[ok].std() == 0 or b[ok].std() == 0:
        return 1
    return 1 if np.corrcoef(a[ok], b[ok])[0, 1] >= 0 else -1


def orientation(ev: pd.DataFrame) -> dict:
    """For every (game, team, half): do the x / y coordinates run the same way as the zone codes?

    Zone codes (1L, 2HR, 4C ...) are always from the team's own view: a higher number = closer to the goal it attacks,
    L = its left, R = its right. Comparing them with the coordinates shows, per game/team/half, whether x or y has
    to be mirrored to get the attacker's view. Returns {(session_id, team, half): (x_sign, y_sign)}.
    """
    z = ev["from_zone"].astype(str).str.extract(_ZONE)
    d = pd.DataFrame({"session_id": ev["session_id"], "team": ev["team"], "half": ev["half"], "x": ev["from_x"],
                      "y": ev["from_y"], "num": pd.to_numeric(z[0]), "side": z[1].map(_SIDE)})
    return {key: (_sign(g["x"], g["num"]), _sign(g["y"], g["side"])) for key, g in d.groupby(["session_id", "team", "half"])}

def shots(data: dict):
    """All shot events as (clean, removed).

    - The shooter of a shot is stored in player_from_*, so it is copied to 'shooter_id' / 'shooter'.
    - Known system glitch: right after OUR shot the system sometimes adds a second 'opponent' shot row with the same
      player of ours (a duplicate). Such rows are returned in 'removed', not counted as opponent shots.
    - An opponent shot that only has one of our players as shooter (tagger picked the wrong player) is a real
      opponent shot: it is kept, with the shooter shown as unknown.
    """
    ev = data["events"].sort_values(["session_id", "event_id"]).copy()
    prev = ev.groupby("session_id")[["event", "team", "player_from_id"]].shift(1)
    s = ev[ev["event"] == "shot"].copy()
    p = prev.loc[s.index]
    s["shooter_id"] = pd.to_numeric(s["player_from_id"], errors="coerce").fillna(pd.to_numeric(s["player_id"], errors="coerce"))
    s["shooter"] = s["player_from"].fillna(s["player"])
    ours = set(pd.to_numeric(data["appearances"].get("player_id", pd.Series(dtype=float)), errors="coerce").dropna())
    ours_shooter = (s["team"] == "opponent") & s["shooter_id"].isin(ours)
    duplicate = ours_shooter & (p["event"] == "shot") & (p["team"] == "ours") & \
        (pd.to_numeric(p["player_from_id"], errors="coerce") == s["shooter_id"])
    wrong_player = ours_shooter & ~duplicate
    s.loc[wrong_player, ["shooter_id", "shooter"]] = [float("nan"), "Unknown opponent player"]
    # attacker's view: ox = distance towards the goal attacked (0-100), oy = across the pitch, small = the shooter's left
    flags = orientation(ev)
    keys = list(zip(s["session_id"], s["team"], s["half"]))
    fx = np.array([flags.get(k, (1, 1))[0] for k in keys])
    fy = np.array([flags.get(k, (1, 1))[1] for k in keys])
    s["ox"] = np.where(fx > 0, s["from_x"], 100 - s["from_x"])
    s["oy"] = np.where(fy > 0, s["from_y"], 100 - s["from_y"])
    s["flip_x"], s["flip_y"] = fx < 0, fy < 0
    return s[~duplicate], s[duplicate]


def pick_games(st_, data: dict, key: str) -> list:
    """Game picker: newest game by default, or tick 'all games'. Returns a list of session_ids."""
    matches = data["matches"]
    if matches.empty:
        return []
    labels = dict(zip(matches["session_id"], matches["label"]))
    ids = list(labels)
    if st_.checkbox("All games", key=f"{key}_all"):
        return ids
    return st_.multiselect("Games", ids, default=ids[:1], format_func=labels.get, key=f"{key}_games")